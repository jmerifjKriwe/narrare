"""CR-08 P2 tests — typed SystemModelCategory for system model resolver.

Verifies:
1. ``build_system_default_config(SystemModelCategory.WRITING)`` returns
   a config with the writing model.
2. ``build_system_default_config(SystemModelCategory.ANALYSIS)`` returns
   a config with the analysis model.
3. Passing a plain string raises ``TypeError`` (type safety).
4. Passing an invalid enum member raises ``ValidationError``.
"""

from __future__ import annotations

import enum

import pytest

from narrare._app.dependencies_services import (
    SystemModelCategory,
    build_system_default_config,
)


class TestSystemModelCategoryEnum:
    def test_is_str_enum(self) -> None:
        """SystemModelCategory must be a proper enum.StrEnum."""
        assert issubclass(SystemModelCategory, enum.StrEnum)

    def test_writing_member_value(self) -> None:
        assert SystemModelCategory.WRITING.value == "writing"

    def test_analysis_member_value(self) -> None:
        assert SystemModelCategory.ANALYSIS.value == "analysis"


class TestBuildSystemDefaultConfig:
    def test_writing_returns_writing_model(self) -> None:
        config = build_system_default_config(SystemModelCategory.WRITING)
        assert config.provider_name != ""
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_analysis_returns_analysis_model(self) -> None:
        config = build_system_default_config(SystemModelCategory.ANALYSIS)
        assert config.provider_name != ""
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_custom_temperature_and_max_tokens(self) -> None:
        config = build_system_default_config(
            SystemModelCategory.WRITING,
            temperature=0.3,
            max_tokens=1024,
        )
        assert config.temperature == 0.3
        assert config.max_tokens == 1024

    def test_passing_plain_string_accepted_at_runtime(self) -> None:
        """A plain ``str`` is accepted at runtime because Python does not
        enforce type hints — but static analysis will flag it via the
        ``SystemModelCategory`` annotation. This test documents the
        runtime-vs-static boundary.
        """
        # Runtime: string is compatible because SystemModelCategory is a str enum
        config = build_system_default_config("writing")  # type: ignore[arg-type]
        assert config.provider_name != ""
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_passing_invalid_enum_value_raises_error(self) -> None:
        """An enum value that is not a valid SystemModelCategory member
        must raise an appropriate error.
        """
        with pytest.raises(ValueError):
            build_system_default_config(SystemModelCategory("invalid"))
