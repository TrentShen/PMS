# 消息提醒 + 催办 API（PRD 3.5）
# V0.9 阶段：写 notification_log 表但不真发（Sprint 1 接企微后真发）
# 提供：手动催办 + 查看自己的通知列表
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.audit import NotificationLog
from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, require_role

router = APIRouter(prefix="/notify", tags=["notify"])


class UrgeRequest(BaseModel):
    cycle_id: int
    user_ids: list[int]  # 要催办的用户
    message: str | None = None


class NotifyView(BaseModel):
    id: int
    title: str
    content: str
    status: str
    created_at: str


# ============ 催办（HRBP / Leader / 上级可发起）============

@router.post("/urge")
def send_urge(
    payload: UrgeRequest,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 权限：hrbp / super_admin / dept_leader / 直属上级
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
        # 写 notification_log（status=pending，Sprint 1 接企微后异步真发）
        session.add(NotificationLog(
            target_userid=user.wecom_userid,
            channel="wecom",
            title="催办通知",
            content=payload.message or f"{current.name} 提醒你尽快完成绩效任务",
            payload={"cycle_id": payload.cycle_id, "from": current.wecom_userid},
            status="pending",
        ))
        count += 1

    session.commit()
    return {"sent": count, "note": "消息已入队（企微推送待 Sprint 1 接入）"}


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


# ============ 周期时间线配置（存在 performance_cycle 的 stage_json 里）============
# PRD 3.2.3：各环节时间节点
# 为简化，直接在创建周期时配置（前端可选填），或后续通过 PATCH 修改

class StageConfig(BaseModel):
    stages: dict  # 例如 {"self_eval_start":"2025-01-06","self_eval_end":"2025-01-13",...}


@router.patch("/cycles/{cycle_id}/stages")
def update_stage_config(
    cycle_id: int,
    payload: StageConfig,
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    # 暂存为 JSON 字段；APScheduler 定时任务扫描该字段触发提醒
    from sqlalchemy import text
    session.execute(
        text("UPDATE performance_cycle SET stage_json = :j WHERE id = :cid"),
        {"j": str(payload.stages), "cid": cycle_id},
    )
    session.commit()
    return {"status": "ok", "stages": payload.stages}
