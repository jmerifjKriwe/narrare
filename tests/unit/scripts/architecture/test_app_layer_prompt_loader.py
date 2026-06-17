"""Tests for RULE-02b checker: app-layer prompt loaders (prompts.py extension).

ADR-046 D.2 Module 2.
"""

from __future__ import annotations

import ast

from scripts.architecture.checkers import check_app_layer_prompt_loader


def _parse(source: str) -> ast.AST:
    return ast.parse(source)


def _lines(source: str) -> list[str]:
    return source.splitlines()


# =====================================================================
# importlib.resources + _bundled detection
# =====================================================================


class TestImportlibBundledFlagged:
    """importlib.resources + _bundled literal in apps/ IS flagged."""

    def test_importfrom_resources_with_bundled_flagged(self) -> None:
        # The exact CR-AUFG-02-06 pattern.
        source = (
            "import importlib.resources\n"
            'path = importlib.resources.files("narrare_core.prompts._bundled")\n'
        )
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/planning/_prompt_loader.py",
            _parse(source),
            _lines(source),
        )
        bundled_hits = [v for v in violations if "importlib" in v.detail]
        assert len(bundled_hits) == 1
        assert bundled_hits[0].rule == "RULE-02b"

    def test_from_importlib_resources_with_bundled_flagged(self) -> None:
        source = 'from importlib.resources import files\ndata = files("pkg.prompts._bundled")\n'
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/planning/loader.py",
            _parse(source),
            _lines(source),
        )
        bundled_hits = [v for v in violations if "importlib" in v.detail]
        assert len(bundled_hits) == 1


# =====================================================================
# .replace("{{...") detection
# =====================================================================


class TestManualSubstitutionFlagged:
    """``.replace(\"{{...\")`` in apps/ IS flagged."""

    def test_replace_template_var_flagged(self) -> None:
        # The exact CR-AUFG-02-06 manual-substitution pattern.
        source = (
            'prompt = template.replace("{{project_title}}", title)\n'
            'prompt = prompt.replace("{{genre}}", genre)\n'
        )
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/planning/_prompt_loader.py",
            _parse(source),
            _lines(source),
        )
        replace_hits = [v for v in violations if ".replace" in v.detail]
        assert len(replace_hits) == 2
        assert all(v.rule == "RULE-02b" for v in replace_hits)

    def test_replace_non_template_not_flagged(self) -> None:
        source = 'clean = text.replace("foo", "bar")\n'
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/kb/service.py",
            _parse(source),
            _lines(source),
        )
        replace_hits = [v for v in violations if ".replace" in v.detail]
        assert replace_hits == []


# =====================================================================
# Filename pattern detection
# =====================================================================


class TestFilenamePatternFlagged:
    """Loader filenames in apps/ ARE flagged."""

    def test_prompt_loader_filename_flagged(self) -> None:
        source = "x = 1\n"
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/planning/_prompt_loader.py",
            _parse(source),
            _lines(source),
        )
        filename_hits = [v for v in violations if "filename" in v.detail]
        assert len(filename_hits) == 1
        assert "_prompt_loader.py" in violations[0].detail

    def test_prompt_prefix_filename_flagged(self) -> None:
        source = "x = 1\n"
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/planning/_prompt_utils.py",
            _parse(source),
            _lines(source),
        )
        filename_hits = [v for v in violations if "filename" in v.detail]
        assert len(filename_hits) == 1


# =====================================================================
# Scope filtering — only apps/
# =====================================================================


class TestScopeFiltering:
    """Non-apps/ paths are NOT checked."""

    def test_core_not_checked(self) -> None:
        # core/prompts/ legitimately uses importlib.resources + _bundled.
        source = (
            "import importlib.resources\n"
            'path = importlib.resources.files("._bundled")\n'
            'prompt = template.replace("{{x}}", "y")\n'
        )
        violations = check_app_layer_prompt_loader(
            "packages/core/narrare_core/prompts/registry.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_tests_not_checked(self) -> None:
        source = 'import importlib.resources\npath = importlib.resources.files("._bundled")\n'
        violations = check_app_layer_prompt_loader(
            "tests/unit/api/planning/test_loader.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []

    def test_normal_app_file_not_flagged(self) -> None:
        # A normal service file with no loader patterns.
        source = (
            "from narrare_core.prompts import PromptComposer\n"
            "composed = await composer.build(intent, ctx)\n"
            "return composed.user\n"
        )
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/chat/chat_service.py",
            _parse(source),
            _lines(source),
        )
        assert violations == []


# =====================================================================
# TYPE_CHECKING exclusion
# =====================================================================


class TestTypeCheckingExclusion:
    def test_importlib_in_type_checking_not_flagged(self) -> None:
        source = (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from importlib.resources import files\n"
            '    bundled = files("._bundled")\n'
        )
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/planning/service.py",
            _parse(source),
            _lines(source),
        )
        bundled_hits = [v for v in violations if "importlib" in v.detail]
        assert bundled_hits == []


# =====================================================================
# Approved exceptions
# =====================================================================


class TestApprovedExceptions:
    def test_approval_marker_accepted(self) -> None:
        source = (
            '# narrare: allow reason="temporary loader during migration"\n'
            'prompt = template.replace("{{project_title}}", title)\n'
        )
        violations = check_app_layer_prompt_loader(
            "apps/api/narrare/planning/_prompt_loader.py",
            _parse(source),
            _lines(source),
        )
        replace_hits = [v for v in violations if ".replace" in v.detail]
        assert len(replace_hits) == 1
        assert replace_hits[0].approved is True
        assert "migration" in replace_hits[0].approval_reason
