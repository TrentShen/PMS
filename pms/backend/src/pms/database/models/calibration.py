# 绩效校准 + 公司级审批（PRD 3.4.7）
# 校准流程：上级初评 → 部门 Leader 校准（可改分）→ HR 审批 → CEO 审批 → 结果锁定
# 驳回时退回到部门 Leader 重新校准
from datetime import datetime
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class CalibrationRecord(SQLModel, table=True):
    # 每次校准修改留痕（PRD 要求"所有修改记录完整留痕"）
    __tablename__ = "calibration_record"

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    # 被校准员工
    user_id: int = Field(foreign_key="user.id", index=True)
    # 谁改的
    operator_userid: str = Field(max_length=64)
    operator_name: str = Field(max_length=64)
    # 修改内容
    field_changed: str = Field(max_length=32)  # perf_score / value_grade
    old_value: str = Field(max_length=64)
    new_value: str = Field(max_length=64)
    reason: str = Field(max_length=512)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class CycleApproval(SQLModel, table=True):
    # 公司级审批链：HR → CEO 串行
    # 一个周期有一条 approval 记录追踪整体审批状态
    __tablename__ = "cycle_approval"

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", unique=True, index=True)
    # 审批链状态：
    #   calibrating    — 部门 Leader 正在校准
    #   pending_hr     — 等待 HR 审批
    #   pending_ceo    — HR 已批，等 CEO 审批
    #   approved       — CEO 批准，可以发布
    #   rejected_by_hr — HR 驳回，退回校准
    #   rejected_by_ceo — CEO 驳回，退回校准
    status: str = Field(default="calibrating", max_length=32, index=True)
    # 审批人信息
    hr_approver_userid: str | None = Field(default=None, max_length=64)
    hr_approved_at: datetime | None = None
    hr_comment: str | None = Field(default=None, max_length=512)
    ceo_approver_userid: str | None = Field(default=None, max_length=64)
    ceo_approved_at: datetime | None = None
    ceo_comment: str | None = Field(default=None, max_length=512)
    # 驳回信息（最近一次）
    reject_reason: str | None = Field(default=None, max_length=512)
    rejected_by: str | None = Field(default=None, max_length=64)
    rejected_at: datetime | None = None
    # 时间戳
    submitted_at: datetime | None = None  # Leader 提交校准的时间
    created_at: datetime = Field(default_factory=datetime.utcnow)
