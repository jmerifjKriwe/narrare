"""Tests for _check_required_vars() tiered Issue generation.

Covers:
1. Tier 1 — Missing base MUST vars → WARN-level Issues
2. Tier 2 — Missing mode-specific MUST vars → FAIL-level Issues
3. Tier 3 — Missing SHOULD vars → WARN with '(SHOULD)' suffix
4. All present — When all tiers satisfied, no Issues generated
5. Combined — Multiple tiers producing issues simultaneously

ADR-025 Phase 1 is the authoritative source for these definitions.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import setup: prompt_checks.py uses ``from prompt_vars import ...`` so the
# scripts/ directory must be on sys.path for the relative import to resolve.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[3] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# Now import from the bare module names (same as check_prompt_structure does).
import prompt_vars  # noqa: E402
from prompt_checks import Issue, PromptFile, _check_required_vars  # noqa: E402

# =====================================================================
# Fixtures
# =====================================================================


def _make_prompt_file(
    *,
    category: str = "writing",
    locale: str = "en",
    mode: str = "",
    variables: set[str] | None = None,
) -> PromptFile:
    """Create a PromptFile with sensible defaults for testing."""
    return PromptFile(
        path=Path(f"_bundled/{category}/{locale}/{mode}/system.md".replace("//", "/")),
        rel_path=f"{category}/{locale}/{mode}/system.md".replace("//", "/"),
        category=category,
        locale=locale,
        mode=mode,
        variables=variables if variables is not None else set(),
    )


# =====================================================================
# 1. Tier 1: Base MUST vars
# =====================================================================


class TestCheckRequiredVarsBaseMust:
    """Tier 1: Missing base MUST vars → WARN-level Issues."""

    def test_missing_base_must_var_generates_warn(self) -> None:
        pf = _make_prompt_file(
            category="writing",
            variables={"user_preferences"},  # missing avoidance_patterns + KB vars
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing", issues)

        warn_messages = [i.message for i in issues if i.level == "WARN"]
        assert any("avoidance_patterns" in m and "required" in m for m in warn_messages)

    def test_all_base_vars_present_no_must_issues(self) -> None:
        all_writing_vars = prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]
        pf = _make_prompt_file(
            category="writing",
            variables=all_writing_vars,
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing", issues)

        # No "required variable" issues for base vars
        base_issues = [
            i
            for i in issues
            if "required variable" in i.message and "mode" not in i.message.lower()
        ]
        assert len(base_issues) == 0

    def test_unknown_category_no_base_issues(self) -> None:
        pf = _make_prompt_file(category="wiki", variables=set())
        issues: list[Issue] = []
        _check_required_vars(pf, "wiki", issues)

        # wiki is not in REQUIRED_VARS_BY_CATEGORY, so no base issues
        base_issues = [
            i
            for i in issues
            if "required variable" in i.message and "mode" not in i.message.lower()
        ]
        assert len(base_issues) == 0

    def test_issue_includes_category_name(self) -> None:
        pf = _make_prompt_file(category="writing", variables=set())
        issues: list[Issue] = []
        _check_required_vars(pf, "writing", issues)

        assert any("category 'writing'" in i.message for i in issues)


# =====================================================================
# 2. Tier 2: Mode-specific MUST vars
# =====================================================================


class TestCheckRequiredVarsModeSpecific:
    """Tier 2: Missing mode-specific MUST vars → FAIL-level Issues."""

    def test_extend_chapter_missing_existing_content_fails(self) -> None:
        pf = _make_prompt_file(
            category="writing",
            mode="extend_chapter",
            variables=prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"],
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing/extend_chapter", issues)

        fail_issues = [i for i in issues if i.level == "FAIL"]
        assert len(fail_issues) >= 1
        assert any("existing_content" in i.message for i in fail_issues)

    def test_rewrite_selection_missing_vars_fails(self) -> None:
        pf = _make_prompt_file(
            category="writing",
            mode="rewrite_selection",
            variables=prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"],
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing/rewrite_selection", issues)

        fail_issues = [i for i in issues if i.level == "FAIL"]
        fail_messages = [i.message for i in fail_issues]
        assert any("selection_text" in m for m in fail_messages)
        assert any("context_before" in m for m in fail_messages)
        assert any("context_after" in m for m in fail_messages)

    def test_mode_vars_present_no_mode_issues(self) -> None:
        all_vars = prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"] | {"existing_content"}
        pf = _make_prompt_file(
            category="writing",
            mode="extend_chapter",
            variables=all_vars,
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing/extend_chapter", issues)

        fail_issues = [i for i in issues if i.level == "FAIL"]
        assert len(fail_issues) == 0

    def test_no_mode_no_mode_issues(self) -> None:
        """When mode is empty, no mode-specific checks run."""
        pf = _make_prompt_file(
            category="writing",
            mode="",
            variables=set(),
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing", issues)

        fail_issues = [i for i in issues if i.level == "FAIL"]
        assert len(fail_issues) == 0

    def test_issue_includes_mode_name(self) -> None:
        pf = _make_prompt_file(
            category="writing",
            mode="rewrite_selection",
            variables=prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"],
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing/rewrite_selection", issues)

        fail_issues = [i for i in issues if i.level == "FAIL"]
        assert any("mode 'rewrite_selection'" in i.message for i in fail_issues)


# =====================================================================
# 3. Tier 3: SHOULD vars
# =====================================================================


class TestCheckRequiredVarsShould:
    """Tier 3: Missing SHOULD vars → WARN with '(SHOULD)' suffix."""

    def test_missing_should_var_generates_warn(self) -> None:
        pf = _make_prompt_file(
            category="writing",
            variables=prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"],
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing", issues)

        should_issues = [i for i in issues if "SHOULD" in i.message]
        assert len(should_issues) >= 1
        # SHOULD issues are WARN, not FAIL
        assert all(i.level == "WARN" for i in should_issues)

    def test_should_issue_message_contains_suffix(self) -> None:
        pf = _make_prompt_file(
            category="writing",
            variables=prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"],
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing", issues)

        should_issues = [i for i in issues if "SHOULD" in i.message]
        assert any("character_voice_profiles" in i.message for i in should_issues)
        assert any("kb_suggested" in i.message for i in should_issues)

    def test_should_vars_present_no_should_issues(self) -> None:
        all_vars = (
            prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]
            | prompt_vars.SHOULD_VARS_BY_CATEGORY["writing"]
        )
        pf = _make_prompt_file(category="writing", variables=all_vars)
        issues: list[Issue] = []
        _check_required_vars(pf, "writing", issues)

        should_issues = [i for i in issues if "SHOULD" in i.message]
        assert len(should_issues) == 0

    def test_analysis_should_vars(self) -> None:
        pf = _make_prompt_file(
            category="analysis",
            variables=prompt_vars.REQUIRED_VARS_BY_CATEGORY["analysis"],
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "analysis", issues)

        should_issues = [i for i in issues if "SHOULD" in i.message]
        should_messages = [i.message for i in should_issues]
        assert any("kb_characters" in m for m in should_messages)
        assert any("kb_locations" in m for m in should_messages)
        assert any("kb_factions" in m for m in should_messages)
        assert any("kb_relationships" in m for m in should_messages)

    def test_kb_should_have_world_context(self) -> None:
        pf = _make_prompt_file(
            category="kb",
            variables=prompt_vars.REQUIRED_VARS_BY_CATEGORY["kb"],
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "kb", issues)

        should_issues = [i for i in issues if "SHOULD" in i.message]
        assert any("world_context" in i.message for i in should_issues)


# =====================================================================
# 4. All tiers satisfied
# =====================================================================


class TestCheckRequiredVarsAllPresent:
    """When all tiers are satisfied, no Issues are generated."""

    def test_all_vars_present_no_issues_at_all(self) -> None:
        """Writing with all vars (base + mode + should) produces zero issues."""
        all_vars = (
            prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]
            | prompt_vars.MODE_REQUIRED_VARS["writing"]["extend_chapter"]
            | prompt_vars.SHOULD_VARS_BY_CATEGORY["writing"]
        )
        pf = _make_prompt_file(
            category="writing",
            mode="extend_chapter",
            variables=all_vars,
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing/extend_chapter", issues)

        assert len(issues) == 0


# =====================================================================
# 5. Combined tiers
# =====================================================================


class TestCheckRequiredVarsCombinedTiers:
    """Multiple tiers can produce issues simultaneously."""

    def test_missing_base_and_mode_and_should(self) -> None:
        """All three tiers generate issues when all are missing."""
        pf = _make_prompt_file(
            category="writing",
            mode="rewrite_selection",
            variables=set(),
        )
        issues: list[Issue] = []
        _check_required_vars(pf, "writing/rewrite_selection", issues)

        # Base MUST → WARN
        base_warns = [
            i
            for i in issues
            if i.level == "WARN" and "required variable" in i.message and "mode" not in i.message
        ]
        assert len(base_warns) >= 1

        # Mode-specific → FAIL
        mode_fails = [i for i in issues if i.level == "FAIL"]
        assert len(mode_fails) >= 3  # selection_text, context_before, context_after

        # SHOULD → WARN with suffix
        should_warns = [i for i in issues if "SHOULD" in i.message]
        assert len(should_warns) >= 1
