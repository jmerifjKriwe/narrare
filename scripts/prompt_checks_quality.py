#!/usr/bin/env python3
"""
Prompt-quality checks for Narrare prompt structure validation.

Contains warning-level quality checks that extend the structural validator:
  - Do-NOT section item count (minimum 4 items)
  - JSON output schema presence for KB/Analysis prompts

Extracted into a separate module per RULE-04 (modularize, not compress —
adding these checks to prompt_checks.py would exceed the 300-line limit)
and RULE-06 (one responsibility per file).
"""

from __future__ import annotations

import re

from prompt_check_types import Issue, PromptFile
from prompt_checks import META_EXEMPT_TYPES, UNIVERSAL_EXEMPT_TYPES

# Minimum number of bullet items expected in a Do-NOT section.
MIN_DO_NOT_ITEMS = 4


# ── Checks ─────────────────────────────────────────────────────


def check_do_not_item_count(pf: PromptFile, issues: list[Issue]) -> None:
    """Check: Do-NOT section should contain at least 4 items.

    Counts bullet items (lines matching ``^\\s*-\\s+``) between the Do-NOT
    heading and the next heading at the same or higher level.  Warns if fewer
    than ``MIN_DO_NOT_ITEMS`` items are present.
    """
    if not pf.is_system_md:
        return
    if pf.prompt_type in META_EXEMPT_TYPES or pf.prompt_type in UNIVERSAL_EXEMPT_TYPES:
        return
    if pf.mode == "inline_suggest" or pf.path.parent.name == "inline_suggest":
        return

    lines = pf.content.splitlines()
    in_do_not = False
    do_not_level = 0
    item_count = 0

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+", line)
        if heading_match:
            level = len(heading_match.group(1))
            title = line[heading_match.end() :].lower()
            if not in_do_not and re.search(r"do\s+not|nicht|ne\s+pas", title):
                in_do_not = True
                do_not_level = level
                continue
            if in_do_not and level <= do_not_level:
                break
        elif in_do_not and re.match(r"^\s*-\s+", line):
            item_count += 1

    if in_do_not and item_count < MIN_DO_NOT_ITEMS:
        issues.append(
            Issue(
                "WARN",
                pf.display_path,
                f"Do-NOT section has only {item_count} items (minimum: {MIN_DO_NOT_ITEMS})",
            )
        )


def check_json_output_schema(pf: PromptFile, issues: list[Issue]) -> None:
    """Check: KB/Analysis prompts should include a JSON codeblock in Output Format.

    Only checks ``kb`` and ``analysis`` prompt types (structured-output
    categories).  If an Output Format heading exists but no fenced code block
    (tagged or untagged) containing JSON-like content (a line starting with
    ``{`` or ``[``) is found anywhere in the file, warns that an example
    object is missing.
    """
    if not pf.is_system_md:
        return
    if pf.prompt_type not in ("kb", "analysis"):
        return
    if pf.mode == "inline_suggest" or pf.path.parent.name == "inline_suggest":
        return

    headings_lower = [h.lower() for h in pf.headings]
    has_output = any(
        "output format" in h or "ausgabeformat" in h or "format de sortie" in h
        for h in headings_lower
    )
    if not has_output:
        return

    # Check for any fenced codeblock containing JSON-like content
    has_json = False
    in_block = False
    for line in pf.content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
        elif in_block and (stripped.startswith("{") or stripped.startswith("[")):
            has_json = True
            break

    if not has_json:
        issues.append(
            Issue(
                "WARN",
                pf.display_path,
                "Output Format section lacks a JSON codeblock with example object",
            )
        )
