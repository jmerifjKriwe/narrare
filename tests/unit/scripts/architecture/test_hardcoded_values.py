"""Tests for RULE-18: configurable defaults — hardcoded constants checker.

Covers patterns 1, 2, and 4 (pattern 3 was excluded from the design).
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from scripts.architecture._checkers.hardcoded_values import check_hardcoded_constants

if TYPE_CHECKING:
    from scripts.architecture.types import Violation

# Default config matching pyproject.toml
DEFAULT_CONFIG: dict[str, object] = {
    "max_allowed_constant": 5,
    "allowed_patterns": [
        "_PERCENTAGES",
        "_VALID_",
        "_PREFERENCE_",
        "_PROVIDER",
        "SUPPORTED_",
    ],
    "ignored_modules": [],
}


def _parse(source: str) -> ast.AST:
    """Parse source code into an AST."""
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    """Split source into lines."""
    return source.splitlines()


def _check(
    source: str, rel_path: str = "packages/core/narrare_core/some/module.py"
) -> list[Violation]:
    """Convenience: parse + check with default config."""
    return check_hardcoded_constants(rel_path, _parse(source), _lines(source), DEFAULT_CONFIG)


# =====================================================================
# Pattern 1: Module-level integer/float constants
# =====================================================================


class TestFlagsModuleLevelInt:
    """Module-level integer/float constants > max_allowed are flagged."""

    def test_flags_large_int(self) -> None:
        v = _check("MAX_RETRIES = 10\n")
        assert len(v) == 1
        assert "MAX_RETRIES" in v[0].detail

    def test_flags_large_float(self) -> None:
        v = _check("DEFAULT_TIMEOUT = 30.0\n")
        assert len(v) == 1
        assert "DEFAULT_TIMEOUT" in v[0].detail

    def test_allows_value_at_threshold(self) -> None:
        assert _check("LIMIT = 5\n") == []

    def test_allows_value_below_threshold(self) -> None:
        assert _check("SMALL = 3\n") == []

    def test_does_not_flag_inside_function(self) -> None:
        assert _check("def compute():\n    LARGE = 100\n    return LARGE\n") == []

    def test_reports_correct_line_number(self) -> None:
        v = _check("import os\n\nMAX_RETRIES = 10\n")
        assert len(v) == 1
        assert v[0].line == 3


# =====================================================================
# Trivial values
# =====================================================================


class TestAllowsTrivialValues:
    """Trivial values (0.0, 0.5, 1.0, 2.0, <0.5) are not flagged."""

    def test_allows_zero(self) -> None:
        assert _check("OFFSET = 0\n") == []

    def test_allows_one(self) -> None:
        assert _check("COUNT = 1\n") == []

    def test_allows_two(self) -> None:
        assert _check("RETRIES = 2\n") == []

    def test_allows_half(self) -> None:
        assert _check("FACTOR = 0.5\n") == []

    def test_allows_small_fraction(self) -> None:
        assert _check("RATE = 0.3\n") == []


# =====================================================================
# Pattern 2: Hardcoded timeouts
# =====================================================================


class TestFlagsTimeoutInCall:
    """Hardcoded ``timeout=`` in function calls is flagged."""

    def test_flags_float_timeout(self) -> None:
        v = _check("result = some_call(timeout=30.0)\n")
        assert len(v) == 1
        assert "timeout=30.0" in v[0].detail

    def test_flags_integer_timeout(self) -> None:
        v = _check("result = some_call(timeout=60)\n")
        assert len(v) == 1
        assert "timeout=60" in v[0].detail

    def test_allows_variable_timeout(self) -> None:
        assert _check("result = some_call(timeout=settings.timeout)\n") == []

    def test_allows_small_timeout(self) -> None:
        assert _check("result = some_call(timeout=3)\n") == []


# =====================================================================
# Allowed patterns
# =====================================================================


class TestAllowsAllowedPatterns:
    """Variables matching allowed_patterns are not flagged."""

    def test_allows_percentage_pattern(self) -> None:
        assert _check('_PERCENTAGES = {"a": 0.5, "b": 0.3}\n') == []

    def test_allows_valid_pattern(self) -> None:
        assert _check("_VALID_MODELS = 10\n") == []

    def test_allows_supported_pattern(self) -> None:
        assert _check("SUPPORTED_FORMATS = 20\n") == []


# =====================================================================
# Config class exemption
# =====================================================================


class TestAllowsConfigClass:
    """Constants inside Config/Settings/Limits/Profile classes are not flagged."""

    def test_config_class_not_flagged(self) -> None:
        assert _check("class ModelConfig:\n    MAX_TOKENS = 100\n    TEMPERATURE = 0.7\n") == []

    def test_settings_class_not_flagged(self) -> None:
        assert _check("class AppSettings:\n    TIMEOUT = 30\n") == []

    def test_regular_class_flagged(self) -> None:
        v = _check("class Service:\n    MAX_RETRIES = 10\n")
        assert len(v) == 1
        assert "MAX_RETRIES" in v[0].detail


# =====================================================================
# TYPE_CHECKING block exclusion
# =====================================================================


class TestAllowsTypeCheckingBlock:
    """Constants inside ``if TYPE_CHECKING:`` blocks are not flagged."""

    def test_type_checking_not_flagged(self) -> None:
        source = "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    LARGE = 100\n"
        assert _check(source) == []

    def test_mixed_tc_and_non_tc(self) -> None:
        source = (
            "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    TC = 100\n\nREAL = 100\n"
        )
        v = _check(source)
        assert len(v) == 1
        assert "REAL" in v[0].detail


# =====================================================================
# Test file exclusion & ignored modules
# =====================================================================


class TestSkipsFiles:
    """test_*.py, conftest, and ignored modules are skipped."""

    def test_test_file_ignored(self) -> None:
        assert _check("MAX_RETRIES = 100\n", "tests/unit/core/test_something.py") == []

    def test_conftest_ignored(self) -> None:
        assert _check("MAX_RETRIES = 100\n", "tests/unit/core/conftest.py") == []

    def test_ignored_module_skipped(self) -> None:
        config: dict[str, object] = {
            "max_allowed_constant": 5,
            "allowed_patterns": [],
            "ignored_modules": ["packages/core/narrare_core/llm/cost_rates.py"],
        }
        v = check_hardcoded_constants(
            "packages/core/narrare_core/llm/cost_rates.py",
            _parse("RATE = 100\n"),
            _lines("RATE = 100\n"),
            config,
        )
        assert v == []


# =====================================================================
# Approved exceptions
# =====================================================================


class TestApprovedException:
    """``# narrare: allow`` comment marks a violation as approved."""

    def test_approval_accepted(self) -> None:
        source = '# narrare: allow reason="legacy default"\nMAX_RETRIES = 100\n'
        v = _check(source)
        assert len(v) == 1
        assert v[0].approved is True
        assert "legacy default" in v[0].approval_reason

    def test_without_approval_not_approved(self) -> None:
        v = _check("MAX_RETRIES = 100\n")
        assert len(v) == 1
        assert v[0].approved is False


# =====================================================================
# Pattern 4: Percentage dicts without ClassVar
# =====================================================================


class TestPercentageDicts:
    """Percentage dicts without ClassVar annotation are flagged."""

    def test_flags_plain_percentage_dict(self) -> None:
        v = _check('SAMPLING_RATES = {"low": 0.2, "high": 0.8}\n')
        pct = [x for x in v if "Percentage dict" in x.detail]
        assert len(pct) == 1
        assert "SAMPLING_RATES" in pct[0].detail

    def test_allows_classvar_annotated_dict(self) -> None:
        source = (
            "from typing import ClassVar\n\n"
            "class C:\n"
            '    RATES: ClassVar[dict[str, float]] = {"a": 0.5}\n'
        )
        v = _check(source)
        assert all("Percentage dict" not in x.detail for x in v)

    def test_non_percentage_dict_not_flagged(self) -> None:
        v = _check('CONFIGS = {"a": 10, "b": 20}\n')
        assert all("Percentage dict" not in x.detail for x in v)
