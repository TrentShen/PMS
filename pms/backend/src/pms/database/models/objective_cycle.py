from __future__ import annotations

# 目标周期：与绩效评估周期解耦，独立管理目标制定/生效/结束
from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


class ObjectiveCycle(SQLModel, table=True):
    __tablename__ = "objective_cycle"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=128)
    start_date: date
    end_date: date
    # 状态机：draft -> active -> completed
    status: str = Field(default="draft", max_length=32, index=True)
    created_by: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
