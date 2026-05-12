# 通用枚举常量定义
# 用字符串枚举而非 int，数据库可读性更好、迁移友好
from enum import StrEnum


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
