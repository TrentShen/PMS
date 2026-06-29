from __future__ import annotations

# 目标周期管理 API（HRBP / super_admin）
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models import ObjectiveCycle, ObjectiveCycleStatus, User
from pms.database.session import get_session
from pms.services.auth import get_current_user, require_role

router = APIRouter(prefix="/objective-cycles", tags=["objective-cycles"])


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

    cycle.status = ObjectiveCycleStatus.ACTIVE
    session.add(cycle)
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

    cycle.status = ObjectiveCycleStatus.COMPLETED
    cycle.completed_at = datetime.now(timezone.utc)
    session.add(cycle)
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

    session.delete(cycle)
    session.commit()
    return {"deleted": True}
