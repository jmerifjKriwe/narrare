"""Narrare Architecture Constraint Checker — shared helpers."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

# Approval markers — if present in a comment near a violation line, it's an approved exception.
APPROVAL_MARKER = "# narrare: allow"
LEGACY_MARKER = "# narrare: allow-direct-llm"
AGENT_MARKER = "# narrare: allow-agent"


def load_config() -> dict[str, object]:
    """Load architecture config from pyproject.toml."""
    config_path = ROOT / "pyproject.toml"
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("narrare", {}).get("architecture", {})


def is_approved_exception(source_lines: list[str], lineno: int) -> tuple[bool, str]:
    """Check if the line or its preceding comment has an approval marker."""
    for check_line in range(max(0, lineno - 3), min(len(source_lines), lineno + 2)):
        line = source_lines[check_line]
        if APPROVAL_MARKER in line or LEGACY_MARKER in line or AGENT_MARKER in line:
            reason_start = line.find("reason=")
            reason = ""
            if reason_start != -1:
                reason = line[reason_start + 8 :].strip().strip('"').strip("'")
            return True, reason
    return False, ""


def compute_type_checking_lines(tree: ast.AST) -> set[int]:
    """Return line numbers inside ``if TYPE_CHECKING:`` blocks.

    Handles both ``if TYPE_CHECKING:`` and
    ``if typing.TYPE_CHECKING:`` forms.
    """
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if (isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING") or (
            isinstance(node.test, ast.Attribute)
            and isinstance(node.test.value, ast.Name)
            and node.test.value.id == "typing"
            and node.test.attr == "TYPE_CHECKING"
        ):
            for child in ast.walk(node):
                lineno = getattr(child, "lineno", None)
                if lineno is not None:
                    lines.add(lineno)
    return lines


def relative_to_root(path: Path) -> str:
    """Return a path string relative to the project root."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)
