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


# 价值观等级"甲"必须附事例，这里只提供校验函数
def require_value_example_if_jia(grade: str, example: str | None) -> None:
    if grade == "jia" and (not example or not example.strip()):
        raise ValueError("价值观评为\"甲\"时必须填写具体事例")


def validate_weights_sum(weights: list[int]) -> None:
    total = sum(weights)
    if total != 100:
        raise ValueError(f"目标权重之和必须为 100，当前为 {total}")
