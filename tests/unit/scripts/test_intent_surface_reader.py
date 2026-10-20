"""Tests for ``scripts/_intent_surface_reader.py`` — the shared AST/YAML readers."""

from __future__ import annotations

import ast

from scripts._intent_surface_reader import dict_entries, string_value


def test_dict_entries_applies_post_literal_writes_and_deletes() -> None:
    """Literal entries, then last write wins, then deletions win."""
    tree = ast.parse(
        'INTENT_TO_MODE = {LLMIntent.WRITE: "new_chapter", "KB_IMPROVE": "improve"}\n'
        'INTENT_TO_MODE[LLMIntent.WRITE] = "other_mode"\n'
        'INTENT_TO_MODE["KB_IMPROVE"] = "enhance"\n'
        'del INTENT_TO_MODE["KB_IMPROVE"]\n'
        'INTENT_TO_MODE[LLMIntent.KB_CREATE] = "create"\n'
        'INTENT_TO_MODE[UNRECOGNISED_KEY] = "ignored"\n'
    )

    entries = dict_entries(tree, "INTENT_TO_MODE")

    assert set(entries) == {"WRITE", "KB_CREATE"}
    assert string_value(entries["WRITE"]) == "other_mode"


def test_dict_entries_ignores_reads_and_other_variables() -> None:
    """Only writes and deletes of the named module-level mapping change the result."""
    tree = ast.parse(
        'INTENT_TO_MODE = {LLMIntent.WRITE: "new_chapter"}\n'
        'OTHER[LLMIntent.WRITE] = "other_mode"\n'
        "value = INTENT_TO_MODE[LLMIntent.WRITE]\n"
        'INTENT_TO_MODE[LLMIntent.EXTEND] = "extend_chapter"\n'
    )

    entries = dict_entries(tree, "INTENT_TO_MODE")

    assert set(entries) == {"WRITE", "EXTEND"}
    assert string_value(entries["WRITE"]) == "new_chapter"
