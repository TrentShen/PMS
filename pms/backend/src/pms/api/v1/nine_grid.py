from __future__ import annotations

# 九宫格人才盘点（PRD 3.6.2）：绩效（横轴 A/B/C 档）× 潜力（纵轴 高/中/低）
# 绩效档取周期参与人的 final_perf_level；潜力取员工档案 User.potential_level（HR 评定）
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from pms.database.models.cycle import CycleParticipant, PerformanceCycle
from pms.database.models.enums import PerfLevel
from pms.database.models.user import User
from pms.database.session import get_session
from pms.services.auth import get_current_user, has_any_role, require_fte
from pms.services.scope import visible_user_ids

router = APIRouter(prefix="/cycles", tags=["nine-grid"], dependencies=[Depends(require_fte)])

POTENTIAL_LEVELS = ("high", "medium", "low")
# 与校准分布同口径：A = 优秀+部分超出，B = 符合预期，C = 部分不符+不符合
PERF_BANDS = {
    "A": {PerfLevel.EXCELLENT.value, PerfLevel.EXCEED_PART.value},
    "B": {PerfLevel.MEET.value},
    "C": {PerfLevel.BELOW_PART.value, PerfLevel.BELOW.value},
}


class NineGridMember(BaseModel):
    user_id: int
    name: str
    position: str | None
    dept_name: str | None
    final_perf_score: float | None
    final_perf_level: str | None
    potential_level: str | None


class NineGridCell(BaseModel):
    perf_band: str  # A / B / C
    potential: str  # high / medium / low
    members: list[NineGridMember]


def _perf_band(level: str | None) -> str | None:
    for band, levels in PERF_BANDS.items():
        if level in levels:
            return band
    return None


@router.get("/{cycle_id}/nine-grid")
def nine_grid(
    cycle_id: int,
    session: Session = Depends(get_session),
    current: User = Depends(get_current_user),
):
    """返回某周期的九宫格数据。权限与校准视图一致：dept_leader/HR，按可见范围裁剪。"""
    if not has_any_role(current, "dept_leader", "hrbp", "super_admin"):
        raise HTTPException(status_code=403, detail="无权限")

    cycle = session.get(PerformanceCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="周期不存在")

    q = (
        select(CycleParticipant, User)
        .join(User, User.id == CycleParticipant.user_id)
        .where(CycleParticipant.cycle_id == cycle_id)
    )
    scope = visible_user_ids(session, current)
    if scope is not None:
        q = q.where(CycleParticipant.user_id.in_(scope))
    rows = session.exec(q).all()

    cells: dict[tuple[str, str], list[NineGridMember]] = {}
    unrated: list[NineGridMember] = []  # 已定级但潜力未评定
    unset_count = 0  # 未定绩效等级

    for p, u in rows:
        band = _perf_band(p.final_perf_level)
        if band is None:
            unset_count += 1
            continue
        member = NineGridMember(
            user_id=u.id,
            name=u.name,
            position=u.position,
            dept_name=p.dept_name_snapshot,
            final_perf_score=p.final_perf_score,
            final_perf_level=p.final_perf_level,
            potential_level=u.potential_level,
        )
        if u.potential_level in POTENTIAL_LEVELS:
            cells.setdefault((band, u.potential_level), []).append(member)
        else:
            unrated.append(member)

    # 9 格全部返回（空格也给空列表），前端直接渲染
    return {
        "cycle_id": cycle.id,
        "cycle_name": cycle.name,
        "cycle_status": cycle.status,
        "cells": [
            NineGridCell(perf_band=band, potential=potential, members=cells.get((band, potential), []))
            for potential in POTENTIAL_LEVELS
            for band in ("A", "B", "C")
        ],
        "unrated_potential": unrated,
        "unset_count": unset_count,
    }
