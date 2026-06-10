from __future__ import annotations

# 绩效评分校验与派生工具
# 业绩分: 1.0 ~ 5.0 之间、必须 0.25 分段
# 派生等级: PRD 3.4.1 的分段规则
from decimal import Decimal

from pms.database.models.enums import PerfLevel


def validate_perf_score(score: float) -> float:
    # 返回规范化后的 score；非法时抛 ValueError
    if score is None:
        raise ValueError("业绩分必填")
    if not (1.0 <= score <= 5.0):
        raise ValueError("业绩分必须在 1.0 ~ 5.0 之间")
    # 用 Decimal 避免浮点误差；score * 4 应为整数
    d = Decimal(str(score)) * 4
    if d != d.to_integral_value():
        raise ValueError("业绩分必须是 0.25 的倍数（如 3.25、4.00、4.75）")
    return float(score)


def derive_perf_level(score: float) -> PerfLevel:
    # 分段规则摘自 PRD 3.4.1
    if score > 4.5:
        return PerfLevel.EXCELLENT
    if score > 4.0:
        return PerfLevel.EXCEED_PART
    if score > 3.5:
        return PerfLevel.MEET
    if score > 3.0:
        return PerfLevel.BELOW_PART
    return PerfLevel.BELOW


# 价值观三维度校验：每个维度评"甲"时必须附事例
VALUE_DIMS = [
    ("belief", "信念"),
    ("team", "团队"),
    ("growth", "成长"),
]

def validate_value_grades(
    belief_grade: str | None, belief_example: str | None,
    team_grade: str | None, team_example: str | None,
    growth_grade: str | None, growth_example: str | None,
) -> None:
    pairs = [
        (belief_grade, belief_example, "信念"),
        (team_grade, team_example, "团队"),
        (growth_grade, growth_example, "成长"),
    ]
    for grade, example, label in pairs:
        if not grade:
            raise ValueError(f"价值观「{label}」维度等级必填")
        if grade not in ("jia", "yi", "bing"):
            raise ValueError(f"价值观「{label}」等级只能是 jia/yi/bing")
        if grade == "jia" and (not example or not example.strip()):
            raise ValueError(f"价值观「{label}」评为甲时必须填写具体事例")


# 兼容旧接口的单维度校验（deprecated，保留给互评等简化场景）
def require_value_example_if_jia(grade: str, example: str | None) -> None:
    if grade == "jia" and (not example or not example.strip()):
        raise ValueError("价值观评为\"甲\"时必须填写具体事例")


def validate_weights_sum(weights: list[int]) -> None:
    total = sum(weights)
    if total != 100:
        raise ValueError(f"目标权重之和必须为 100，当前为 {total}")
