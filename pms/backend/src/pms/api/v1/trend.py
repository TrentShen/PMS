from __future__ import annotations

# 绩效趋势分析（个人/部门）
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.historical_performance import HistoricalPerformanceResult
from pms.database.models.user import Department, User
from pms.database.session import get_session
from pms.services.auth import get_current_user, has_any_role, require_role

router = APIRouter(prefix="/trend", tags=["trend"])


class TrendPoint(BaseModel):
    cycle_name: str
    perf_score: float | None
    perf_level: str | None
    value_belief: str | None
    value_team: str | None
    value_growth: str | None
    source: str  # current | historical


class DepartmentTrendPoint(BaseModel):
    cycle_name: str
    department_name: str
    avg_score: float
    participant_count: int


@router.get("/users/{user_id}", response_model=list[TrendPoint])
def get_user_trend(
    user_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """个人绩效趋势：当前系统已发布周期 + 导入的历史数据。"""
    from pms.services.scope import ensure_can_view_user

    ensure_can_view_user(session, current, user_id)

    # 当前系统已发布周期
    current_rows = session.exec(
        select(CycleParticipant, PerformanceCycle)
        .join(PerformanceCycle, PerformanceCycle.id == CycleParticipant.cycle_id)
        .where(
            CycleParticipant.user_id == user_id,
            PerformanceCycle.status == "published",
        )
        .order_by(PerformanceCycle.end_date.asc())
    ).all()

    # 导入的历史数据
    historical_rows = session.exec(
        select(HistoricalPerformanceResult).where(
            HistoricalPerformanceResult.user_id == user_id,
        ).order_by(HistoricalPerformanceResult.cycle_name.asc())
    ).all()

    result: list[TrendPoint] = []
    for cp, cycle in current_rows:
        result.append(
            TrendPoint(
                cycle_name=cycle.name,
                perf_score=cp.final_perf_score,
                perf_level=cp.final_perf_level,
                value_belief=cp.final_value_belief,
                value_team=cp.final_value_team,
                value_growth=cp.final_value_growth,
                source="current",
            )
        )
    for h in historical_rows:
        result.append(
            TrendPoint(
                cycle_name=h.cycle_name,
                perf_score=h.perf_score,
                perf_level=h.perf_level,
                value_belief=h.value_belief,
                value_team=h.value_team,
                value_growth=h.value_growth,
                source="historical",
            )
        )
    return result


@router.get("/departments", response_model=list[DepartmentTrendPoint])
def get_department_trend(
    session: Session = Depends(get_session),
    hr: User = Depends(require_role("hrbp", "super_admin")),
):
    """部门绩效趋势：各部门在每个已发布周期的平均分。"""
    rows = session.exec(
        select(CycleParticipant, PerformanceCycle, User, Department)
        .join(PerformanceCycle, PerformanceCycle.id == CycleParticipant.cycle_id)
        .join(User, User.id == CycleParticipant.user_id)
        .join(Department, Department.id == User.department_id, isouter=True)
        .where(PerformanceCycle.status == "published")
        .order_by(PerformanceCycle.end_date.asc(), Department.id.asc())
    ).all()

    grouped: dict[tuple[str, str], dict] = {}
    for cp, cycle, user, dept in rows:
        dept_name = dept.name if dept else "未分配部门"
        key = (cycle.name, dept_name)
        if key not in grouped:
            grouped[key] = {"scores": [], "count": 0}
        if cp.final_perf_score is not None:
            grouped[key]["scores"].append(cp.final_perf_score)
        grouped[key]["count"] += 1

    result: list[DepartmentTrendPoint] = []
    for (cycle_name, dept_name), data in grouped.items():
        scores = data["scores"]
        if not scores:
            continue
        result.append(
            DepartmentTrendPoint(
                cycle_name=cycle_name,
                department_name=dept_name,
                avg_score=round(sum(scores) / len(scores), 2),
                participant_count=data["count"],
            )
        )
    return result
