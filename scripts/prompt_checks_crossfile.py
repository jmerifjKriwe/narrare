#!/usr/bin/env python3
"""
Cross-file prompt checks for Narrare prompt structure validation.

Contains checks that operate across multiple prompt files (locale coverage,
meta-prompt guardrails).  Extracted from prompt_checks.py per RULE-04
(modularize, not compress — original file exceeded 400-line limit).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from prompt_check_types import Issue, PromptFile, parse_prompt_file

if TYPE_CHECKING:
    from pathlib import Path

# ── Constants ──────────────────────────────────────────────────

_SUPPORTED_PROMPT_LOCALES: frozenset[str] = frozenset({"en", "de", "fr"})
_LOCALIZED_REQUIRED_CATEGORIES: frozenset[str] = frozenset({"meta", "universal", "universal_rules"})

# Mandatory keywords for meta prompts (ADR-019).
_META_MANDATORY_PATTERNS: list[tuple[str, str]] = [
    ("fiction|narrative|fiktion|narratif|ficti", "fiction/narrative content guidance"),
    ("avoidance_patterns", "{{avoidance_patterns}} variable"),
    (
        r"user_provided_text|user_provided_data|user_instructions|nutzerinhalte|contenu.*balisé",
        "content security (XML-tagged user content)",
    ),
]


# ── Cross-file checks ─────────────────────────────────────────


def check_locale_coverage(prompts: list[PromptFile], issues: list[Issue]) -> None:
    """Check 6: Locale coverage according to ADR-026 Phase 5 policy.

    Bundled feature system prompts are EN-only by default. Meta and universal
    capability prompts remain localized-required because persona, security, and
    interaction wording can be language-sensitive. Feature prompt families that
    already include multiple bundled locales are still checked for complete
    locale coverage so accidental partial localized families stay visible.
    """

    # Group system.md files by (category, mode, variant).
    groups: dict[str, dict[str, PromptFile]] = {}
    for pf in prompts:
        if not pf.is_system_md or not pf.locale:
            continue
        key = pf.group_key
        if pf.variant:
            key += f"/{pf.variant}"
        groups.setdefault(key, {})[pf.locale] = pf

    for key, locale_files in sorted(groups.items()):
        present_locales = set(locale_files.keys())
        missing = _SUPPORTED_PROMPT_LOCALES - present_locales

        if not missing:
            continue

        category = key.split("/", maxsplit=1)[0]

        if category not in _LOCALIZED_REQUIRED_CATEGORIES and present_locales == {"en"}:
            continue

        if category in _LOCALIZED_REQUIRED_CATEGORIES:
            missing_str = ", ".join(sorted(missing))
            issues.append(
                Issue(
                    "WARN",
                    f"{key}/en",
                    f"Missing required locales: {missing_str} "
                    f"(localized prompt family requires en/de/fr)",
                )
            )
            continue

        missing_str = ", ".join(sorted(missing))
        present_str = ", ".join(sorted(present_locales))
        issues.append(
            Issue(
                "WARN",
                f"{key}/{present_str}",
                f"Missing locales: {missing_str} (has {present_str})",
            )
        )


def check_meta_guardrails(prompts: list[PromptFile], issues: list[Issue]) -> None:
    """Check 7: Meta-prompt guardrails per ADR-019."""
    for pf in prompts:
        if not pf.is_system_md or pf.prompt_type != "meta":
            continue

        content_lower = pf.content.lower()

        for pattern, description in _META_MANDATORY_PATTERNS:
            if not re.search(pattern, content_lower, re.IGNORECASE):
                issues.append(
                    Issue(
                        "WARN",
                        pf.display_path,
                        f"Meta-prompt missing ADR-019 mandatory element: {description}",
                    )
                )


# ── Discovery ──────────────────────────────────────────────────


def discover_prompts(bundled_dir: Path) -> list[PromptFile]:
    """Discover all .md files in the bundled prompts directory."""
    prompts: list[PromptFile] = []
    for md_file in sorted(bundled_dir.rglob("*.md")):
        prompts.append(parse_prompt_file(md_file, bundled_dir))
    return prompts
