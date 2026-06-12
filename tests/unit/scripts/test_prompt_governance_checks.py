"""Tests for CR-01 prompt governance gates."""
# ruff: noqa: E402, I001

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = str(_ROOT / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from narrare_core.prompts.variable_registry import USER_CONTENT_VARS

from check_prompt_structure import BUNDLED_DIR, collect_issues
from prompt_check_types import Issue, PromptFile
from prompt_checks import check_security
from prompt_vars import UNSAFE_USER_VARS


def _prompt_file(content: str, *, category: str = "kb", mode: str = "consistency") -> PromptFile:
    return PromptFile(
        path=Path(f"_bundled/{category}/en/{mode}/system.md"),
        rel_path=f"{category}/en/{mode}/system.md",
        content=content,
        variables=set(),
        category=category,
        locale="en",
        mode=mode,
    )


def _security_issues(
    content: str, *, category: str = "kb", mode: str = "consistency"
) -> list[Issue]:
    pf = _prompt_file(content, category=category, mode=mode)
    issues: list[Issue] = []
    check_security(pf, issues)
    return issues


def test_unsafe_user_vars_are_derived_from_user_content_vars_ssot() -> None:
    assert UNSAFE_USER_VARS == USER_CONTENT_VARS


def test_unwrapped_entity_name_fails() -> None:
    issues = _security_issues("## System Prompt\nEntity: {{entity_name}}")

    assert any(issue.level == "FAIL" and "entity_name" in issue.message for issue in issues)


def test_entity_name_wrapped_in_approved_tag_passes() -> None:
    issues = _security_issues(
        "## System Prompt\nEntity: <user_provided_data>{{entity_name}}</user_provided_data>"
    )

    assert not issues


def test_entity_name_wrapped_in_non_standard_tag_fails() -> None:
    issues = _security_issues("## System Prompt\n<entity>{{entity_name}}</entity>")

    assert any("non-standard XML wrapper <entity>" in issue.message for issue in issues)


def test_language_in_bundled_system_prompt_fails() -> None:
    issues = _security_issues("## System Prompt\nWrite in {{language}}.")

    assert any("Deprecated {{language}}" in issue.message for issue in issues)


def test_kb_suggested_without_full_precedence_wording_fails() -> None:
    issues = _security_issues(
        "## System Prompt\n### Suggested KB Entries\nUseful context:\n{{kb_suggested}}",
        category="writing",
        mode="extend_chapter",
    )

    assert any(
        "kb_suggested" in issue.message and "precedence wording" in issue.message
        for issue in issues
    )


def test_current_bundled_prompts_pass_strict_prompt_checks() -> None:
    _total, _system_count, issues = collect_issues(BUNDLED_DIR)

    assert issues == []
