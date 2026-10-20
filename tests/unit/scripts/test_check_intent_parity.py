"""Tests for scripts/check_intent_parity.py — intent-contract parity gate.

The mutation tests copy only the declaration files, the two governance YAML files
and the routed EN prompt templates into ``tmp_path`` (keeping the
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
_MANIFEST = Path("scripts/architecture/prompt-surface-manifest.yaml")
_REGISTRY = Path("scripts/architecture/adoption-registry.yaml")
_BUNDLED = _CORE / "prompts" / "_bundled"

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


def _prompt_files() -> list[Path]:
    """Return the EN system.md paths the routed intents resolve today."""
    facts = collect_facts(ROOT)
    paths: list[Path] = []
    for fact in facts["route_configs"].values():
        if fact.category is not None and fact.mode is not None:
            paths.append(_BUNDLED / fact.category / "en" / fact.mode / "system.md")
    return paths


def _copy_declaration_tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    copied = (*_DECLARATION_FILES, _MANIFEST, _REGISTRY, *_prompt_files())
    for relative in copied:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return root


def _replace(root: Path, relative: Path, old: str, new: str) -> None:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    assert old in text, f"mutation anchor missing from {relative}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _mutate(tmp_path: Path, relative: Path, old: str, new: str) -> Path:
    root = _copy_declaration_tree(tmp_path)
    _replace(root, relative, old, new)
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


# ── Prompt-directory family ────────────────────────────────────────────────


def test_missing_prompt_template_for_a_locale_is_reported(tmp_path: Path) -> None:
    root = _copy_declaration_tree(tmp_path)
    (root / _BUNDLED / "writing" / "en" / "new_chapter" / "system.md").unlink()

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message
        and "locale 'en'" in message
        and "writing/en/new_chapter/system.md" in message
        for message in messages
    ), messages


def test_missing_localized_prompt_template_names_that_locale(tmp_path: Path) -> None:
    root = _copy_declaration_tree(tmp_path)
    source = root / _BUNDLED / "writing" / "en" / "new_chapter" / "system.md"
    for locale in ("en", "de", "fr"):
        target = root / _BUNDLED / "universal" / locale / "new_chapter" / "system.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (root / _BUNDLED / "universal" / "de" / "new_chapter" / "system.md").unlink()
    _replace(
        root,
        _ROUTE_INTENTS,
        '    LLMIntent.WRITE: "writing",\n',
        '    LLMIntent.WRITE: "universal",\n',
    )
    _replace(
        root,
        _ROUTE_TABLE,
        '    LLMIntent.WRITE: PromptRouteConfig(\n        "writing",\n',
        '    LLMIntent.WRITE: PromptRouteConfig(\n        "universal",\n',
    )

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message
        and "locale 'de'" in message
        and "universal/de/new_chapter/system.md" in message
        for message in messages
    ), messages


def test_prompt_directories_exist_for_every_required_locale() -> None:
    messages = find_disagreements(collect_facts(ROOT))
    assert [message for message in messages if "prompt" in message and "locale" in message] == []


# ── Manifest-block family ──────────────────────────────────────────────────


def test_manifest_mode_mismatch_is_reported(tmp_path: Path) -> None:
    root = _mutate(
        tmp_path,
        _MANIFEST,
        "  - intent: WRITE\n    routeable: true\n    category: writing\n    mode: new_chapter\n",
        "  - intent: WRITE\n    routeable: true\n    category: writing\n    mode: other_mode\n",
    )

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message and "mode" in message and "prompt-surface-manifest.yaml" in message
        for message in messages
    ), messages


def test_manifest_block_missing_for_a_routed_intent_is_reported(tmp_path: Path) -> None:
    root = _mutate(
        tmp_path,
        _MANIFEST,
        "  - intent: WRITE\n    routeable: true\n",
        "  - intent: WRITE\n    routeable: false\n",
    )

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message
        and "missing block" in message
        and "prompt-surface-manifest.yaml" in message
        for message in messages
    ), messages


def test_manifest_block_for_an_unrouted_intent_is_reported(tmp_path: Path) -> None:
    root = _mutate(
        tmp_path,
        _MANIFEST,
        "  - intent: SENTIMENT\n    routeable: false\n",
        "  - intent: SENTIMENT\n    routeable: true\n    category: analysis\n    mode: sentiment\n",
    )

    messages = find_disagreements(collect_facts(root))

    assert any(
        "SENTIMENT" in message
        and "no route entry" in message
        and "prompt-surface-manifest.yaml" in message
        for message in messages
    ), messages


def test_duplicate_manifest_block_is_reported(tmp_path: Path) -> None:
    block = "  - intent: WRITE\n    routeable: true\n    category: writing\n    mode: new_chapter\n"
    root = _mutate(tmp_path, _MANIFEST, block, block + block)

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message and "duplicate" in message and "prompt-surface-manifest.yaml" in message
        for message in messages
    ), messages


def test_manifest_blocks_agree_with_the_route_table() -> None:
    messages = find_disagreements(collect_facts(ROOT))
    assert [message for message in messages if "prompt-surface-manifest.yaml" in message] == []


# ── Adoption-registry family ───────────────────────────────────────────────


def test_missing_adoption_registry_entry_is_reported(tmp_path: Path) -> None:
    root = _mutate(tmp_path, _REGISTRY, "  writing/new_chapter: true\n", "")

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message and "new_chapter" in message and "adoption-registry.yaml" in message
        for message in messages
    ), messages


def test_adoption_registry_entry_for_an_unknown_intent_is_reported(tmp_path: Path) -> None:
    root = _mutate(
        tmp_path,
        _REGISTRY,
        "prompt_path_compliance:\n",
        "prompt_path_compliance:\n  NOT_A_REAL_INTENT: true\n",
    )

    messages = find_disagreements(collect_facts(root))

    assert any(
        "NOT_A_REAL_INTENT" in message and "adoption-registry.yaml" in message
        for message in messages
    ), messages


def test_adoption_registry_covers_every_routed_intent() -> None:
    messages = find_disagreements(collect_facts(ROOT))
    assert [message for message in messages if "adoption-registry.yaml" in message] == []
