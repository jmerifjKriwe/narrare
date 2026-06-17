"""Tests for RULE-02b checker: direct PromptRegistry access (prompt_path.py).

ADR-046 D.2 Module 1.
"""

from __future__ import annotations

import ast

from scripts.architecture.checkers import check_prompt_registry_access


def _parse(source: str) -> ast.AST:
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    return source.splitlines()


# =====================================================================
# .resolve() call detection — the resolution act
# =====================================================================


class TestResolveCallFlagged:
    """``<registry>.resolve(...)`` outside core/prompts/ IS flagged."""

    def test_prompt_registry_class_resolve_flagged(self) -> None:
        source = 'result = PromptRegistry.resolve(category="kb")\n'
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/analyzer.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].rule == "RULE-02b"
        assert "resolve()" in violations[0].detail

    def test_prompt_registry_instance_resolve_flagged(self) -> None:
        source = 'result = self._prompt_registry.resolve(category="kb")\n'
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/worldbuilding_analyzer.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].line == 1

    def test_local_registry_var_resolve_flagged(self) -> None:
        source = 'result = prompt_registry.resolve(mode="phase2")\n'
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/service.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1

    def test_correct_line_number_for_resolve(self) -> None:
        source = 'x = 1\ny = 2\nresult = self._prompt_registry.resolve(category="kb")\n'
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/analyzer.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].line == 3


class TestPathResolveNotFlagged:
    """``Path(...).resolve()`` is NOT flagged (not a registry receiver)."""

    def test_path_resolve_allowed(self) -> None:
        source = "ROOT = Path(__file__).resolve().parent\n"
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_extra_resolve_allowed(self) -> None:
        source = "p = extra.resolve()\n"
        violations = check_prompt_registry_access(
            "scripts/some_tool.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_config_resolve_allowed(self) -> None:
        source = "val = settings.resolve()\n"
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# Import detection (resolution-purpose imports)
# =====================================================================


class TestImportFlagged:
    """PromptRegistry imports for resolution (no construction) ARE flagged."""

    def test_import_from_registry_module_flagged(self) -> None:
        source = "from narrare_core.prompts.registry import PromptRegistry\n"
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/service.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].rule == "RULE-02b"
        assert "PromptRegistry imported" in violations[0].detail

    def test_import_from_prompts_package_flagged(self) -> None:
        source = "from narrare_core.prompts import PromptRegistry\n"
        violations = check_prompt_registry_access(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1

    def test_import_other_names_not_flagged(self) -> None:
        source = "from narrare_core.prompts import PromptComposer, PromptContext\n"
        violations = check_prompt_registry_access(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# DI-wiring exemption (construction = wiring, not resolution)
# =====================================================================


class TestDIWiringExempt:
    """Files that construct ``PromptRegistry(...)`` are DI wiring — import exempt."""

    def test_construction_exempts_import(self) -> None:
        # The real DI pattern from _app/dependencies_prompts.py
        source = (
            "from narrare_core.prompts import PromptComposer, PromptRegistry\n"
            "\n"
            "def get_registry() -> PromptRegistry:\n"
            "    return PromptRegistry(project_root=BASE_DIR)\n"
        )
        violations = check_prompt_registry_access(
            "apps/api/narrare/_app/dependencies_prompts.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_construction_but_resolve_still_flagged(self) -> None:
        # Even a DI file that resolves is caught on the resolve() call.
        # The receiver must be registry-typed (contains "registry") to be flagged;
        # a bare ``reg.resolve()`` is too ambiguous (could be ModelRegistry).
        source = (
            "from narrare_core.prompts import PromptRegistry\n"
            "registry = PromptRegistry()\n"
            'result = registry.resolve(category="kb")\n'
        )
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/service.py",
            _parse(source),
            _lines(source),
        )
        # resolve() flagged; import exempted by construction.
        assert len(violations) == 1
        assert "resolve()" in violations[0].detail
        assert violations[0].line == 3


# =====================================================================
# Scope filtering — exempt paths
# =====================================================================


class TestScopeFiltering:
    """core/prompts/, core/agents/capabilities/, and tests are NOT checked."""

    def test_core_prompts_not_checked(self) -> None:
        source = (
            "from narrare_core.prompts.registry import PromptRegistry\n"
            'result = PromptRegistry.resolve(category="kb")\n'
        )
        violations = check_prompt_registry_access(
            "packages/core/narrare_core/prompts/composer.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_capabilities_not_checked(self) -> None:
        source = "from narrare_core.prompts import PromptRegistry\n"
        violations = check_prompt_registry_access(
            "packages/core/narrare_core/agents/capabilities/meta.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_test_files_not_checked(self) -> None:
        source = (
            "from narrare_core.prompts.registry import PromptRegistry\n"
            'result = PromptRegistry.resolve(category="kb")\n'
        )
        violations = check_prompt_registry_access(
            "tests/unit/core/prompts/test_registry.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_type_checking_block_not_checked(self) -> None:
        source = (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from narrare_core.prompts.registry import PromptRegistry\n"
        )
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# Approved exceptions
# =====================================================================


class TestApprovedExceptions:
    """Inline approval markers suppress violations."""

    def test_approval_marker_accepted_on_resolve(self) -> None:
        source = (
            '# narrare: allow reason="legacy phase2 during migration"\n'
            'result = self._prompt_registry.resolve(category="kb")\n'
        )
        violations = check_prompt_registry_access(
            "apps/api/narrare/kb/analyzer.py",
            _parse(source),
            _lines(source),
        )
        assert len(violations) == 1
        assert violations[0].approved is True
        assert "legacy phase2" in violations[0].approval_reason
