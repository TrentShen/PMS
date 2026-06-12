from __future__ import annotations

# 目标中途调整记录（PRD 3.3.3）
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ObjectiveRevision(SQLModel, table=True):
    __tablename__ = "objective_revision"

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # 调整原因
    reason: str
    # 调整前的目标快照
    old_objectives: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    # 调整后的目标
    new_objectives: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    # 审批状态
    status: str = Field(default="pending", max_length=16)  # pending / approved / rejected
    requested_by_userid: str = Field(max_length=64)
    reviewed_by: str | None = Field(default=None, max_length=64)
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
