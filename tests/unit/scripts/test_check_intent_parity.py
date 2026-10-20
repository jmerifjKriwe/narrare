"""Tests for scripts/check_intent_parity.py — intent-contract parity gate (T14a).

The mutation tests copy only the declaration files into ``tmp_path`` (keeping the
repository-relative directory shape) and mutate the copy; the real tree is never
touched.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from scripts.check_intent_parity import collect_facts, find_disagreements

ROOT = Path(__file__).resolve().parents[3]

_CORE = Path("packages/core/narrare_core")
_ENUMS = _CORE / "llm" / "intents" / "_enums.py"
_CATEGORIES = _CORE / "llm" / "intent_categories.py"
_PROFILES = _CORE / "llm" / "intent_profiles.py"
_ROUTE_INTENTS = _CORE / "prompts" / "route_table_intents.py"
_ROUTE_TABLE = _CORE / "prompts" / "route_table.py"
_DECLARATION_FILES = (_ENUMS, _CATEGORIES, _PROFILES, _ROUTE_INTENTS, _ROUTE_TABLE)

Facts = dict[str, dict[str, dict[str, str | None]]]


def _facts(**overrides: dict[str, dict[str, str | None]]) -> Facts:
    base: Facts = {
        "enums": {"WRITE": {"category": "writing", "mode": "new_chapter"}},
        "categories": {"WRITE": {"category": "writing", "mode": None}},
        "route_intents": {"WRITE": {"category": "writing", "mode": "new_chapter"}},
        "route_configs": {"WRITE": {"category": None, "mode": "new_chapter"}},
        "profiles": {"WRITE": {"category": None, "mode": None}},
    }
    base.update(overrides)
    return base


def test_agreeing_surfaces_produce_no_disagreement() -> None:
    assert find_disagreements(_facts()) == []


def test_enum_without_a_category_entry_is_reported() -> None:
    assert find_disagreements(_facts(categories={})) != []


def test_category_mismatch_between_two_surfaces_is_reported() -> None:
    bad = _facts(route_intents={"WRITE": {"category": "analysis", "mode": "new_chapter"}})
    assert any("WRITE" in d for d in find_disagreements(bad))


def test_mode_mismatch_between_two_surfaces_is_reported() -> None:
    bad = _facts(route_configs={"WRITE": {"category": None, "mode": "other_mode"}})
    assert any("mode" in d for d in find_disagreements(bad))


def test_real_tree_has_no_disagreements() -> None:
    assert find_disagreements(collect_facts(ROOT)) == []


def _copy_declaration_tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    for relative in _DECLARATION_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root


def _mutate(tmp_path: Path, relative: Path, old: str, new: str) -> Path:
    root = _copy_declaration_tree(tmp_path)
    path = root / relative
    text = path.read_text(encoding="utf-8")
    assert old in text, f"mutation anchor missing from {relative}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return root


def test_dropping_a_enum_member_is_reported(tmp_path: Path) -> None:
    root = _mutate(tmp_path, _ENUMS, '    WRITE = "write"\n', '    WRITE_ALIAS = "write"\n')
    messages = find_disagreements(collect_facts(root))
    assert any(
        "WRITE" in message and "enums" in message and "categories" in message
        for message in messages
    ), messages


def test_changing_a_category_is_reported(tmp_path: Path) -> None:
    root = _mutate(
        tmp_path,
        _ROUTE_INTENTS,
        '    LLMIntent.WRITE: "writing",\n',
        '    LLMIntent.WRITE: "analysis",\n',
    )
    messages = find_disagreements(collect_facts(root))
    assert any(
        "WRITE" in message
        and "category" in message
        and "route_intents" in message
        and "route_configs" in message
        for message in messages
    ), messages


def test_changing_a_mode_is_reported(tmp_path: Path) -> None:
    root = _mutate(
        tmp_path,
        _ROUTE_TABLE,
        '    LLMIntent.WRITE: PromptRouteConfig(\n        "writing",\n        "new_chapter",\n',
        '    LLMIntent.WRITE: PromptRouteConfig(\n        "writing",\n        "other_mode",\n',
    )
    messages = find_disagreements(collect_facts(root))
    assert any(
        "WRITE" in message
        and "mode" in message
        and "route_intents" in message
        and "route_configs" in message
        for message in messages
    ), messages
