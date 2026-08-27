from __future__ import annotations

# 目标周期管理 API（HRBP / super_admin）
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models import ObjectiveCycle, ObjectiveCycleParticipant, ObjectiveCycleStatus, User
from pms.database.models.objective import Objective
from pms.database.models.objective_revision import ObjectiveRevision
from pms.database.models.user import Department
from pms.database.session import get_session
from pms.services.auth import is_fte, require_role
from pms.utils.audit import write_audit

router = APIRouter(prefix="/objective-cycles", tags=["objective-cycles"])


# ============ 请求/响应 Schema ============

class ObjectiveCycleCreate(BaseModel):
    name: str
    start_date: date
    end_date: date


class ObjectiveCycleUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ObjectiveCycleView(ObjectiveCycleCreate):
    id: int
    status: str
    created_by: str
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class ParticipantAdd(BaseModel):
    user_ids: list[int]


class ParticipantDetail(BaseModel):
    id: int
    objective_cycle_id: int
    user_id: int
    user_name: str
    user_position: str | None
    leader_userid_snapshot: str | None
    dept_name_snapshot: str | None
    status: str


class ObjectiveStatusSummary(BaseModel):
    total: int
    pending: int
    pending_review: int
    approved: int


# ============ 目标周期 CRUD ============

@router.get("", response_model=list[ObjectiveCycleView])
def list_objective_cycles(
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> list[ObjectiveCycleView]:
    cycles = session.exec(select(ObjectiveCycle).order_by(ObjectiveCycle.start_date.desc())).all()
    return [ObjectiveCycleView.model_validate(c, from_attributes=True) for c in cycles]


@router.post("", response_model=ObjectiveCycleView)
def create_objective_cycle(
    payload: ObjectiveCycleCreate,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> ObjectiveCycleView:
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    cycle = ObjectiveCycle(
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=ObjectiveCycleStatus.DRAFT,
        created_by=current.wecom_userid,
    )
    session.add(cycle)
    session.commit()
    session.refresh(cycle)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="create_objective_cycle",
        resource_type="objective_cycle",
        resource_id=str(cycle.id),
        after={"name": cycle.name, "status": cycle.status},
    )
    session.commit()
    return ObjectiveCycleView.model_validate(cycle, from_attributes=True)


@router.get("/{objective_cycle_id}", response_model=ObjectiveCycleView)
def get_objective_cycle(
    objective_cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> ObjectiveCycleView:
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")
    return ObjectiveCycleView.model_validate(cycle, from_attributes=True)


@router.put("/{objective_cycle_id}", response_model=ObjectiveCycleView)
def update_objective_cycle(
    objective_cycle_id: int,
    payload: ObjectiveCycleUpdate,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> ObjectiveCycleView:
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")
    if cycle.status != ObjectiveCycleStatus.DRAFT:
        raise HTTPException(status_code=400, detail="仅 draft 状态的目标周期可编辑")

    if payload.name is not None:
        cycle.name = payload.name
    if payload.start_date is not None:
        cycle.start_date = payload.start_date
    if payload.end_date is not None:
        cycle.end_date = payload.end_date

    if cycle.start_date > cycle.end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    session.add(cycle)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="update_objective_cycle",
        resource_type="objective_cycle",
        resource_id=str(cycle.id),
        # mode="json"：date 等类型转成可 JSON 序列化的值，否则审计写入会 TypeError
        after={k: v for k, v in payload.model_dump(mode="json").items() if v is not None},
    )
    session.commit()
    session.refresh(cycle)
    return ObjectiveCycleView.model_validate(cycle, from_attributes=True)


@router.post("/{objective_cycle_id}/start", response_model=ObjectiveCycleView)
def start_objective_cycle(
    objective_cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> ObjectiveCycleView:
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")
    if cycle.status != ObjectiveCycleStatus.DRAFT:
        raise HTTPException(status_code=400, detail="仅 draft 状态可启动")

    before = {"status": cycle.status}
    cycle.status = ObjectiveCycleStatus.ACTIVE
    session.add(cycle)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="start_objective_cycle",
        resource_type="objective_cycle",
        resource_id=str(cycle.id),
        before=before,
        after={"status": cycle.status},
    )
    session.commit()
    session.refresh(cycle)
    return ObjectiveCycleView.model_validate(cycle, from_attributes=True)


@router.post("/{objective_cycle_id}/complete", response_model=ObjectiveCycleView)
def complete_objective_cycle(
    objective_cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> ObjectiveCycleView:
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")
    if cycle.status != ObjectiveCycleStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="仅 active 状态可完成")

    before = {"status": cycle.status}
    cycle.status = ObjectiveCycleStatus.COMPLETED
    cycle.completed_at = datetime.now(timezone.utc)
    session.add(cycle)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="complete_objective_cycle",
        resource_type="objective_cycle",
        resource_id=str(cycle.id),
        before=before,
        after={"status": cycle.status},
    )
    session.commit()
    session.refresh(cycle)
    return ObjectiveCycleView.model_validate(cycle, from_attributes=True)


@router.delete("/{objective_cycle_id}")
def delete_objective_cycle(
    objective_cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> dict:
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")
    if cycle.status != ObjectiveCycleStatus.DRAFT:
        raise HTTPException(status_code=400, detail="仅 draft 状态可删除")

    # 删除前记录关键数量，便于审计追溯
    objective_count = len(session.exec(
        select(Objective).where(Objective.objective_cycle_id == objective_cycle_id)
    ).all())
    revision_count = len(session.exec(
        select(ObjectiveRevision).where(ObjectiveRevision.objective_cycle_id == objective_cycle_id)
    ).all())

    # 级联删除该周期下的参与人、目标、调整申请
    for model in (ObjectiveCycleParticipant, Objective, ObjectiveRevision):
        for row in session.exec(
            select(model).where(
                model.objective_cycle_id == objective_cycle_id
            )
        ).all():
            session.delete(row)

    session.delete(cycle)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="delete_objective_cycle",
        resource_type="objective_cycle",
        resource_id=str(objective_cycle_id),
        before={
            "name": cycle.name,
            "status": cycle.status,
            "objective_count": objective_count,
            "revision_count": revision_count,
        },
    )
    session.commit()
    return {"deleted": True}


# ============ 参与人管理 ============

@router.get("/{objective_cycle_id}/participants")
def list_participants(
    objective_cycle_id: int,
    page: int = 1,
    page_size: int = 50,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
):
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")

    rows = session.exec(
        select(ObjectiveCycleParticipant, User)
        .join(User, User.id == ObjectiveCycleParticipant.user_id)
        .where(ObjectiveCycleParticipant.objective_cycle_id == objective_cycle_id)
    ).all()

    total = len(rows)
    start = (page - 1) * page_size
    paged = rows[start:start + page_size]

    items = [
        ParticipantDetail(
            id=p.id,
            objective_cycle_id=p.objective_cycle_id,
            user_id=p.user_id,
            user_name=u.name,
            user_position=u.position,
            leader_userid_snapshot=p.leader_userid_snapshot,
            dept_name_snapshot=p.dept_name_snapshot,
            status=p.status,
        )
        for p, u in paged
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{objective_cycle_id}/participants", response_model=list[ParticipantDetail])
def add_participants(
    objective_cycle_id: int,
    payload: ParticipantAdd,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> list[ParticipantDetail]:
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")
    if cycle.status != ObjectiveCycleStatus.DRAFT:
        raise HTTPException(status_code=400, detail="仅在 draft 状态可添加参与人")

    # 与绩效周期 add_participants 对齐：受限 HRBP 只能添加自己管辖范围内的员工
    if current.role == "hrbp" and current.hrbp_scope_dept_ids:
        from pms.services.scope import visible_user_ids

        scope = visible_user_ids(session, current)
        if scope is not None:
            outside = [uid for uid in payload.user_ids if uid not in scope]
            if outside:
                raise HTTPException(
                    status_code=403,
                    detail=f"以下用户超出你的管辖范围，无法添加：{outside}",
                )

    existing_ids = {
        p.user_id
        for p in session.exec(
            select(ObjectiveCycleParticipant).where(
                ObjectiveCycleParticipant.objective_cycle_id == objective_cycle_id
            )
        ).all()
    }

    added: list[ObjectiveCycleParticipant] = []
    for uid in payload.user_ids:
        if uid in existing_ids:
            continue
        user = session.get(User, uid)
        if not user:
            continue
        if not is_fte(user):
            continue
        dept = session.get(Department, user.department_id) if user.department_id else None
        cp = ObjectiveCycleParticipant(
            objective_cycle_id=objective_cycle_id,
            user_id=uid,
            leader_userid_snapshot=user.leader_userid,
            dept_name_snapshot=dept.name if dept else None,
            status="pending",
        )
        session.add(cp)
        added.append(cp)

    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="add_objective_participants",
        resource_type="objective_cycle",
        resource_id=str(objective_cycle_id),
        after={"added_user_ids": payload.user_ids},
    )
    session.commit()

    return [
        ParticipantDetail(
            id=p.id,
            objective_cycle_id=p.objective_cycle_id,
            user_id=p.user_id,
            user_name=u.name,
            user_position=u.position,
            leader_userid_snapshot=p.leader_userid_snapshot,
            dept_name_snapshot=p.dept_name_snapshot,
            status=p.status,
        )
        for p, u in ((p, session.get(User, p.user_id)) for p in added)
        if u
    ]


@router.delete("/{objective_cycle_id}/participants/{participant_id}")
def remove_participant(
    objective_cycle_id: int,
    participant_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
):
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")
    if cycle.status != ObjectiveCycleStatus.DRAFT:
        raise HTTPException(status_code=400, detail="仅在 draft 状态可移除参与人")

    participant = session.get(ObjectiveCycleParticipant, participant_id)
    if not participant or participant.objective_cycle_id != objective_cycle_id:
        raise HTTPException(status_code=404, detail="参与人不存在")

    session.delete(participant)
    write_audit(
        session,
        operator_userid=current.wecom_userid,
        operator_name=current.name,
        action="remove_objective_participant",
        resource_type="objective_cycle",
        resource_id=str(objective_cycle_id),
        before={"participant_id": participant_id, "user_id": participant.user_id, "status": participant.status},
    )
    session.commit()
    return {"deleted": True}


# ============ 目标状态汇总 ============

@router.get("/{objective_cycle_id}/objective-status-summary")
def objective_status_summary(
    objective_cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(require_role("hrbp", "super_admin")),
) -> ObjectiveStatusSummary:
    cycle = session.get(ObjectiveCycle, objective_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="目标周期不存在")

    participants = session.exec(
        select(ObjectiveCycleParticipant).where(
            ObjectiveCycleParticipant.objective_cycle_id == objective_cycle_id
        )
    ).all()

    total = len(participants)
    pending = 0
    pending_review = 0
    approved = 0

    # 批量加载本周期所有目标，避免循环内逐人查询（N+1）
    all_objs = session.exec(
        select(Objective).where(Objective.objective_cycle_id == objective_cycle_id)
    ).all()
    objs_by_user: dict[int, list[Objective]] = {}
    for o in all_objs:
        objs_by_user.setdefault(o.user_id, []).append(o)

    for p in participants:
        # 以该员工最新目标状态作为进度
        objs = objs_by_user.get(p.user_id, [])
        if not objs:
            pending += 1
        elif any(o.status == "pending_review" for o in objs):
            pending_review += 1
        elif all(o.status in ("approved", "locked") for o in objs):
            approved += 1
        else:
            pending += 1

    return ObjectiveStatusSummary(
        total=total,
        pending=pending,
        pending_review=pending_review,
        approved=approved,
    )
