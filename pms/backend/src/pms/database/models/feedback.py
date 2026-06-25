from __future__ import annotations

# 绩效反馈面谈记录（PRD 3.4.8）
# 流程：上级填写面谈记录 → 员工查看 → 员工点击"确认收到"或"有异议"
from datetime import datetime, timezone

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel, UniqueConstraint


class FeedbackRecord(SQLModel, table=True):
    # 每个周期每位员工最多一条面谈记录（由直属上级创建）
    __tablename__ = "feedback_record"
    __table_args__ = (
        UniqueConstraint("cycle_id", "user_id", name="uq_feedback_per_user_cycle"),
    )

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    # 被面谈员工
    user_id: int = Field(foreign_key="user.id", index=True)
    # 面谈人（通常为直属上级）的 wecom_userid
    interviewer_userid: str = Field(max_length=64)
    interviewer_name: str = Field(max_length=64)
    # 面谈内容
    strengths: str = Field(default="", sa_column=Column(Text))       # 员工优势
    improvements: str = Field(default="", sa_column=Column(Text))    # 待改进项
    next_goals: str = Field(default="", sa_column=Column(Text))      # 下阶段目标/期望
    # 员工确认状态：pending / confirmed / disputed
    confirm_status: str = Field(default="pending", max_length=16, index=True)
    # 员工异议内容（confirm_status=disputed 时填写）
    dispute_comment: str | None = Field(default=None, sa_column=Column(Text))
    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: datetime | None = None
