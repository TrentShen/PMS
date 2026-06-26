from __future__ import annotations

# 通用枚举常量定义
# 用字符串枚举而非 int，数据库可读性更好、迁移友好
from enum import Enum

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11
    class StrEnum(str, Enum):  # noqa: UP042
        """兼容 Python 3.10 的字符串枚举。"""

        def __str__(self) -> str:
            return self.value


class Role(StrEnum):
    # 角色定义（PRD 2.1）
    SUPER_ADMIN = "super_admin"          # 超级管理员
    HRBP = "hrbp"                        # HR/绩效管理员
    DEPT_LEADER = "dept_leader"          # 部门 Leader（校准人）
    DIRECT_LEADER = "direct_leader"      # 直属上级（非部门负责人但有下属）
    EMPLOYEE = "employee"                # 普通员工


class CycleStatus(StrEnum):
    # 绩效周期生命周期
    DRAFT = "draft"              # 草稿，HR 还在配置参与人
    IN_PROGRESS = "in_progress"  # 进行中，员工可自评等
    PUBLISHED = "published"      # 已公布，员工可见结果
    CLOSED = "closed"            # 已归档


class ParticipantStatus(StrEnum):
    # 参与人在某周期下的进度（驱动前端"我的待办"显示）
    PENDING = "pending"            # 待自评
    SELF_DONE = "self_done"        # 自评已完成，等上级评
    LEADER_DONE = "leader_done"    # 上级已评，等发布
    PUBLISHED = "published"        # 已公布，员工可见
    EXCLUDED = "excluded"          # 周期关闭/归档时被排除，未参与完成


class EvalType(StrEnum):
    # 评估类型；V0.9 只有自评和上级评估
    SELF = "self"
    SUPERIOR = "superior"
    # PEER = "peer"              # Sprint 2


class PerfLevel(StrEnum):
    # 业绩等级（由 perf_score 派生，见 utils/score.py）
    EXCELLENT = "excellent"              # >4.5 优秀
    EXCEED_PART = "exceed_part"          # 4.0~4.5 部分超出
    MEET = "meet"                        # 3.5~4.0 符合预期
    BELOW_PART = "below_part"            # 3.0~3.5 部分不符
    BELOW = "below"                      # <=3.0 不符合


class ValueGrade(StrEnum):
    # 价值观等级（PRD 3.4.1）
    JIA = "jia"      # 甲 — 必须填具体事例
    YI = "yi"        # 乙 — 失去晋升及调薪资格
    BING = "bing"    # 丙


class ProbationPlanStatus(StrEnum):
    # 试用期计划生命周期
    DRAFT = "draft"                              # 计划已创建，目标未填写
    OBJECTIVE_DRAFT = "objective_draft"          # 员工填写目标中，未提交
    OBJECTIVE_PENDING_REVIEW = "objective_pending_review"  # 目标已提交，待上级审批
    IN_PROGRESS = "in_progress"                  # 目标已批准，试用期进行中
    PENDING_EVALUATION = "pending_evaluation"    # 临转正前，待上级评估
    COMPLETED = "completed"                      # 评估已完成
    EXTENDED = "extended"                        # 已延期


class ProbationObjectiveStatus(StrEnum):
    # 试用期目标状态
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    LOCKED = "locked"


class ProbationResult(StrEnum):
    # 试用期转正建议
    REGULAR = "regular"              # 建议转正
    ELIMINATE = "eliminate"          # 建议淘汰
    PENDING_OTHER = "pending_other"  # 待定/其他
