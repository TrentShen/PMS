from __future__ import annotations

# 历史绩效结果（只读快照）
# 用于导入历史考核结果，不参与当前绩效流程
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class HistoricalPerformanceResult(SQLModel, table=True):
    __tablename__ = "historical_performance_result"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    cycle_name: str = Field(max_length=128, index=True)
    perf_score: float | None = None
    perf_level: str | None = Field(default=None, max_length=32)
    value_belief: str | None = Field(default=None, max_length=32)
    value_team: str | None = Field(default=None, max_length=32)
    value_growth: str | None = Field(default=None, max_length=32)
    comment: str | None = None
    imported_by: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
