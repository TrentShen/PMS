from __future__ import annotations

import pytest

from pms.utils.score import validate_weights_sum


class TestValidateWeightsSum:
    """目标权重和校验"""

    def test_exact_100_passes(self) -> None:
        validate_weights_sum([40, 30, 20, 10])

    def test_single_100_passes(self) -> None:
        validate_weights_sum([100])

    def test_over_100_raises(self) -> None:
        with pytest.raises(ValueError, match="必须为 100"):
            validate_weights_sum([50, 50, 10])

    def test_under_100_raises(self) -> None:
        with pytest.raises(ValueError, match="必须为 100"):
            validate_weights_sum([30, 30])

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="必须为 100"):
            validate_weights_sum([])
