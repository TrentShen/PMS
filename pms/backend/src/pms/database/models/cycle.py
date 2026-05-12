# 绩效周期（项目）与参与人快照
from datetime import date, datetime

from sqlmodel import Field, SQLModel


class PerformanceCycle(SQLModel, table=True):
    # 一个 cycle = 一次考核活动，如「2025H2 绩效考核」
    __tablename__ = "performance_cycle"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=128)
    start_date: date
    end_date: date
    # V0.9 状态机：draft -> in_progress -> published -> closed
    status: str = Field(default="draft", max_length=32, index=True)
    # 创建人 wecom_userid
    created_by: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=datetime.utcnow)
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
    final_value_grade: str | None = Field(default=None, max_length=8)
