from __future__ import annotations

import pytest

from pms.utils.score import validate_value_grades


class TestValidateValueGrades:
    """价值观三维度校验"""

    def test_all_yi_passes(self) -> None:
        validate_value_grades("yi", None, "yi", None, "yi", None)

    def test_jia_with_example_passes(self) -> None:
        validate_value_grades(
            "jia", "具体事例",
            "jia", "具体事例",
            "yi", None,
        )

    def test_jia_without_example_raises(self) -> None:
        with pytest.raises(ValueError, match="评为甲时必须填写具体事例"):
            validate_value_grades("jia", None, "yi", None, "yi", None)

    def test_jia_empty_example_raises(self) -> None:
        with pytest.raises(ValueError, match="评为甲时必须填写具体事例"):
            validate_value_grades("jia", "   ", "yi", None, "yi", None)

    def test_missing_grade_raises(self) -> None:
        with pytest.raises(ValueError, match="必填"):
            validate_value_grades(None, None, "yi", None, "yi", None)

    def test_invalid_grade_raises(self) -> None:
        with pytest.raises(ValueError, match="只能是 jia/yi/bing"):
            validate_value_grades("jia", "事例", "jia", "事例", "abc", None)
