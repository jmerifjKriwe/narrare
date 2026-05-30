"""Helper utilities for prompt integrity tests.

Provides functions for:
- Discovering bundled prompt files
- Parsing YAML frontmatter from .md files
- Scanning Python source files for prompt-like string constants

All helpers are pure functions with no I/O side effects beyond reading
local files.  No LLM, DB, or network access required.
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# Project paths - resolved relative to this file
# _prompt_helpers.py lives at: tests/unit/architecture/_prompt_helpers.py
# Project root is 4 levels up.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BUNDLED_ROOT = PROJECT_ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
PROMPTS_DIR = PROJECT_ROOT / "packages" / "core" / "narrare_core" / "prompts"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_bundled_prompts() -> list[Path]:
    """Return all .md files under ``_bundled/``, sorted deterministically.

    Returns an empty list when the bundled-root directory does not exist
    (graceful degradation for partial checkouts).
    """
    if not BUNDLED_ROOT.is_dir():
        return []
    return sorted(BUNDLED_ROOT.rglob("*.md"))


def parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Parse simple YAML frontmatter delimited by ``---`` lines.

    Only handles flat ``key: value`` pairs — no nested structures.
    Quoted values (single or double) are unwrapped.

    Returns:
        ``(metadata, content_lines)`` where *metadata* is a dict of
        key-value pairs and *content_lines* are the lines after the
        closing ``---``.
    """
    if not lines or lines[0].strip() != "---":
        return {}, lines

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, lines

    metadata: dict[str, str] = {}
    for line in lines[1:end_idx]:
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip().strip('"').strip("'")

    return metadata, lines[end_idx + 1 :]


def find_prompt_constants(py_file: Path) -> list[tuple[str, int, str]]:
    """Find prompt-like string constants in a Python file.

    A "prompt-like constant" is a variable whose name contains
    ``PROMPT`` (case-insensitive) and whose string value exceeds 200
    characters.

    Covers both plain assignments (``X = "..."``) and annotated
    assignments (``X: str = "..."``).

    Returns:
        List of ``(variable_name, line_number, content)`` tuples.
    """
    try:
        source = py_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return []

    results: list[tuple[str, int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = _extract_string(node.value)
            if value is None or len(value) <= 200:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and "PROMPT" in target.id.upper():
                    results.append((target.id, node.lineno, value))

        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = _extract_string(node.value)
            if value is None or len(value) <= 200:
                continue
            if isinstance(node.target, ast.Name) and "PROMPT" in node.target.id.upper():
                results.append((node.target.id, node.lineno, value))

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_string(node: ast.expr) -> str | None:
    """Extract a string value from an AST node, if it is a string constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None
