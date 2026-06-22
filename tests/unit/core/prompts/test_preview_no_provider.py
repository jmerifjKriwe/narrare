"""PROMPT-003 invariant: preview modules must not import LLM providers."""

from __future__ import annotations

import ast
from pathlib import Path

_PREVIEW_MODULES = (
    Path("packages/core/narrare_core/prompts/preview.py"),
    Path("packages/core/narrare_core/prompts/preview_types.py"),
    Path("packages/core/narrare_core/prompts/contracts.py"),
)
_FORBIDDEN_MODULES = {
    "narrare_core.llm.gateway",
    "narrare_core.agents",
    "openai",
    "anthropic",
    "google.generativeai",
}


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.add(node.module.split(".")[0])
    return imported


def test_preview_modules_do_not_import_providers() -> None:
    root = Path(__file__).parents[4]
    for rel_path in _PREVIEW_MODULES:
        source = (root / rel_path).read_text(encoding="utf-8")
        violations = _imported_modules(source) & _FORBIDDEN_MODULES
        assert not violations, f"{rel_path} imports forbidden modules: {violations}"
