# APScheduler 定时任务（PRD 3.2.3 + 3.5）
# 每小时扫描一次进行中的周期，按 stage_json 配置的时间节点自动生成提醒
from datetime import date, datetime

from loguru import logger
from sqlmodel import Session, select

from pms.database.models.audit import NotificationLog
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.user import User
from pms.database.session import engine

# 环节名 → 提醒标题
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
    # 幂等：同一天同类型最多 1 条
    exists = s.exec(
        select(NotificationLog).where(
            NotificationLog.target_userid == userid,
            NotificationLog.title == title,
            NotificationLog.created_at >= datetime(today.year, today.month, today.day),
        )
    ).first()
    return exists is not None


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

            # 遍历各环节的 _end 日期
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

                # 截止前3天、1天、当天发提醒
                if days_left not in (3, 1, 0):
                    continue

                if days_left == 0:
                    title = f"{label}今日截止"
                    content = f"「{cycle.name}」{label}环节今日截止，请尽快完成。"
                else:
                    title = f"{label}即将截止"
                    content = f"「{cycle.name}」{label}环节将在 {days_left} 天后截止，请尽快完成。"

                # 给所有 pending 状态的参与人发
                participants = s.exec(
                    select(CycleParticipant, User)
                    .join(User, User.id == CycleParticipant.user_id)
                    .where(
                        CycleParticipant.cycle_id == cycle.id,
                        CycleParticipant.status.in_(["pending", "self_done"]),
                    )
                ).all()

                sent = 0
                for p, u in participants:
                    if _already_notified(s, u.wecom_userid, title, today):
                        continue
                    s.add(NotificationLog(
                        target_userid=u.wecom_userid,
                        channel="wecom",
                        title=title,
                        content=content,
                        payload={"cycle_id": cycle.id, "stage": stage_key, "days_left": days_left},
                        status="pending",
                    ))
                    sent += 1

                if sent > 0:
                    s.commit()
                    logger.info("周期 {} / {} 截止提醒: 发送 {} 人", cycle.name, label, sent)


def check_deadline_reminders():
    """兜底：没有配置 stage_json 的周期，给 pending 人员发通用提醒"""
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
            for p, u in pending:
                title = "自评截止提醒"
                if _already_notified(s, u.wecom_userid, title, today):
                    continue
                s.add(NotificationLog(
                    target_userid=u.wecom_userid,
                    channel="wecom",
                    title=title,
                    content=f"「{cycle.name}」自评尚未完成，请尽快提交。",
                    payload={"cycle_id": cycle.id},
                    status="pending",
                ))
            s.commit()
            if pending:
                logger.info("周期 {} 通用提醒 {} 人", cycle.name, len(pending))


def start_scheduler():
    """启动定时任务调度器"""
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    # 每小时检查时间节点提醒
    scheduler.add_job(check_stage_reminders, "interval", hours=1, id="stage_remind")
    # 每天早上 9 点通用提醒
    scheduler.add_job(check_deadline_reminders, "cron", hour=9, id="deadline_remind")
    scheduler.start()
    logger.info("APScheduler started: stage_remind (hourly) + deadline_remind (daily 9am)")
