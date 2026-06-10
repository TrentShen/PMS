from __future__ import annotations

# 绩效目标 CRUD（员工手动录入 + HR 代录）
# PRD 3.3：目标 3-5 条，权重总和 100
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.objective import Objective
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user

router = APIRouter(prefix="/cycles/{cycle_id}/objectives", tags=["objectives"])


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


# ============ 查：我的目标 ============

@router.get("", response_model=list[ObjectiveView])
def list_my_objectives(
    cycle_id: int,
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
            Objective.cycle_id == cycle_id, Objective.user_id == target_id
        ).order_by(Objective.order_num)
    ).all()
    return [ObjectiveView.model_validate(o, from_attributes=True) for o in objs]


# ============ 写：批量保存目标（覆盖式）============

@router.put("")
def save_objectives(
    cycle_id: int,
    payload: ObjectiveBatchSave,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    # 员工只能改自己的；周期必须在 in_progress 或 draft
    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle or cycle.status not in ("draft", "in_progress"):
        raise HTTPException(status_code=400, detail="当前周期状态不允许修改目标")

    # 必须是参与人
    participant = session.exec(
        select(CycleParticipant).where(
            CycleParticipant.cycle_id == cycle_id,
            CycleParticipant.user_id == current.id,
        )
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="你不在本周期的参与人列表中")

    # 已提交自评后不能再改目标
    if participant.status != "pending":
        raise HTTPException(status_code=400, detail="自评已提交，不能再修改目标")

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

    # 删旧 + 写新（覆盖式）
    old = session.exec(
        select(Objective).where(
            Objective.cycle_id == cycle_id, Objective.user_id == current.id
        )
    ).all()
    for o in old:
        session.delete(o)
    session.flush()

    for i, item in enumerate(payload.items):
        session.add(Objective(
            cycle_id=cycle_id,
            user_id=current.id,
            title=item.title.strip(),
            description=item.description.strip(),
            measure_criteria=item.measure_criteria.strip(),
            weight=item.weight,
            order_num=i,
        ))

    session.commit()
    return {"saved": len(payload.items)}
