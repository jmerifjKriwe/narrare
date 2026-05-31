"""RULE-INLINE · Inline prompt strings >100 chars must be registered.

Detects unregistered inline prompt strings in Python files outside
``core/prompts/`` and test directories.  Registered inline fallbacks
(from ``adoption-registry.yaml``) are emitted as approved exceptions.

ADR-025 Decision 4 is the authoritative specification.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import yaml
from scripts.architecture.types import Violation

# ── Constants ──────────────────────────────────────────────────────

_MIN_LENGTH = 100

_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\byou are\b",
        r"\byour task\b",
        r"\byour job\b",
        r"\byour role\b",
        r"\bact as\b",
        r"\byou work\b",
        r"\bsystem prompt\b",
        r"\byou are an?\b",
    )
)

# Directories where prompt building is allowed (RULE-02).
_EXEMPT_PATH_PREFIXES = (
    "packages/core/narrare_core/prompts/",
    "packages/core/narrare_core/prompts\\",
)

# Test file patterns.
_TEST_PATTERNS = (
    "/tests/",
    "\\tests\\",
    "/test_",
    "\\test_",
    "_test.py",
    "/conftest.py",
)

# Path to the adoption registry (relative to project root).
_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "adoption-registry.yaml"

# ── Registry loading (cached) ─────────────────────────────────────

_cached_fallbacks: list[dict[str, str]] | None = None


def _load_registered_fallbacks() -> list[dict[str, str]]:
    """Load ``inline_fallbacks`` from the adoption registry (cached)."""
    global _cached_fallbacks
    if _cached_fallbacks is not None:
        return _cached_fallbacks

    if not _REGISTRY_PATH.exists():
        _cached_fallbacks = []
        return _cached_fallbacks

    with _REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    fallbacks: list[dict[str, str]] = data.get("inline_fallbacks", []) or []
    _cached_fallbacks = fallbacks
    return _cached_fallbacks


def _is_exempt_path(rel_path: str) -> bool:
    """Return *True* for files exempt from inline-prompt checking."""
    if any(rel_path.startswith(p) for p in _EXEMPT_PATH_PREFIXES):
        return True
    return any(pat in rel_path for pat in _TEST_PATTERNS)


def _is_prompt_like(text: str) -> bool:
    """Return *True* if *text* contains prompt-like role-assignment phrases."""
    return any(pat.search(text) for pat in _PATTERNS)


def _match_fallback(
    rel_path: str,
    var_name: str | None,
    registered: list[dict[str, str]],
) -> dict[str, str] | None:
    """Find a matching registered fallback for the given file/variable."""
    for entry in registered:
        if entry.get("file", "") != rel_path:
            continue
        entry_var = entry.get("variable", "")
        # Blanket approval for generic/fallback entries (e.g. "fallback when composer=None").
        if not entry_var or "fallback" in entry_var.lower():
            return entry
        # Exact variable-name match.
        if var_name and entry_var == var_name:
            return entry
    return None


# ── AST helpers ────────────────────────────────────────────────────


def _extract_string_value(node: ast.AST) -> str | None:
    """Extract a static string value from an AST node, if possible."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # Handle simple string concatenation: "a" + "b"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _extract_string_value(node.left)
        right = _extract_string_value(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _find_assign_target_name(node: ast.Assign) -> str | None:
    """Get the variable name from an assignment's first target."""
    if not node.targets:
        return None
    target = node.targets[0]
    if isinstance(target, ast.Name):
        return target.id
    return None


# ── Public API ─────────────────────────────────────────────────────


def check_inline_prompts(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """RULE-INLINE: Inline prompt strings >100 chars must be registered.

    Detects string literals > 100 characters that contain prompt-like
    patterns (role-assignment phrases).  Skips ``core/prompts/`` and
    test files.  Registered inline fallbacks are emitted as approved
    exceptions, not violations.
    """
    if _is_exempt_path(rel_path):
        return []

    registered = _load_registered_fallbacks()
    violations: list[Violation] = []

    for node in ast.walk(tree):
        # Only look at assignments for variable-name matching.
        if not isinstance(node, ast.Assign):
            continue

        value = _extract_string_value(node.value)
        if value is None or len(value) < _MIN_LENGTH:
            continue

        if not _is_prompt_like(value):
            continue

        var_name = _find_assign_target_name(node)
        fallback = _match_fallback(rel_path, var_name, registered)

        if fallback is not None:
            reason = fallback.get("reason", "Registered inline fallback")
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-INLINE",
                    detail=(
                        f"Registered inline prompt '{var_name or '<expr>'}' "
                        f"({len(value)} chars) — {reason}"
                    ),
                    approved=True,
                    approval_reason=reason,
                )
            )
        else:
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-INLINE",
                    detail=(
                        f"Unregistered inline prompt '{var_name or '<expr>'}' "
                        f"({len(value)} chars) — register in adoption-registry.yaml "
                        f"or move to bundled prompt (RULE-02)"
                    ),
                    approved=False,
                )
            )

    return violations
