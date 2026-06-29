from __future__ import annotations

# 绩效反馈 API（PRD 3.4.8）
# 上级创建/编辑面谈记录 → 员工确认/有异议
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.feedback import FeedbackRecord
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import SUPERIOR_ROLES, can_act_as_superior, get_current_user, has_any_role, require_fte
from pms.services.notification import get_hrbp_userids, send_textcard_notification
from pms.utils.audit import write_audit

router = APIRouter(
    prefix="/feedback",
    tags=["feedback"],
    dependencies=[Depends(require_fte)],
)


# ============ Schema ============

class FeedbackCreate(BaseModel):
    strengths: str       # 员工优势
    improvements: str    # 待改进项
    next_goals: str      # 下阶段目标/期望

    def validate(self) -> None:
        for field, label in [(self.strengths, "员工优势"), (self.improvements, "待改进项"), (self.next_goals, "下阶段目标")]:
            if not field or not field.strip():
                raise ValueError(f"{label} 不能为空")


class FeedbackView(BaseModel):
    id: int
    cycle_id: int
    user_id: int
    interviewer_name: str
    strengths: str
    improvements: str
    next_goals: str
    confirm_status: str
    dispute_comment: str | None
    created_at: str
    confirmed_at: str | None


class ConfirmAction(BaseModel):
    action: str  # confirmed / disputed
    comment: str | None = None  # 异议时填写原因


# ============ 上级创建/编辑面谈记录 ============

@router.post("/cycles/{cycle_id}/users/{user_id}")
def create_or_update_feedback(
    cycle_id: int,
    user_id: int,
    payload: FeedbackCreate,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 只有直属上级 / HR / 超管可以写
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="员工不存在")
    if current.id != user_id and not can_act_as_superior(current, target, allowed_roles=SUPERIOR_ROLES):
        raise HTTPException(status_code=403, detail="你不是该员工的直属上级")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if not cycle.enable_feedback:
        raise HTTPException(status_code=400, detail="当前周期未开启绩效反馈")
    # 必须在 in_progress 或 published 状态才能写反馈
    # 校准完成后即可面谈，满足"先沟通后公开"原则
    if cycle.status not in ("in_progress", "published"):
        raise HTTPException(status_code=400, detail="当前周期状态不允许填写反馈")

    try:
        payload.validate()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # upsert
    existing = session.exec(
        select(FeedbackRecord).where(
            FeedbackRecord.cycle_id == cycle_id,
            FeedbackRecord.user_id == user_id,
        )
    ).first()

    if existing:
        existing.strengths = payload.strengths
        existing.improvements = payload.improvements
        existing.next_goals = payload.next_goals
        existing.interviewer_userid = current.wecom_userid
        existing.interviewer_name = current.name
        session.add(existing)
        fb = existing
    else:
        fb = FeedbackRecord(
            cycle_id=cycle_id,
            user_id=user_id,
            interviewer_userid=current.wecom_userid,
            interviewer_name=current.name,
            strengths=payload.strengths,
            improvements=payload.improvements,
            next_goals=payload.next_goals,
        )
        session.add(fb)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="create_feedback",
        resource_type="feedback_record",
        resource_id=f"{cycle_id}:{user_id}",
        after={"strengths": payload.strengths[:50]},
    )
    session.commit()
    session.refresh(fb)

    # 通知员工查看反馈
    if target.wecom_userid:
        send_textcard_notification(
            target_userids=[target.wecom_userid],
            title="绩效反馈已填写",
            description=f"你的「{cycle.name}」绩效反馈已填写，请查看并确认。",
            url=f"/feedback/{cycle.id}",
            payload={"cycle_id": cycle.id, "user_id": target.id, "event": "feedback_created"},
        )

    return _to_view(fb)


# ============ 查看面谈记录（上级/员工本人/HR） ============

@router.get("/cycles/{cycle_id}/users/{user_id}")
def get_feedback(
    cycle_id: int,
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 员工本人 + 上级 + HR 可看
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="员工不存在")
    is_self = current.id == user_id
    if not is_self and not can_act_as_superior(current, target, allowed_roles=SUPERIOR_ROLES):
        raise HTTPException(status_code=403, detail="无权查看")

    fb = session.exec(
        select(FeedbackRecord).where(
            FeedbackRecord.cycle_id == cycle_id,
            FeedbackRecord.user_id == user_id,
        )
    ).first()
    if not fb:
        return None
    return _to_view(fb)


# ============ 员工确认/有异议 ============

@router.post("/cycles/{cycle_id}/confirm")
def confirm_feedback(
    cycle_id: int,
    payload: ConfirmAction,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 员工只能对自己的反馈做确认
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    if not cycle.enable_feedback:
        raise HTTPException(status_code=400, detail="当前周期未开启绩效反馈")

    fb = session.exec(
        select(FeedbackRecord).where(
            FeedbackRecord.cycle_id == cycle_id,
            FeedbackRecord.user_id == current.id,
        )
    ).first()
    if not fb:
        raise HTTPException(status_code=404, detail="暂无反馈记录")
    if fb.confirm_status != "pending":
        raise HTTPException(status_code=400, detail="已确认过，不能重复操作")

    if payload.action == "confirmed":
        fb.confirm_status = "confirmed"
        fb.confirmed_at = datetime.now(timezone.utc)
    elif payload.action == "disputed":
        if not payload.comment or not payload.comment.strip():
            raise HTTPException(status_code=400, detail="有异议时必须填写原因")
        fb.confirm_status = "disputed"
        fb.dispute_comment = payload.comment
        fb.confirmed_at = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=400, detail="action 只能是 confirmed/disputed")

    session.add(fb)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="confirm_feedback",
        resource_type="feedback_record",
        resource_id=f"{cycle_id}:{current.id}",
        after={"action": payload.action},
    )
    session.commit()

    # 通知直属上级和 HRBP
    notify_userids: set[str] = set()
    if current.leader_userid:
        notify_userids.add(current.leader_userid)
    notify_userids.update(get_hrbp_userids(session, current))
    if notify_userids:
        action_label = "已确认" if payload.action == "confirmed" else "有异议"
        send_textcard_notification(
            target_userids=list(notify_userids),
            title=f"员工绩效反馈{action_label}",
            description=f"员工 {current.name} 对「{cycle.name}」绩效反馈{action_label}，请及时处理。",
            url=f"/feedback/{cycle.id}/list",
            payload={"cycle_id": cycle.id, "user_id": current.id, "event": "feedback_confirmed"},
        )

    return {"status": fb.confirm_status}


# ============ Leader 查看下属反馈状态列表 ============

@router.get("/cycles/{cycle_id}/list")
def list_feedback_status(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # Leader / HR 查看本周期所有反馈状态
    if current.role not in ("dept_leader", "hrbp", "super_admin", "direct_leader"):
        raise HTTPException(status_code=403, detail="无权限")

    from pms.services.scope import visible_user_ids
    scope = visible_user_ids(session, current)

    q = select(CycleParticipant, User).join(
        User, User.id == CycleParticipant.user_id
    ).where(CycleParticipant.cycle_id == cycle_id)
    if scope is not None:
        q = q.where(CycleParticipant.user_id.in_(scope))

    rows = session.exec(q).all()
    result = []
    for p, u in rows:
        fb = session.exec(
            select(FeedbackRecord).where(
                FeedbackRecord.cycle_id == cycle_id,
                FeedbackRecord.user_id == p.user_id,
            )
        ).first()
        result.append({
            "user_id": p.user_id,
            "user_name": u.name,
            "has_feedback": fb is not None,
            "confirm_status": fb.confirm_status if fb else None,
        })
    return result


def _to_view(fb: FeedbackRecord) -> FeedbackView:
    return FeedbackView(
        id=fb.id,
        cycle_id=fb.cycle_id,
        user_id=fb.user_id,
        interviewer_name=fb.interviewer_name,
        strengths=fb.strengths,
        improvements=fb.improvements,
        next_goals=fb.next_goals,
        confirm_status=fb.confirm_status,
        dispute_comment=fb.dispute_comment,
        created_at=fb.created_at.isoformat(),
        confirmed_at=fb.confirmed_at.isoformat() if fb.confirmed_at else None,
    )
