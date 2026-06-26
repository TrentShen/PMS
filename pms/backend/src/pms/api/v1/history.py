from __future__ import annotations

# 历史绩效查询 — 管理视角（PRD 3.6.1）
# Leader/HR 按部门查看下属历史绩效分布和趋势
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, has_any_role, require_fte
from pms.services.scope import visible_user_ids

router = APIRouter(
    prefix="/history",
    tags=["history"],
    dependencies=[Depends(require_fte)],
)


@router.get("/subordinates")
def subordinate_history(
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """上级/HR 查看自己管辖范围内的员工所有已发布周期的绩效结果"""
    if not has_any_role(current, "hrbp", "super_admin", "dept_leader", "direct_leader"):
        raise HTTPException(status_code=403, detail="无权限")

    scope = visible_user_ids(session, current)

    # 拉所有已发布的周期
    published = session.exec(
        select(PerformanceCycle).where(PerformanceCycle.status == "published")
        .order_by(PerformanceCycle.start_date.desc())
    ).all()

    result = []
    for cycle in published:
        q = select(CycleParticipant, User).join(
            User, User.id == CycleParticipant.user_id
        ).where(
            CycleParticipant.cycle_id == cycle.id,
            CycleParticipant.status == "published",
        )
        if scope is not None:
            q = q.where(CycleParticipant.user_id.in_(scope))

        rows = session.exec(q).all()
        participants = [
            {
                "user_id": u.id,
                "user_name": u.name,
                "position": u.position,
                "department_id": u.department_id,
                "perf_score": p.final_perf_score,
                "perf_level": p.final_perf_level,
                "value_belief": p.final_value_belief,
                "value_team": p.final_value_team,
                "value_growth": p.final_value_growth,
            }
            for p, u in rows
        ]
        if participants:
            result.append({
                "cycle_id": cycle.id,
                "cycle_name": cycle.name,
                "start_date": cycle.start_date.isoformat(),
                "end_date": cycle.end_date.isoformat(),
                "participants": participants,
            })
    return result


@router.get("/user/{user_id}")
def user_history(
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """查看某位员工的历史绩效趋势（多周期）"""
    from pms.services.scope import ensure_can_view_user
    ensure_can_view_user(session, current, user_id)

    target = session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")

    records = session.exec(
        select(CycleParticipant, PerformanceCycle)
        .join(PerformanceCycle, PerformanceCycle.id == CycleParticipant.cycle_id)
        .where(
            CycleParticipant.user_id == user_id,
            CycleParticipant.status == "published",
        )
        .order_by(PerformanceCycle.start_date)
    ).all()

    return {
        "user": {"id": target.id, "name": target.name, "position": target.position},
        "history": [
            {
                "cycle_id": c.id,
                "cycle_name": c.name,
                "start_date": c.start_date.isoformat(),
                "end_date": c.end_date.isoformat(),
                "perf_score": p.final_perf_score,
                "perf_level": p.final_perf_level,
                "value_belief": p.final_value_belief,
                "value_team": p.final_value_team,
                "value_growth": p.final_value_growth,
            }
            for p, c in records
        ],
    }
