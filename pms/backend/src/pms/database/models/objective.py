from __future__ import annotations

# 绩效目标：每位员工在每个周期下有一组（3-5 条）目标
from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class Objective(SQLModel, table=True):
    __tablename__ = "objective"

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(max_length=256)
    # description / measure_criteria 可能较长，显式用 TEXT
    description: str = Field(default="", sa_column=Column(Text))
    measure_criteria: str = Field(default="", sa_column=Column(Text))
    # 权重：百分比，同一人所有目标权重之和应为 100（前端+后端双校验）
    weight: int = Field(default=0)
    order_num: int = Field(default=0)
