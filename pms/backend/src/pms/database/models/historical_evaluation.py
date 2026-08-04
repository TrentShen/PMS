from __future__ import annotations

# 历史绩效敏感数据（只读快照）
# 存线下 Excel 导入的历史考核汇总与明细（含互评评语），不参与当前绩效流程
# 数据高度敏感：仅 HR（hrbp/super_admin）与员工直属上级可见
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class HistoricalEvaluationSummary(SQLModel, table=True):
    __tablename__ = "historical_evaluation_summary"
    __table_args__ = (
        UniqueConstraint("user_id", "cycle_name", name="uq_historical_eval_summary_user_cycle"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    cycle_name: str = Field(max_length=128, index=True)
    # 上级评估
    superior_score: float | None = None
    superior_level: str | None = Field(default=None, max_length=32)
    superior_value_grade: str | None = Field(default=None, max_length=32)
    # 互评汇总
    peer_avg_score: float | None = None
    peer_level: str | None = Field(default=None, max_length=32)
    peer_value_grade: str | None = Field(default=None, max_length=32)
    # 自评
    self_score: float | None = None
    self_level: str | None = Field(default=None, max_length=32)
    self_value_grade: str | None = Field(default=None, max_length=32)
    # 校准
    is_calibrated: bool = Field(default=False)
    calibration_suggestion: str | None = Field(default=None, sa_column=Column(Text))
    calibrated_score: float | None = None
    calibrated_result: str | None = Field(default=None, max_length=64)
    comment: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )


class HistoricalEvaluationDetail(SQLModel, table=True):
    __tablename__ = "historical_evaluation_detail"
    __table_args__ = (
        UniqueConstraint("user_id", "cycle_name", name="uq_historical_eval_detail_user_cycle"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    cycle_name: str = Field(max_length=128, index=True)
    # 自评明细
    self_score: float | None = None
    self_value_grade: str | None = Field(default=None, max_length=32)
    self_output: str | None = Field(default=None, sa_column=Column(Text))   # 自评产出
    self_comment: str | None = Field(default=None, sa_column=Column(Text))  # 自评整体评价
    # 上级评估明细
    superior_score: float | None = None
    superior_value_grade: str | None = Field(default=None, max_length=32)
    superior_comment: str | None = Field(default=None, sa_column=Column(Text))
    # 互评明细：JSON 数组 [{index, score, comment}]，最多 5 条，只存非空条目
    peers_json: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
