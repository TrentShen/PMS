from __future__ import annotations

# 绩效目标：每位员工在每个目标周期下有一组（3-5 条）目标
from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class Objective(SQLModel, table=True):
    __tablename__ = "objective"

    id: int | None = Field(default=None, primary_key=True)
    objective_cycle_id: int = Field(foreign_key="objective_cycle.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(max_length=256)
    # description / measure_criteria 可能较长，显式用 TEXT
    description: str = Field(default="", sa_column=Column(Text))
    measure_criteria: str = Field(default="", sa_column=Column(Text))
    # 权重：百分比，同一人所有目标权重之和应为 100（前端+后端双校验）
    weight: int = Field(default=0)
    order_num: int = Field(default=0)
    # 目标状态：draft → pending_review → approved → locked
    status: str = Field(default="draft", max_length=16)
    # 审批信息
    reviewed_by: str | None = Field(default=None, max_length=64)
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
