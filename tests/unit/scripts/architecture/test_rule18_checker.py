"""Tests for RULE-18: no hardcoded model configuration in routers/dependencies."""

from __future__ import annotations

import ast

from scripts.architecture.checkers import check_hardcoded_model_config


def _parse(source: str) -> ast.AST:
    """Parse source code into an AST."""
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    """Split source into lines."""
    return source.splitlines()


# =====================================================================
# Violation detected — hardcoded provider_name
# =====================================================================


class TestViolationDetected:
    """ResolvedModelConfig(provider_name=<string>) in apps/api/ IS flagged."""

    def test_provider_name_default_flagged(self) -> None:
        """provider_name='default' → violation (the original bug)."""
        source = """\
from narrare_core.llm.intents import ResolvedModelConfig

config = ResolvedModelConfig(
    provider_name="default",
    model_id="default",
)
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].rule == "RULE-18"
        assert "default" in violations[0].detail
        assert "settings cascade" in violations[0].detail

    def test_provider_name_anthropic_flagged(self) -> None:
        """provider_name='anthropic' → violation."""
        source = """\
from narrare_core.llm.intents import ResolvedModelConfig

config = ResolvedModelConfig(
    provider_name="anthropic",
    model_id="claude-sonnet-4-20250514",
)
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/writing/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "anthropic" in violations[0].detail

    def test_provider_name_openai_flagged(self) -> None:
        """provider_name='openai' → violation."""
        source = """\
config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/writing/router.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1

    def test_provider_name_ollama_flagged(self) -> None:
        """provider_name='ollama' → violation."""
        source = """\
config = ResolvedModelConfig(provider_name="ollama", model_id="llama3")
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/generation/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1

    def test_any_string_literal_flagged(self) -> None:
        """Any string literal for provider_name → violation (RULE-18 strict)."""
        source = """\
config = ResolvedModelConfig(provider_name="my-custom-provider", model_id="x")
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/_app/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "my-custom-provider" in violations[0].detail

    def test_multiple_calls_in_same_file(self) -> None:
        """Multiple ResolvedModelConfig calls → multiple violations."""
        source = """\
config1 = ResolvedModelConfig(provider_name="anthropic", model_id="a")
config2 = ResolvedModelConfig(provider_name="openai", model_id="b")
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 2

    def test_correct_line_number_reported(self) -> None:
        """Violation reports the line of the ResolvedModelConfig() call."""
        source = """\
from narrare_core.llm.intents import ResolvedModelConfig

config = ResolvedModelConfig(
    provider_name="groq",
    model_id="llama3",
)
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/analysis/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].line == 3


# =====================================================================
# No violation — correct code
# =====================================================================


class TestNoViolation:
    """Code that correctly uses variable references is NOT flagged."""

    def test_variable_reference_allowed(self) -> None:
        """provider_name=<variable> → no violation."""
        source = """\
from narrare_core.llm.intents import ResolvedModelConfig

settings = get_settings()
config = ResolvedModelConfig(
    provider_name=settings.provider_name,
    model_id=settings.model_id,
)
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/writing/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_no_provider_name_kwarg(self) -> None:
        """ResolvedModelConfig() without provider_name → no violation."""
        source = """\
config = ResolvedModelConfig(model_id="test")
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/kb/service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_no_resolved_model_config_call(self) -> None:
        """No ResolvedModelConfig at all → no violation."""
        source = """\
def get_service(session: SessionDep) -> Service:
    return Service(session)
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/writing/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_model_id_string_not_flagged(self) -> None:
        """model_id=<string> alone → no violation (only provider_name checked)."""
        source = """\
config = ResolvedModelConfig(
    provider_name=get_provider(),
    model_id="claude-sonnet-4-20250514",
)
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/writing/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# Scope filtering — non-apps/api paths
# =====================================================================


class TestScopeFiltering:
    """Check is only applied to files under apps/api/."""

    def test_packages_core_not_checked(self) -> None:
        """packages/core/ files are NOT checked."""
        source = """\
config = ResolvedModelConfig(provider_name="anthropic", model_id="a")
"""
        violations = check_hardcoded_model_config(
            "packages/core/narrare_core/llm/gateway.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_tests_not_checked(self) -> None:
        """tests/ files are NOT checked."""
        source = """\
config = ResolvedModelConfig(provider_name="anthropic", model_id="a")
"""
        violations = check_hardcoded_model_config(
            "tests/unit/api/writing/conftest.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_root_file_not_checked(self) -> None:
        """Root-level files are NOT checked."""
        source = """\
config = ResolvedModelConfig(provider_name="anthropic", model_id="a")
"""
        violations = check_hardcoded_model_config(
            "scripts/some_script.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_non_apps_api_path_not_checked(self) -> None:
        """packages/web/ files are NOT checked."""
        source = """\
config = ResolvedModelConfig(provider_name="anthropic", model_id="a")
"""
        violations = check_hardcoded_model_config(
            "packages/web/src/lib/config.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# TYPE_CHECKING block exclusion
# =====================================================================


class TestTypeCheckingExclusion:
    """Calls inside if TYPE_CHECKING: blocks are NOT flagged."""

    def test_type_checking_block_not_flagged(self) -> None:
        """ResolvedModelConfig inside if TYPE_CHECKING: → no violation."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.llm.intents import ResolvedModelConfig

    config = ResolvedModelConfig(provider_name="anthropic", model_id="a")
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/writing/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_mixed_tc_and_non_tc(self) -> None:
        """Only the non-TYPE_CHECKING call is flagged."""
        source = """\
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    config_tc = ResolvedModelConfig(provider_name="anthropic", model_id="a")

config_real = ResolvedModelConfig(provider_name="openai", model_id="b")
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/writing/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert "openai" in violations[0].detail


# =====================================================================
# Approved exceptions
# =====================================================================


class TestApprovedExceptions:
    """Approved exceptions are marked accordingly."""

    def test_approval_marker_accepted(self) -> None:
        """# narrare: allow comment suppresses the violation."""
        source = """\
from narrare_core.llm.intents import ResolvedModelConfig

# narrare: allow reason="temporary fallback during migration"
config = ResolvedModelConfig(provider_name="default", model_id="default")
"""
        violations = check_hardcoded_model_config(
            "apps/api/narrare/kb/dependencies.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].approved is True
        assert "temporary fallback" in violations[0].approval_reason
