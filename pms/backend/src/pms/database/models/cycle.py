from __future__ import annotations

# 绩效周期（项目）与参与人快照
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class PerformanceCycle(SQLModel, table=True):
    # 一个 cycle = 一次考核活动，如「2025H2 绩效考核」
    __tablename__ = "performance_cycle"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=128)
    start_date: date
    end_date: date
    # 状态机：draft -> in_progress -> published -> closed
    status: str = Field(default="draft", max_length=32, index=True)
    # 关联目标周期：本评估周期评估的是哪个目标周期
    objective_cycle_id: int | None = Field(
        default=None, foreign_key="objective_cycle.id", index=True, nullable=True
    )
    # 考核模式开关（PRD 3.2.1：可开关各环节）
    # 默认全开；关闭某环节后该环节自动跳过
    enable_self_eval: bool = Field(default=True)
    enable_peer_eval: bool = Field(default=True)
    enable_calibration: bool = Field(default=True)
    enable_feedback: bool = Field(default=True)
    # 时间线配置（JSON）
    stage_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    # 考核对象排除规则（PRD 3.2.2）
    exclusion_rules: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    # 创建人 wecom_userid
    created_by: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: datetime | None = None


class CycleParticipant(SQLModel, table=True):
    # 冻结快照：即使周期中途组织调整，也按这里记录的上级做审批链
    __tablename__ = "cycle_participant"
    __table_args__ = {"comment": "参与人维度进度跟踪"}

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # 快照字段 —— 防止组织调整影响历史归属
    leader_userid_snapshot: str | None = Field(default=None, max_length=64)
    dept_name_snapshot: str | None = Field(default=None, max_length=128)
    # 进度：pending / self_done / leader_done / published
    status: str = Field(default="pending", max_length=32, index=True)
    # 冗余存最终结果，便于发布后快速查询，也方便导出
    final_perf_score: float | None = None
    final_perf_level: str | None = Field(default=None, max_length=32)
    # 价值观三维度最终结果
    final_value_belief: str | None = Field(default=None, max_length=8)
    final_value_team: str | None = Field(default=None, max_length=8)
    final_value_growth: str | None = Field(default=None, max_length=8)
