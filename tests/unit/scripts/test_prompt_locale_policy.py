"""Regression tests for ADR-026 Phase 5 prompt locale policy.

Bundled feature system prompts are EN-only by default. Locale coverage remains
required for meta/universal prompt families, and sync checks must still compare
feature families once more than one locale variant exists.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPTS_DIR = _ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from prompt_check_types import Issue, PromptFile  # noqa: E402
from prompt_checks_crossfile import check_locale_coverage  # noqa: E402
from scripts.architecture._checkers import _check_i18n  # noqa: E402
from scripts.architecture.types import CheckResult  # noqa: E402
from scripts.check_locale_sync import check_sync, discover_groups  # noqa: E402


def _prompt_file(category: str, locale: str, mode: str = "test") -> PromptFile:
    """Create a system.md PromptFile for cross-file locale policy checks."""
    rel_path = f"{category}/{locale}/{mode}/system.md" if mode else f"{category}/{locale}/system.md"
    return PromptFile(
        path=Path(rel_path),
        rel_path=rel_path,
        frontmatter={"prompt_type": category},
        category=category,
        locale=locale,
        mode=mode,
    )


def _write_system_prompt(
    bundled_dir: Path,
    rel_path: str,
    *,
    variables: tuple[str, ...] = (),
) -> None:
    """Write a minimal prompt file with optional template variables."""
    path = bundled_dir / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    variable_lines = "\n".join(f"{{{{{variable}}}}}" for variable in variables)
    path.write_text(
        textwrap.dedent(
            f"""
            ---
            prompt_type: test
            prompt_language: en
            prompt_version: 1.0.0
            ---

            # System Prompt

            {variable_lines}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


class TestPromptLocaleCoveragePolicy:
    """ADR-026 Phase 5 locale coverage behavior."""

    @pytest.mark.parametrize(
        ("category", "mode"),
        [("writing", "test"), ("analysis", "review")],
    )
    def test_en_only_bundled_feature_prompt_does_not_warn(
        self,
        category: str,
        mode: str,
    ) -> None:
        issues: list[Issue] = []

        check_locale_coverage([_prompt_file(category, "en", mode)], issues)

        assert issues == []

    @pytest.mark.parametrize("category", ["meta", "universal"])
    def test_localized_required_prompt_without_de_fr_warns(self, category: str) -> None:
        issues: list[Issue] = []

        check_locale_coverage([_prompt_file(category, "en", "")], issues)

        assert len(issues) == 1
        assert issues[0].level == "WARN"
        assert "Missing required locales: de, fr" in issues[0].message

    def test_feature_prompt_with_multiple_locales_still_reports_missing_locale(self) -> None:
        issues: list[Issue] = []

        check_locale_coverage(
            [_prompt_file("writing", "en", "test"), _prompt_file("writing", "de", "test")],
            issues,
        )

        assert len(issues) == 1
        assert issues[0].level == "WARN"
        assert "Missing locales: fr" in issues[0].message


class TestLocaleSyncPolicy:
    """Locale sync remains active for multi-locale feature prompt families."""

    def test_single_locale_feature_group_is_valid_no_drift(self, tmp_path: Path) -> None:
        _write_system_prompt(tmp_path, "writing/en/test/system.md", variables=("writing_language",))

        groups = discover_groups(tmp_path)
        report = check_sync(groups["writing/test"])

        assert report.synced
        assert report.variable_drifts == []

    def test_multi_locale_feature_group_keeps_variable_sync_active(
        self,
        tmp_path: Path,
    ) -> None:
        _write_system_prompt(
            tmp_path,
            "writing/en/test/system.md",
            variables=("writing_language", "user_preferences"),
        )
        _write_system_prompt(
            tmp_path,
            "writing/de/test/system.md",
            variables=("writing_language",),
        )

        groups = discover_groups(tmp_path)
        report = check_sync(groups["writing/test"])

        assert not report.synced
        assert any("user_preferences" in drift for drift in report.variable_drifts)


class TestArchitecturePromptI18nPolicy:
    """Architecture i18n checker follows prompt category policy."""

    def test_feature_en_only_prompt_has_no_architecture_exception(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path
        bundled = root / "packages/core/narrare_core/prompts/_bundled"
        _write_system_prompt(bundled, "writing/en/test/system.md")
        monkeypatch.setattr(_check_i18n, "ROOT", root)

        result = CheckResult()
        _check_i18n.check_prompt_i18n_completeness(result)

        assert result.approved_exceptions == []

    def test_meta_en_only_prompt_still_requires_locales(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path
        bundled = root / "packages/core/narrare_core/prompts/_bundled"
        _write_system_prompt(bundled, "meta/en/system.md")
        monkeypatch.setattr(_check_i18n, "ROOT", root)

        result = CheckResult()
        _check_i18n.check_prompt_i18n_completeness(result)

        details = [exception.detail for exception in result.approved_exceptions]
        assert any("DE counterpart missing" in detail for detail in details)
        assert any("FR counterpart missing" in detail for detail in details)
