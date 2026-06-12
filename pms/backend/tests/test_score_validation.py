from __future__ import annotations

import pytest

from pms.database.models.enums import PerfLevel
from pms.utils.score import derive_perf_level, validate_perf_score


class TestValidatePerfScore:
    """业绩评分 0.25 分段校验"""

    @pytest.mark.parametrize(
        "score",
        [
            1.0,
            1.25,
            2.5,
            3.0,
            3.25,
            3.75,
            4.0,
            4.25,
            4.5,
            4.75,
            5.0,
        ],
    )
    def test_valid_scores(self, score: float) -> None:
        assert validate_perf_score(score) == score

    @pytest.mark.parametrize(
        "score",
        [
            0.9,   # 低于 1.0
            0.0,
            5.01,  # 高于 5.0
            6.0,
            3.33,  # 不是 0.25 倍数
            4.17,
            2.01,
        ],
    )
    def test_invalid_scores_raise(self, score: float) -> None:
        with pytest.raises(ValueError):
            validate_perf_score(score)

    def test_none_raises(self) -> None:
        with pytest.raises(ValueError, match="必填"):
            validate_perf_score(None)  # type: ignore[arg-type]


class TestDerivePerfLevel:
    """业绩分 → 等级派生"""

    @pytest.mark.parametrize(
        "score,expected",
        [
            (4.76, PerfLevel.EXCELLENT),
            (4.51, PerfLevel.EXCELLENT),
            (5.0, PerfLevel.EXCELLENT),
            (4.5, PerfLevel.EXCEED_PART),
            (4.01, PerfLevel.EXCEED_PART),
            (4.0, PerfLevel.EXCEED_PART),
            (3.51, PerfLevel.MEET),
            (3.5, PerfLevel.MEET),
            (3.01, PerfLevel.BELOW_PART),
            (3.0, PerfLevel.BELOW_PART),
            (2.5, PerfLevel.BELOW),
            (1.0, PerfLevel.BELOW),
        ],
    )
    def test_level_mapping(self, score: float, expected: PerfLevel) -> None:
        assert derive_perf_level(score) == expected
