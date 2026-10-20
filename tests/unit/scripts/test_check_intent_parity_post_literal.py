"""Post-literal mutations of a module-level intent mapping (gate level).

The gate must compare declarations written after the dict literal too:
``INTENT_TO_MODE[X] = ...`` and ``del INTENT_TO_MODE[X]``. Each test copies only
the declaration files, the two governance YAML files and the routed EN prompt
templates into ``tmp_path``, appends the mutation to the copy, and runs the real
comparison; the real tree is never touched.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from scripts.check_intent_parity import collect_facts, find_disagreements

ROOT = Path(__file__).resolve().parents[3]

_CORE = Path("packages/core/narrare_core")
_DECLARATION_FILES = (
    _CORE / "llm" / "intents" / "_enums.py",
    _CORE / "llm" / "intent_categories.py",
    _CORE / "llm" / "intent_profiles.py",
    _CORE / "prompts" / "route_table_intents.py",
    _CORE / "prompts" / "route_table.py",
)
_ROUTE_INTENTS = _CORE / "prompts" / "route_table_intents.py"
_MANIFEST = Path("scripts/architecture/prompt-surface-manifest.yaml")
_REGISTRY = Path("scripts/architecture/adoption-registry.yaml")
_BUNDLED = _CORE / "prompts" / "_bundled"


def _prompt_files() -> list[Path]:
    """Return the EN system.md paths the routed intents resolve today."""
    paths: list[Path] = []
    for fact in collect_facts(ROOT)["route_configs"].values():
        if fact.category is not None and fact.mode is not None:
            paths.append(_BUNDLED / fact.category / "en" / fact.mode / "system.md")
    return paths


def _append(tmp_path: Path, text: str) -> Path:
    """Copy the declaration tree and append *text* to ``route_table_intents.py``."""
    root = tmp_path / "tree"
    for relative in (*_DECLARATION_FILES, _MANIFEST, _REGISTRY, *_prompt_files()):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    surface = root / _ROUTE_INTENTS
    surface.write_text(surface.read_text(encoding="utf-8") + text, encoding="utf-8")
    return root


def test_post_literal_mode_override_is_reported(tmp_path: Path) -> None:
    """A write after the dict literal is a declaration the gate must compare."""
    root = _append(tmp_path, '\nINTENT_TO_MODE[LLMIntent.WRITE] = "other_mode"\n')

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message
        and "mode" in message
        and "route_intents" in message
        and "route_configs" in message
        and "other_mode" in message
        for message in messages
    ), messages


def test_post_literal_mode_entry_without_a_route_mode_is_reported(tmp_path: Path) -> None:
    """Presence direction: KB_CREATE has no default mode, so a late entry contradicts it."""
    root = _append(tmp_path, '\nINTENT_TO_MODE[LLMIntent.KB_CREATE] = "create"\n')

    messages = find_disagreements(collect_facts(root))

    assert any(
        "KB_CREATE" in message
        and "INTENT_TO_MODE" in message
        and "route_configs" in message
        and "no mode" in message
        for message in messages
    ), messages


def test_post_literal_mode_deletion_is_reported(tmp_path: Path) -> None:
    """A `del` after the literal removes a declaration the route table still needs."""
    root = _append(tmp_path, "\ndel INTENT_TO_MODE[LLMIntent.WRITE]\n")

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message
        and "missing from 'INTENT_TO_MODE'" in message
        and "route_configs" in message
        and "new_chapter" in message
        for message in messages
    ), messages


def test_post_literal_category_override_is_reported(tmp_path: Path) -> None:
    root = _append(tmp_path, '\nINTENT_TO_CATEGORY[LLMIntent.WRITE] = "analysis"\n')

    messages = find_disagreements(collect_facts(root))

    assert any(
        "WRITE" in message
        and "category" in message
        and "route_intents" in message
        and "route_configs" in message
        and "analysis" in message
        for message in messages
    ), messages
