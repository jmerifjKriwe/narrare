#!/usr/bin/env python3
"""Prompt governance checks for bundled prompt validation.

This module owns CR-01 content/security gates that go beyond structural
frontmatter checks: user-content wrapper vocabulary, deprecated prompt variables,
and generated-suggestion precedence wording.
"""

from __future__ import annotations

import re

from prompt_check_types import Issue, PromptFile
from prompt_vars import UNSAFE_USER_VARS

APPROVED_USER_CONTENT_WRAPPER_TAGS = frozenset(
    {"user_provided_text", "user_provided_data", "user_instructions"}
)


def check_prompt_governance(pf: PromptFile, issues: list[Issue]) -> None:
    """Run CR-01 prompt governance checks for a bundled system prompt."""
    if not pf.is_system_md:
        return

    check_user_content_wrapping(pf, issues)
    check_deprecated_language_variable(pf, issues)
    check_kb_suggested_precedence(pf, issues)


def check_user_content_wrapping(pf: PromptFile, issues: list[Issue]) -> None:
    """Require every user-content variable occurrence to use an approved XML tag."""
    for var in sorted(UNSAFE_USER_VARS):
        var_pattern = re.compile(r"\{\{" + re.escape(var) + r"\}\}")
        for match in var_pattern.finditer(pf.content):
            tag = _direct_xml_wrapper_tag(pf.content, match.start(), match.end())
            line_no = _line_number(pf.content, match.start())

            if tag is None:
                issues.append(
                    Issue(
                        "FAIL",
                        pf.display_path,
                        f"Variable {{{{{var}}}}} on line {line_no} is not wrapped "
                        "in XML tags (user-content must use "
                        f"one of: {_approved_tags_display()})",
                    )
                )
                continue

            if tag not in APPROVED_USER_CONTENT_WRAPPER_TAGS:
                issues.append(
                    Issue(
                        "FAIL",
                        pf.display_path,
                        f"Variable {{{{{var}}}}} on line {line_no} uses non-standard "
                        f"XML wrapper <{tag}> (approved tags: {_approved_tags_display()})",
                    )
                )


def check_deprecated_language_variable(pf: PromptFile, issues: list[Issue]) -> None:
    """Disallow deprecated {{language}} in bundled system prompts."""
    for match in re.finditer(r"\{\{language\}\}", pf.content):
        line_no = _line_number(pf.content, match.start())
        issues.append(
            Issue(
                "FAIL",
                pf.display_path,
                f"Deprecated {{{{language}}}} on line {line_no}; use "
                "{{writing_language}} in bundled system prompts",
            )
        )


def check_kb_suggested_precedence(pf: PromptFile, issues: list[Issue]) -> None:
    """Require generated-suggestion precedence wording near {{kb_suggested}}."""
    for match in re.finditer(r"\{\{kb_suggested\}\}", pf.content):
        section = _section_around_offset(pf.content, match.start())
        missing = _missing_kb_suggested_requirements(section)
        if not missing:
            continue

        line_no = _line_number(pf.content, match.start())
        issues.append(
            Issue(
                "FAIL",
                pf.display_path,
                f"{{{{kb_suggested}}}} on line {line_no} lacks required "
                "generated-suggestion precedence wording nearby "
                f"(missing: {', '.join(missing)})",
            )
        )


def _direct_xml_wrapper_tag(content: str, start: int, end: int) -> str | None:
    """Return the direct XML wrapper tag around an occurrence, if present."""
    left = content[:start]
    right = content[end:]
    open_match = re.search(r"<([A-Za-z][\w:-]*)(?:\s+[^<>]*)?>\s*$", left)
    close_match = re.match(r"\s*</([A-Za-z][\w:-]*)>", right)
    if open_match is None or close_match is None:
        return None

    open_tag = open_match.group(1)
    close_tag = close_match.group(1)
    if open_tag != close_tag:
        return None
    return open_tag


def _section_around_offset(content: str, offset: int) -> str:
    """Return the markdown section containing the offset."""
    line_starts = [0]
    for match in re.finditer(r"\n", content):
        line_starts.append(match.end())

    current_line_index = max(i for i, start in enumerate(line_starts) if start <= offset)
    lines = content.splitlines()

    start_line = current_line_index
    while start_line > 0 and not re.match(r"^#{1,6}\s+", lines[start_line]):
        start_line -= 1

    end_line = current_line_index + 1
    while end_line < len(lines) and not re.match(r"^#{1,6}\s+", lines[end_line]):
        end_line += 1

    return "\n".join(lines[start_line:end_line])


def _missing_kb_suggested_requirements(section: str) -> list[str]:
    normalized = " ".join(section.lower().replace("-", " ").split())
    requirements = {
        "generated": "generated" in normalized,
        "unaccepted": "unaccepted" in normalized or "not accepted" in normalized,
        "lower-priority": "lower priority" in normalized,
        "no-override": _has_no_override_wording(normalized),
        "author instructions": "author instruction" in normalized,
        "curated KB": "curated" in normalized and "kb" in normalized,
        "current context": "current" in normalized and "context" in normalized,
    }
    return [label for label, present in requirements.items() if not present]


def _has_no_override_wording(normalized: str) -> bool:
    if "override" not in normalized:
        return False
    return any(marker in normalized for marker in ("not override", "never override", "no override"))


def _line_number(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def _approved_tags_display() -> str:
    return ", ".join(f"<{tag}>" for tag in sorted(APPROVED_USER_CONTENT_WRAPPER_TAGS))
