from __future__ import annotations

# 消息提醒 + 催办 API
# 催办写 notification_log 后即时调企微发送；失败标记待重试
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.configs import settings
from pms.database.models.audit import NotificationLog
from pms.database.models.cycle import PerformanceCycle
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, require_role
from pms.services.wecom import send_textcard

router = APIRouter(prefix="/notify", tags=["notify"])

MAX_RETRIES = 3


class UrgeRequest(BaseModel):
    cycle_id: int
    user_ids: list[int]
    message: str | None = None


class NotifyView(BaseModel):
    id: int
    title: str
    content: str
    status: str
    created_at: str


def _send_and_log(notification: NotificationLog, session: Session) -> None:
    """调企微发送并更新日志；失败计入 retry_count"""
    try:
        send_textcard(
            user_ids=[notification.target_userid],
            title=notification.title,
            description=notification.content,
            url=f"{settings.frontend_origin}",
        )
        notification.status = "sent"
        notification.sent_at = datetime.now(timezone.utc)
        logger.info("企微消息发送成功: {} -> {}", notification.title, notification.target_userid)
    except Exception as e:
        notification.retry_count = (notification.retry_count or 0) + 1
        notification.error_msg = str(e)[:256]
        if notification.retry_count >= MAX_RETRIES:
            notification.status = "failed"
            logger.error("企微消息发送失败(已耗尽重试): {} -> {} {}", notification.title, notification.target_userid, e)
        else:
            notification.status = "retry"
            logger.warning("企微消息发送失败(将重试): {} -> {} {}", notification.title, notification.target_userid, e)
    session.commit()


# ============ 催办 ============

@router.post("/urge")
def send_urge(
    payload: UrgeRequest,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    if current.role == "employee":
        raise HTTPException(status_code=403, detail="普通员工不能发起催办")

    cycle = session.get(PerformanceCycle, payload.cycle_id)
    if not cycle or cycle.status not in ("in_progress", "published"):
        raise HTTPException(status_code=400, detail="周期不在进行中或已归档")

    count = 0
    for uid in payload.user_ids:
        user = session.get(User, uid)
        if not user:
            continue
        notification = NotificationLog(
            target_userid=user.wecom_userid,
            channel="wecom",
            title="催办通知",
            content=payload.message or f"{current.name} 提醒你尽快完成「{cycle.name}」的绩效任务",
            payload={"cycle_id": payload.cycle_id, "from": current.wecom_userid},
            status="pending",
        )
        session.add(notification)
        session.commit()
        _send_and_log(notification, session)
        count += 1

    return {"sent": count}


# ============ 重试失败消息 ============

@router.post("/retry")
def retry_failed(
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    """手动重试所有 status=retry 的通知"""
    pending = session.exec(
        select(NotificationLog).where(NotificationLog.status == "retry")
    ).all()
    sent = 0
    for n in pending:
        _send_and_log(n, session)
        sent += 1
    return {"retried": sent}


# ============ 我的通知列表 ============

@router.get("/mine", response_model=list[NotifyView])
def my_notifications(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    logs = session.exec(
        select(NotificationLog)
        .where(NotificationLog.target_userid == current.wecom_userid)
        .order_by(NotificationLog.created_at.desc())
        .limit(50)
    ).all()
    return [
        NotifyView(
            id=n.id,
            title=n.title,
            content=n.content,
            status=n.status,
            created_at=n.created_at.isoformat(),
        )
        for n in logs
    ]


# ============ 周期时间线 ============

class StageConfig(BaseModel):
    self_eval_start: str | None = None
    self_eval_end: str | None = None
    peer_confirm_start: str | None = None
    peer_confirm_end: str | None = None
    peer_eval_start: str | None = None
    peer_eval_end: str | None = None
    superior_eval_start: str | None = None
    superior_eval_end: str | None = None
    calibration_start: str | None = None
    calibration_end: str | None = None
    approval_start: str | None = None
    approval_end: str | None = None
    feedback_start: str | None = None
    feedback_end: str | None = None
    publish_date: str | None = None


@router.get("/cycles/{cycle_id}/stages")
def get_stage_config(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    return {"cycle_id": cycle_id, "stages": cycle.stage_json}


@router.put("/cycles/{cycle_id}/stages")
def update_stage_config(
    cycle_id: int,
    payload: StageConfig,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    cycle.stage_json = payload.model_dump(exclude_none=True)
    session.add(cycle)
    session.commit()
    return {"status": "ok", "stages": cycle.stage_json}
