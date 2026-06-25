from __future__ import annotations

# 试用期管理模型
# 独立于绩效周期，与 User.hired_at / probation / employee_status 联动
from datetime import date, datetime, timezone

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class ProbationPlan(SQLModel, table=True):
    __tablename__ = "probation_plan"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    # 试用期起止日期；默认从 User.hired_at + probation 推导
    start_date: date
    end_date: date
    probation_months: int | None = Field(default=None, description="试用期月数，冗余存储")

    # 计划生命周期状态
    status: str = Field(default="draft", max_length=32)

    # 目标审批信息
    objective_submitted_at: datetime | None = None
    objective_reviewed_by: str | None = Field(default=None, max_length=64)
    objective_reviewed_at: datetime | None = None

    # 评估信息（轻量，合并到主表；仅支持一次上级评估）
    evaluation_comment: str | None = Field(default=None, sa_column=Column(Text))
    evaluation_result: str | None = Field(default=None, max_length=32)
    evaluator_userid: str | None = Field(default=None, max_length=64)
    evaluated_at: datetime | None = None

    # 计划变更记录（HR 延期等）
    extended_by: str | None = Field(default=None, max_length=64)
    extended_at: datetime | None = None
    extension_note: str | None = Field(default=None, sa_column=Column(Text))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProbationObjective(SQLModel, table=True):
    __tablename__ = "probation_objective"

    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="probation_plan.id", index=True)

    title: str = Field(max_length=256)
    description: str | None = Field(default=None, sa_column=Column(Text))
    measure_criteria: str | None = Field(default=None, sa_column=Column(Text))
    order_num: int = Field(default=0)

    # 目标状态：draft → pending_review → approved → locked
    status: str = Field(default="draft", max_length=32)
    reviewed_by: str | None = Field(default=None, max_length=64)
    reviewed_at: datetime | None = None
    reject_reason: str | None = Field(default=None, sa_column=Column(Text))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
