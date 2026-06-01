#!/usr/bin/env python3
"""
Variable-map constants for Narrare prompt structure validation.

Defines tiered variable requirements (MUST / mode-specific / SHOULD) per
prompt category, plus the set of user-content variables that require
XML-wrapping for injection safety.

Extracted from prompt_checks.py per RULE-04 (modularize, not compress).

ADR-025 Decision 2 is the authoritative source for these definitions.
"""

from __future__ import annotations

# ── MUST: Base variables required per category ──────────────────
# WARN level when missing — existing behaviour preserved.
REQUIRED_VARS_BY_CATEGORY: dict[str, set[str]] = {
    "writing": {
        "user_preferences",
        "avoidance_patterns",
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_relationships",  # NEW: catches the gap from FIND-009
        "culture_guidelines",
    },
    "kb": {"user_preferences", "avoidance_patterns"},
    "analysis": {"user_preferences", "avoidance_patterns"},
    "planning": {"user_preferences", "avoidance_patterns", "culture_guidelines"},
    "generation": {"user_preferences", "avoidance_patterns"},
    "chat": {"user_preferences", "avoidance_patterns"},
}

# ── MUST: Mode-specific additions (added ON TOP of category base) ──
# Only modes listed here have extra requirements beyond the category base.
# FAIL level when missing — mode-specific vars are hard requirements.
MODE_REQUIRED_VARS: dict[str, dict[str, set[str]]] = {
    "writing": {
        "extend_chapter": {"existing_content"},
        "extend": {"existing_content"},
        "rewrite_selection": {"selection_text", "context_before", "context_after"},
    },
}

# ── EXEMPT: Modes that intentionally skip certain category-required vars ──
# These modes have legitimate reasons to omit certain variables.
# The validator will suppress WARN-level messages for exempted combinations.
MODE_EXEMPT_VARS: dict[str, dict[str, set[str]]] = {
    "writing": {
        "inline_suggest": {"kb_characters", "kb_locations", "kb_factions", "kb_relationships"},
    },
    "analysis": {
        "consistency": {"kb_characters", "kb_locations", "kb_factions", "kb_relationships"},
        "preferences": {"kb_characters", "kb_locations", "kb_factions", "kb_relationships"},
        "remap": {"kb_characters", "kb_locations", "kb_factions", "kb_relationships"},
    },
    "kb": {
        "consistency": {"world_context"},
    },
}

# ── SHOULD: Recommended variables (warn, don't fail) ───────────
SHOULD_VARS_BY_CATEGORY: dict[str, set[str]] = {
    "writing": {"character_voice_profiles"},
    "analysis": {"kb_characters", "kb_locations", "kb_factions", "kb_relationships"},
    "kb": {"world_context"},
}

# ── Security: User-content variables that MUST be XML-wrapped ──
UNSAFE_USER_VARS = frozenset(
    {
        "existing_content",
        "chapter_text",
        "entry_content",
        "selection_text",
        "context_before",
        "context_after",
        "text_before",
        "text_after",
        "author_instructions",
        "conversation_history",
        "existing_answers",
    }
)
