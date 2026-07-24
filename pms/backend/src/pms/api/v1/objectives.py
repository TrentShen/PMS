from __future__ import annotations

# 绩效目标 CRUD（员工线上填写 + 上级审批确认）
# PRD 3.3：目标 3-5 条，权重总和 100
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.objective import Objective
from pms.database.models.objective_cycle import ObjectiveCycle
from pms.database.models.objective_cycle_participant import ObjectiveCycleParticipant
from pms.database.models.objective_revision import ObjectiveRevision
from pms.database.models.user import Department, User
from pms.database.session import get_session
from pms.services.auth import can_act_as_superior, get_current_user, has_any_role, require_fte
from pms.utils.audit import write_audit

router = APIRouter(
    prefix="/objective-cycles/{objective_cycle_id}/objectives",
    tags=["objectives"],
    dependencies=[Depends(require_fte)],
)


class ObjectiveInput(BaseModel):
    title: str
    description: str
    measure_criteria: str
    weight: int  # 百分比，所有目标加起来必须 = 100


class ObjectiveBatchSave(BaseModel):
    # 一次性保存该员工在本周期的全部目标（覆盖式）
    items: list[ObjectiveInput]


class ObjectiveView(BaseModel):
    id: int
    title: str
    description: str
    measure_criteria: str
    weight: int
    order_num: int
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    reject_reason: str | None


class RejectPayload(BaseModel):
    reason: str


# ============ 查：我的目标 ============

@router.get("", response_model=list[ObjectiveView])
def list_my_objectives(
    objective_cycle_id: int,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 默认看自己的；HR/Leader 可通过 ?user_id=xxx 看别人的
    target_id = user_id if user_id else current.id
    if target_id != current.id:
        from pms.services.scope import ensure_can_view_user
        ensure_can_view_user(session, current, target_id)

    objs = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id, Objective.user_id == target_id
        ).order_by(Objective.order_num)
    ).all()
    return [ObjectiveView.model_validate(o, from_attributes=True) for o in objs]


# ============ 写：批量保存目标（草稿，覆盖式）============

@router.put("")
def save_objectives(
    objective_cycle_id: int,
    payload: ObjectiveBatchSave,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 员工只能改自己的；目标周期必须在 draft 或 active
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle or cycle.status not in ("draft", "active"):
        raise HTTPException(status_code=400, detail="当前周期状态不允许修改目标")

    # 已提交审批后不能再改草稿（approved/locked 状态的目标不可改）
    existing = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id, Objective.user_id == current.id
        )
    ).all()
    locked = [o for o in existing if o.status in ("approved", "locked")]
    if locked:
        raise HTTPException(
            status_code=400,
            detail="目标已被上级确认，如需调整请发起变更申请",
        )

    # 校验
    if len(payload.items) < 1:
        raise HTTPException(status_code=400, detail="至少需要 1 条目标")
    if len(payload.items) > 10:
        raise HTTPException(status_code=400, detail="目标不能超过 10 条")

    total_weight = sum(item.weight for item in payload.items)
    if total_weight != 100:
        raise HTTPException(status_code=400, detail=f"权重总和必须为 100，当前为 {total_weight}")

    for item in payload.items:
        if not item.title.strip():
            raise HTTPException(status_code=400, detail="目标标题不能为空")
        if item.weight <= 0:
            raise HTTPException(status_code=400, detail="每条目标权重必须大于 0")

    # 删旧 + 写新（覆盖式），状态为 draft
    old = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id, Objective.user_id == current.id
        )
    ).all()
    for o in old:
        session.delete(o)
    session.flush()

    for i, item in enumerate(payload.items):
        session.add(Objective(
            objective_cycle_id=objective_cycle_id,
            user_id=current.id,
            title=item.title.strip(),
            description=item.description.strip(),
            measure_criteria=item.measure_criteria.strip(),
            weight=item.weight,
            order_num=i,
            status="draft",
        ))

    _ensure_participant(session, objective_cycle_id, current.id)
    _sync_participant_status(session, objective_cycle_id, current.id)

    session.commit()
    return {"saved": len(payload.items)}


# ============ 提交上级审批 ============

@router.post("/submit")
def submit_objectives_for_review(
    objective_cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """员工提交目标给上级审批。要求：有 draft 状态目标，权重和=100"""
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle or cycle.status not in ("draft", "active"):
        raise HTTPException(status_code=400, detail="当前周期状态不允许提交目标")

    objs = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id, Objective.user_id == current.id
        )
    ).all()
    if not objs:
        raise HTTPException(status_code=400, detail="尚未填写目标")

    drafts = [o for o in objs if o.status == "draft"]
    if not drafts:
        raise HTTPException(status_code=400, detail="没有待提交的目标")

    total_weight = sum(o.weight for o in objs if o.status in ("draft", "pending_review"))
    if total_weight != 100:
        raise HTTPException(
            status_code=400,
            detail=f"权重总和必须为 100，当前为 {total_weight}",
        )

    for o in drafts:
        o.status = "pending_review"
        o.reviewed_by = None
        o.reviewed_at = None
        o.reject_reason = None
        session.add(o)

    _ensure_participant(session, objective_cycle_id, current.id)
    _sync_participant_status(session, objective_cycle_id, current.id)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="submit_objectives",
        resource_type="objective",
        resource_id=str(objective_cycle_id),
        after={"user_id": current.id, "count": len(drafts)},
    )
    session.commit()
    return {"submitted": len(drafts)}


# ============ 上级审批：批准 ============

@router.post("/users/{user_id}/approve")
def approve_objectives(
    objective_cycle_id: int,
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """上级批准员工提交的目标"""
    # 权限：必须是该员工的直属上级，或 HR/部门 Leader
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not can_act_as_superior(current, target):
        raise HTTPException(status_code=403, detail="无权审批该员工的目标")

    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle or cycle.status not in ("draft", "active"):
        raise HTTPException(status_code=400, detail="当前周期状态不允许审批")

    pending = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id,
            Objective.user_id == user_id,
            Objective.status == "pending_review",
        )
    ).all()
    if not pending:
        raise HTTPException(status_code=400, detail="没有待审批的目标")

    for o in pending:
        o.status = "approved"
        o.reviewed_by = current.wecom_userid
        o.reviewed_at = datetime.now(timezone.utc)
        o.reject_reason = None
        session.add(o)

    _sync_participant_status(session, objective_cycle_id, user_id)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="approve_objectives",
        resource_type="objective",
        resource_id=str(objective_cycle_id),
        after={"user_id": user_id, "count": len(pending)},
    )
    session.commit()
    return {"approved": len(pending)}


# ============ 上级审批：驳回 ============

@router.post("/users/{user_id}/reject")
def reject_objectives(
    objective_cycle_id: int,
    user_id: int,
    payload: RejectPayload,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """上级驳回员工提交的目标，需填写原因"""
    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not can_act_as_superior(current, target):
        raise HTTPException(status_code=403, detail="无权审批该员工的目标")

    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle or cycle.status not in ("draft", "active"):
        raise HTTPException(status_code=400, detail="当前周期状态不允许审批")

    if not payload.reason or not payload.reason.strip():
        raise HTTPException(status_code=400, detail="驳回原因不能为空")

    pending = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id,
            Objective.user_id == user_id,
            Objective.status == "pending_review",
        )
    ).all()
    if not pending:
        raise HTTPException(status_code=400, detail="没有待审批的目标")

    for o in pending:
        o.status = "draft"  # 打回草稿状态，员工可修改后重新提交
        o.reviewed_by = current.wecom_userid
        o.reviewed_at = datetime.now(timezone.utc)
        o.reject_reason = payload.reason.strip()
        session.add(o)

    _sync_participant_status(session, objective_cycle_id, user_id)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="reject_objectives",
        resource_type="objective",
        resource_id=str(objective_cycle_id),
        after={"user_id": user_id, "count": len(pending), "reason": payload.reason.strip()},
    )
    session.commit()
    return {"rejected": len(pending)}


# ============ 目标中途调整（PRD 3.3.3）============

class AdjustmentRequest(BaseModel):
    items: list[ObjectiveInput]
    reason: str


class AdjustmentView(BaseModel):
    id: int
    objective_cycle_id: int
    user_id: int
    reason: str
    old_objectives: list[dict] | None
    new_objectives: list[dict] | None
    status: str
    requested_by_userid: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    reject_reason: str | None
    created_at: str


def _validate_objectives(items: list[ObjectiveInput]) -> None:
    if len(items) < 1:
        raise HTTPException(status_code=400, detail="至少需要 1 条目标")
    if len(items) > 10:
        raise HTTPException(status_code=400, detail="目标不能超过 10 条")
    total_weight = sum(item.weight for item in items)
    if total_weight != 100:
        raise HTTPException(status_code=400, detail=f"权重总和必须为 100，当前为 {total_weight}")
    for item in items:
        if not item.title.strip():
            raise HTTPException(status_code=400, detail="目标标题不能为空")
        if item.weight <= 0:
            raise HTTPException(status_code=400, detail="每条目标权重必须大于 0")


def _snapshot_objectives(objs: list[Objective]) -> list[dict]:
    return [
        {
            "title": o.title,
            "description": o.description,
            "measure_criteria": o.measure_criteria,
            "weight": o.weight,
            "order_num": o.order_num,
            "status": o.status,
        }
        for o in objs
    ]


@router.post("/request-adjustment")
def request_adjustment(
    objective_cycle_id: int,
    payload: AdjustmentRequest,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """员工对已 approved 的目标发起调整申请"""
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle or cycle.status != "active":
        raise HTTPException(status_code=400, detail="当前周期状态不允许调整目标")

    existing = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id,
            Objective.user_id == current.id,
        ).order_by(Objective.order_num)
    ).all()
    approved = [o for o in existing if o.status in ("approved", "locked")]
    if not approved:
        raise HTTPException(status_code=400, detail="当前没有已确认的目标，无需调整申请")

    # 检查是否已有待审批的调整
    pending_adj = session.exec(
        select(ObjectiveRevision).where(
            ObjectiveRevision.objective_cycle_id == objective_cycle_id,
            ObjectiveRevision.user_id == current.id,
            ObjectiveRevision.status == "pending",
        )
    ).first()
    if pending_adj:
        raise HTTPException(status_code=400, detail="已有待审批的调整申请，不能重复提交")

    _validate_objectives(payload.items)

    if not payload.reason or not payload.reason.strip():
        raise HTTPException(status_code=400, detail="调整原因不能为空")

    revision = ObjectiveRevision(
        objective_cycle_id=objective_cycle_id,
        user_id=current.id,
        reason=payload.reason.strip(),
        old_objectives=_snapshot_objectives(existing),
        new_objectives=[
            {
                "title": item.title.strip(),
                "description": item.description.strip(),
                "measure_criteria": item.measure_criteria.strip(),
                "weight": item.weight,
                "order_num": i,
            }
            for i, item in enumerate(payload.items)
        ],
        requested_by_userid=current.wecom_userid,
    )
    session.add(revision)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="request_adjustment",
        resource_type="objective_revision",
        resource_id=str(revision.id),
        after={"reason": payload.reason.strip(), "item_count": len(payload.items)},
    )
    session.commit()
    session.refresh(revision)
    return {"revision_id": revision.id, "status": "pending"}


@router.get("/adjustments", response_model=list[AdjustmentView])
def list_adjustments(
    objective_cycle_id: int,
    user_id: int | None = None,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """查看目标调整申请列表。员工看自己，上级/HR 看指定用户或全部"""
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")

    q = select(ObjectiveRevision).where(ObjectiveRevision.objective_cycle_id == objective_cycle_id)

    if user_id:
        target = session.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="用户不存在")
        is_superior = target.leader_userid == current.wecom_userid
        is_self = current.id == user_id
        is_admin = has_any_role(current, "hrbp", "super_admin", "dept_leader")
        if not (is_self or is_superior or is_admin):
            raise HTTPException(status_code=403, detail="无权查看")
        q = q.where(ObjectiveRevision.user_id == user_id)
    else:
        # 不传 user_id 时，HR/超管看全部；其余角色（含 Leader）只能看自己 scope 内的
        if not has_any_role(current, "hrbp", "super_admin"):
            from pms.services.scope import visible_user_ids
            visible = visible_user_ids(session, current)
            if visible is None:
                visible = {current.id} if current.id is not None else set()
            q = q.where(ObjectiveRevision.user_id.in_(visible))

    revisions = session.exec(q.order_by(ObjectiveRevision.created_at.desc())).all()
    return [
        AdjustmentView(
            id=r.id,
            objective_cycle_id=r.objective_cycle_id,
            user_id=r.user_id,
            reason=r.reason,
            old_objectives=r.old_objectives,
            new_objectives=r.new_objectives,
            status=r.status,
            requested_by_userid=r.requested_by_userid,
            reviewed_by=r.reviewed_by,
            reviewed_at=r.reviewed_at,
            reject_reason=r.reject_reason,
            created_at=r.created_at.isoformat(),
        )
        for r in revisions
    ]


@router.post("/adjustments/{revision_id}/approve")
def approve_adjustment(
    objective_cycle_id: int,
    revision_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """上级批准目标调整申请：用新目标覆盖旧目标"""
    revision = session.get(ObjectiveRevision, revision_id)
    if not revision or revision.objective_cycle_id != objective_cycle_id:
        raise HTTPException(status_code=404, detail="调整申请不存在")
    if revision.status != "pending":
        raise HTTPException(status_code=400, detail=f"当前状态为 {revision.status}，不能审批")

    target = session.get(User, revision.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not can_act_as_superior(current, target):
        raise HTTPException(status_code=403, detail="无权审批")

    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle or cycle.status != "active":
        raise HTTPException(status_code=400, detail="当前周期状态不允许审批")

    # 删除当前 objective 表中该用户该周期的所有目标
    old_objs = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id,
            Objective.user_id == revision.user_id,
        )
    ).all()
    for o in old_objs:
        session.delete(o)
    session.flush()

    # 写入新目标（status=approved）
    if revision.new_objectives:
        for i, item in enumerate(revision.new_objectives):
            session.add(Objective(
                objective_cycle_id=objective_cycle_id,
                user_id=revision.user_id,
                title=item.get("title", ""),
                description=item.get("description", ""),
                measure_criteria=item.get("measure_criteria", ""),
                weight=item.get("weight", 0),
                order_num=item.get("order_num", i),
                status="approved",
                reviewed_by=current.wecom_userid,
                reviewed_at=datetime.now(),
            ))

    revision.status = "approved"
    revision.reviewed_by = current.wecom_userid
    revision.reviewed_at = datetime.now(timezone.utc)
    session.add(revision)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="approve_adjustment",
        resource_type="objective_revision",
        resource_id=str(revision.id),
        after={"user_id": revision.user_id},
    )
    session.commit()
    return {"status": "approved"}


@router.post("/adjustments/{revision_id}/reject")
def reject_adjustment(
    objective_cycle_id: int,
    revision_id: int,
    payload: RejectPayload,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """上级驳回目标调整申请"""
    revision = session.get(ObjectiveRevision, revision_id)
    if not revision or revision.objective_cycle_id != objective_cycle_id:
        raise HTTPException(status_code=404, detail="调整申请不存在")
    if revision.status != "pending":
        raise HTTPException(status_code=400, detail=f"当前状态为 {revision.status}，不能审批")

    target = session.get(User, revision.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    is_superior = target.leader_userid == current.wecom_userid
    is_hr = has_any_role(current, "hrbp", "super_admin")
    if not (is_superior or is_hr):
        raise HTTPException(status_code=403, detail="无权审批")

    if not payload.reason or not payload.reason.strip():
        raise HTTPException(status_code=400, detail="驳回原因不能为空")

    revision.status = "rejected"
    revision.reviewed_by = current.wecom_userid
    revision.reviewed_at = datetime.now()
    revision.reject_reason = payload.reason.strip()
    session.add(revision)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="reject_adjustment",
        resource_type="objective_revision",
        resource_id=str(revision.id),
        after={"user_id": revision.user_id, "reason": payload.reason.strip()},
    )
    session.commit()
    return {"status": "rejected"}


# ============ 参与人状态同步 ============

def _ensure_participant(session: Session, objective_cycle_id: int, user_id: int) -> None:
    """确保某员工在目标周期的参与人列表中；不存在则自动创建。"""
    existing = session.exec(
        select(ObjectiveCycleParticipant).where(
            ObjectiveCycleParticipant.objective_cycle_id == objective_cycle_id,
            ObjectiveCycleParticipant.user_id == user_id,
        )
    ).first()
    if existing:
        return
    user = session.get(User, user_id)
    if not user:
        return
    dept = session.get(Department, user.department_id) if user.department_id else None
    session.add(ObjectiveCycleParticipant(
        objective_cycle_id=objective_cycle_id,
        user_id=user_id,
        leader_userid_snapshot=user.leader_userid,
        dept_name_snapshot=dept.name if dept else None,
        status="pending",
    ))


def _sync_participant_status(session: Session, objective_cycle_id: int, user_id: int) -> None:
    """根据该员工当前目标状态，同步 ObjectiveCycleParticipant.status。"""
    participant = session.exec(
        select(ObjectiveCycleParticipant).where(
            ObjectiveCycleParticipant.objective_cycle_id == objective_cycle_id,
            ObjectiveCycleParticipant.user_id == user_id,
        )
    ).first()
    if not participant:
        return

    objs = session.exec(
        select(Objective).where(
            Objective.objective_cycle_id == objective_cycle_id,
            Objective.user_id == user_id,
        )
    ).all()

    if not objs:
        participant.status = "pending"
    elif any(o.status == "pending_review" for o in objs):
        participant.status = "pending_review"
    elif all(o.status in ("approved", "locked") for o in objs):
        participant.status = "approved"
    else:
        participant.status = "pending"
    session.add(participant)
