# APScheduler 定时任务定义（PRD 3.2.3 + 3.5）
# V0.9 阶段：只写 notification_log，不真发消息（Sprint 1 接企微后加真实推送）
# 注册方式：在 main.py 的 lifespan 中调用 start_scheduler()
from datetime import date, datetime

from loguru import logger
from sqlmodel import Session, select

from pms.database.models.audit import NotificationLog
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.user import User
from pms.database.session import engine


def check_deadline_reminders():
    """每小时执行一次：扫描进行中的周期，
    对截止前 3天/1天 未完成的参与人生成提醒（幂等，每天同类型最多 1 条）"""
    today = date.today()
    with Session(engine) as s:
        cycles = s.exec(
            select(PerformanceCycle).where(PerformanceCycle.status == "in_progress")
        ).all()
        for cycle in cycles:
            # 找出状态还是 pending（未自评）的人
            pending = s.exec(
                select(CycleParticipant, User)
                .join(User, User.id == CycleParticipant.user_id)
                .where(
                    CycleParticipant.cycle_id == cycle.id,
                    CycleParticipant.status == "pending",
                )
            ).all()
            for p, u in pending:
                # 幂等：今天已发过就跳过
                key = f"deadline_remind:{cycle.id}:{u.wecom_userid}:{today.isoformat()}"
                exists = s.exec(
                    select(NotificationLog).where(
                        NotificationLog.target_userid == u.wecom_userid,
                        NotificationLog.title == "自评截止提醒",
                        NotificationLog.created_at >= datetime(today.year, today.month, today.day),
                    )
                ).first()
                if exists:
                    continue
                s.add(NotificationLog(
                    target_userid=u.wecom_userid,
                    channel="wecom",
                    title="自评截止提醒",
                    content=f"「{cycle.name}」自评尚未完成，请尽快提交。",
                    payload={"cycle_id": cycle.id},
                    status="pending",
                ))
            s.commit()
            if pending:
                logger.info("周期 {} 提醒 {} 人自评", cycle.name, len(pending))


def start_scheduler():
    """启动定时任务调度器（进程内，非阻塞）"""
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    # 每小时检查一次截止提醒
    scheduler.add_job(check_deadline_reminders, "interval", hours=1, id="deadline_remind")
    scheduler.start()
    logger.info("APScheduler started: deadline_remind (hourly)")
