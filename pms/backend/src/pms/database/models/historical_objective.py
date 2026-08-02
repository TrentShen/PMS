from __future__ import annotations

# 历史（线下）绩效目标留档（只读快照）
# 用于导入历史考核周期的目标明细，不参与当前绩效流程
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel


class HistoricalObjective(SQLModel, table=True):
    __tablename__ = "historical_objective"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    cycle_name: str = Field(max_length=128, index=True)
    title: str = Field(max_length=256)
    description: str | None = Field(default=None, sa_column=Column(Text))
    measure_criteria: str | None = Field(default=None, sa_column=Column(Text))
    weight: int = Field(default=0)
    order_num: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
