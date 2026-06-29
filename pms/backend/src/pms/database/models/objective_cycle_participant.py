from __future__ import annotations

# 目标周期参与人
# HR 在目标周期中添加参与人后，员工才能在该周期下填写/提交目标
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class ObjectiveCycleParticipant(SQLModel, table=True):
    __tablename__ = "objective_cycle_participant"

    id: int | None = Field(default=None, primary_key=True)
    objective_cycle_id: int = Field(foreign_key="objective_cycle.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # 快照字段 —— 防止组织调整影响历史归属
    leader_userid_snapshot: str | None = Field(default=None, max_length=64)
    dept_name_snapshot: str | None = Field(default=None, max_length=128)
    # 目标制定进度：pending（未提交） / pending_review（待审批） / approved（已确认）
    status: str = Field(default="pending", max_length=32, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
