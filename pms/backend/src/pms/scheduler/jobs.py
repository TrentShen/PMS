# APScheduler 定时任务：提醒扫描 + 通讯录同步
from datetime import date, datetime

from loguru import logger
from sqlmodel import Session, select

from pms.database.models.audit import NotificationLog
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.user import User
from pms.database.session import engine

STAGE_LABELS = {
    "self_eval": "自评",
    "peer_confirm": "互评名单确认",
    "peer_eval": "互评",
    "superior_eval": "上级评估",
    "calibration": "绩效校准",
    "approval": "公司级审批",
    "feedback": "绩效反馈",
}


def _today() -> date:
    return date.today()


def _already_notified(s: Session, userid: str, title: str, today: date) -> bool:
    exists = s.exec(
        select(NotificationLog).where(
            NotificationLog.target_userid == userid,
            NotificationLog.title == title,
            NotificationLog.created_at >= datetime(today.year, today.month, today.day),
        )
    ).first()
    return exists is not None


def _try_send(notification: NotificationLog, s: Session) -> None:
    """调企微发送并更新日志"""
    from pms.services.wecom import send_textcard
    from pms.configs import settings
    try:
        send_textcard(
            user_ids=[notification.target_userid],
            title=notification.title,
            description=notification.content,
            url=f"{settings.frontend_origin}",
        )
        notification.status = "sent"
        notification.sent_at = datetime.utcnow()
    except Exception as e:
        notification.retry_count = (notification.retry_count or 0) + 1
        notification.error_msg = str(e)[:256]
        notification.status = "retry" if notification.retry_count < 3 else "failed"
        logger.warning("企微消息发送失败: {} -> {} {}", notification.title, notification.target_userid, e)
    s.commit()


def check_stage_reminders():
    """按 stage_json 配置的截止日期发送提醒（截止前3天/1天/当天）"""
    today = _today()
    with Session(engine) as s:
        cycles = s.exec(
            select(PerformanceCycle).where(PerformanceCycle.status == "in_progress")
        ).all()

        for cycle in cycles:
            if not cycle.stage_json:
                continue
            stages = cycle.stage_json

            for stage_key, label in STAGE_LABELS.items():
                end_key = f"{stage_key}_end"
                end_str = stages.get(end_key)
                if not end_str:
                    continue
                try:
                    end_date = date.fromisoformat(end_str)
                except ValueError:
                    continue

                days_left = (end_date - today).days
                if days_left not in (3, 1, 0):
                    continue

                if days_left == 0:
                    title = f"{label}今日截止"
                    content = f"「{cycle.name}」{label}环节今日截止，请尽快完成。"
                else:
                    title = f"{label}即将截止"
                    content = f"「{cycle.name}」{label}环节将在 {days_left} 天后截止。"

                participants = s.exec(
                    select(CycleParticipant, User)
                    .join(User, User.id == CycleParticipant.user_id)
                    .where(
                        CycleParticipant.cycle_id == cycle.id,
                        CycleParticipant.status.in_(["pending", "self_done"]),
                    )
                ).all()

                sent_count = 0
                for p, u in participants:
                    if _already_notified(s, u.wecom_userid, title, today):
                        continue
                    notification = NotificationLog(
                        target_userid=u.wecom_userid,
                        channel="wecom",
                        title=title,
                        content=content,
                        payload={"cycle_id": cycle.id, "stage": stage_key, "days_left": days_left},
                        status="pending",
                    )
                    s.add(notification)
                    s.flush()  # 生成 id 但不提交事务
                    sent_count += 1
                    _try_send(notification, s)

                if sent_count:
                    logger.info("周期 {} / {} 截止提醒: {} 人", cycle.name, label, sent_count)


def check_deadline_reminders():
    """兜底：给 pending 人员发通用提醒"""
    today = _today()
    with Session(engine) as s:
        cycles = s.exec(
            select(PerformanceCycle).where(PerformanceCycle.status == "in_progress")
        ).all()
        for cycle in cycles:
            pending = s.exec(
                select(CycleParticipant, User)
                .join(User, User.id == CycleParticipant.user_id)
                .where(
                    CycleParticipant.cycle_id == cycle.id,
                    CycleParticipant.status == "pending",
                )
            ).all()
            sent_count = 0
            for p, u in pending:
                title = "自评截止提醒"
                if _already_notified(s, u.wecom_userid, title, today):
                    continue
                notification = NotificationLog(
                    target_userid=u.wecom_userid,
                    channel="wecom",
                    title=title,
                    content=f"「{cycle.name}」自评尚未完成，请尽快提交。",
                    payload={"cycle_id": cycle.id},
                    status="pending",
                )
                s.add(notification)
                s.flush()
                sent_count += 1
                _try_send(notification, s)
            if sent_count:
                logger.info("周期 {} 通用提醒 {} 人", cycle.name, sent_count)


def sync_contacts_daily():
    """每日 02:00 全量同步企微通讯录"""
    from pms.api.v1.users import _sync_departments, _sync_users
    from pms.database.session import Session, engine
    with Session(engine) as s:
        try:
            _sync_departments(s)
            count = _sync_users(s)
            logger.info("每日通讯录同步完成: {} 个用户", count)
        except Exception:
            logger.exception("每日通讯录同步失败")


def start_scheduler():
    """启动定时任务调度器"""
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    # 每小时检查时间节点提醒
    scheduler.add_job(check_stage_reminders, "interval", hours=1, id="stage_remind")
    # 每天早上 9 点通用提醒
    scheduler.add_job(check_deadline_reminders, "cron", hour=9, id="deadline_remind")
    # 每日凌晨 2 点同步通讯录
    scheduler.add_job(sync_contacts_daily, "cron", hour=2, id="contact_sync")
    scheduler.start()
    logger.info("APScheduler started: stage_remind + deadline_remind + contact_sync")
