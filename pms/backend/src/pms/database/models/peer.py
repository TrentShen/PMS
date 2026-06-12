from __future__ import annotations

# 互评与匿名评价相关模型（PRD 3.4.5）
# 三个阶段：
#   1) PeerInvitation  —— 员工自选互评人，Leader 审核前的状态
#   2) PeerEvaluation  —— Leader 审核通过后的正式互评任务（含打分内容）
#   3) AnonymousFeedback —— 未被邀请、主动发起的匿名评价（仅 HR/部门 Leader 可见）
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PeerInvitation(SQLModel, table=True):
    # 员工选的候选互评人
    # (cycle_id, invitee_user_id, peer_user_id) 唯一；同一候选只能加一次
    __tablename__ = "peer_invitation"
    __table_args__ = (
        UniqueConstraint("cycle_id", "invitee_user_id", "peer_user_id", name="uq_peer_invitation"),
    )

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    # 被考核人（自己选互评人的那个人）
    invitee_user_id: int = Field(foreign_key="user.id", index=True)
    # 被选中的互评人
    peer_user_id: int = Field(foreign_key="user.id", index=True)
    # pending（员工已选，等 Leader 审核） / approved（已批准，进入正式互评）/ removed（Leader 删除）
    status: str = Field(default="pending", max_length=16, index=True)
    # 是谁提议的：employee（员工自选）/ leader（Leader 新增）
    proposed_by: str = Field(default="employee", max_length=16)
    created_at: datetime = Field(default_factory=_now)


class PeerEvaluation(SQLModel, table=True):
    # 正式互评：审核通过后生成一条待填记录
    # (cycle_id, target_user_id, evaluator_user_id) 唯一
    __tablename__ = "peer_evaluation"
    __table_args__ = (
        UniqueConstraint(
            "cycle_id", "target_user_id", "evaluator_user_id", name="uq_peer_evaluation"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    # 被评人
    target_user_id: int = Field(foreign_key="user.id", index=True)
    # 评价人
    evaluator_user_id: int = Field(foreign_key="user.id", index=True)

    # 业绩 1-5 分，0.25 分段（同自评/上级评估）
    perf_score: float | None = None
    perf_level: str | None = Field(default=None, max_length=32)
    # 价值观三维度
    value_belief_grade: str | None = Field(default=None, max_length=8)
    value_belief_example: str | None = None
    value_team_grade: str | None = Field(default=None, max_length=8)
    value_team_example: str | None = None
    value_growth_grade: str | None = Field(default=None, max_length=8)
    value_growth_example: str | None = None
    comment: str | None = None

    submitted_at: datetime | None = None
    status: str = Field(default="pending", max_length=16, index=True)  # pending / submitted


class AnonymousFeedback(SQLModel, table=True):
    # 匿名主动评价（PRD 3.4.5 中"匿名主动评价"额外通道）
    # 任何员工都可以对任何同事发起；仅 HRBP/部门 Leader 可见
    # 被评人与直属上级都**不可见**
    __tablename__ = "anonymous_feedback"

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: int = Field(foreign_key="performance_cycle.id", index=True)
    # 被评人
    target_user_id: int = Field(foreign_key="user.id", index=True)
    # 评价人（**后端内部留痕，前端永不展示，防止反查**）
    author_user_id: int = Field(foreign_key="user.id", index=True)
    # 评分可选；匿名评价允许只留文字
    perf_score: float | None = None
    value_grade: str | None = Field(default=None, max_length=8)
    comment: str | None = None
    created_at: datetime = Field(default_factory=_now)
