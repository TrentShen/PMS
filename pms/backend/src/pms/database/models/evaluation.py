# 评估记录：一条记录承载自评或上级评估
# 以 (cycle_id, user_id, eval_type) 唯一，重复提交时走 upsert
from datetime import datetime

from sqlmodel import Field, SQLModel, UniqueConstraint


class Evaluation(SQLModel, table=True):
    __tablename__ = "evaluation"
    __table_args__ = (
        UniqueConstraint("cycle_id", "user_id", "eval_type", name="uq_eval_unique"),
    )

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    # 被评人
    user_id: int = Field(foreign_key="user.id", index=True)
    # 评价人 wecom_userid（自评时 = user 自己的 wecom_userid）
    evaluator_userid: str = Field(max_length=64)
    # self / superior
    eval_type: str = Field(max_length=16, index=True)

    # 业绩 1-5 分，0.25 分段。用 float 存，提交时必须能被 0.25 整除
    perf_score: float | None = None
    # 由 perf_score 派生，存起来便于查询
    perf_level: str | None = Field(default=None, max_length=32)
    # 价值观三维度独立评级（信念/团队/成长），每个维度 jia/yi/bing
    value_belief_grade: str | None = Field(default=None, max_length=8)
    value_belief_example: str | None = None
    value_team_grade: str | None = Field(default=None, max_length=8)
    value_team_example: str | None = None
    value_growth_grade: str | None = Field(default=None, max_length=8)
    value_growth_example: str | None = None
    # 关键成果（PRD 3.4.1：自评与上级评必填）
    key_results: str | None = None
    # 综合评语
    comment: str | None = None

    submitted_at: datetime | None = None
    # draft / submitted
    status: str = Field(default="draft", max_length=16, index=True)
