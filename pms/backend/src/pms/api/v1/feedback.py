from __future__ import annotations

# 绩效反馈 API（PRD 3.4.8）
# 上级创建/编辑面谈记录 → 员工确认/有异议
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.feedback import FeedbackRecord
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user
from pms.utils.audit import write_audit

router = APIRouter(prefix="/feedback", tags=["feedback"])


# ============ Schema ============

class FeedbackCreate(BaseModel):
    strengths: str       # 员工优势
    improvements: str    # 待改进项
    next_goals: str      # 下阶段目标/期望


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
    is_superior = target.leader_userid == current.wecom_userid
    is_admin = current.role in ("hrbp", "super_admin", "dept_leader")
    if not (is_superior or is_admin):
        raise HTTPException(status_code=403, detail="你不是该员工的直属上级")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")
    # 必须在 published 状态才能写反馈（校准完才有最终结果）
    if cycle.status != "published":
        raise HTTPException(status_code=400, detail="周期未发布，不能填写反馈")

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
    is_superior = target.leader_userid == current.wecom_userid
    is_admin = current.role in ("hrbp", "super_admin", "dept_leader")
    if not (is_self or is_superior or is_admin):
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
        fb.confirmed_at = datetime.utcnow()
    elif payload.action == "disputed":
        if not payload.comment or not payload.comment.strip():
            raise HTTPException(status_code=400, detail="有异议时必须填写原因")
        fb.confirm_status = "disputed"
        fb.dispute_comment = payload.comment
        fb.confirmed_at = datetime.utcnow()
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
    return {"status": fb.confirm_status}


# ============ Leader 查看下属反馈状态列表 ============

@router.get("/cycles/{cycle_id}/list")
def list_feedback_status(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # Leader / HR 查看本周期所有反馈状态
    if current.role not in ("dept_leader", "hrbp", "super_admin"):
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
