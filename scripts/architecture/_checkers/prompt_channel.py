"""RULE-02b · No feature system prompt concatenated into the user channel.

Detects prompt-channel injection violations (ADR-046 Component 1 / D.2 Module 3):

A service that resolves a feature prompt via ``PromptComposer.build()`` receives a
``ComposedPrompt`` with separate ``.system`` and ``.user`` channels. The system
content must be passed as agent system/instructions; only ``.user`` belongs in the
user prompt. Concatenating both channels (e.g. ``composed.system + composed.user``
or ``f"{composed.system}\\n\\n{composed.user}"``) lands feature instructions in the
user channel, where the model treats them as user text rather than instructions.

**What is flagged:**
- ``x.system + x.user`` (or with intermediates, e.g. ``x.system + "\\n" + x.user``)
- f-strings that interpolate both ``.system`` and ``.user`` into one string

**What is NOT flagged (correct patterns):**
- ``return (composed.system, composed.user)`` — a tuple keeps the channels separate
- ``agent.run(prompt=composed.user)`` with ``system_prompt=composed.system``

See: ``docs/architecture/decisions/ADR-046-prompt-path-compliance.md`` (D.2 Module 3)
See: ``docs/_shared/CONSTRAINTS.md`` RULE-02b (violation 3)
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import (
    compute_type_checking_lines,
    is_approved_exception,
)
from scripts.architecture.types import Violation

# core/prompts/ legitimately combines channels when assembling the final prompt.
_EXEMPT_PREFIXES = (
    "packages/core/narrare_core/prompts/",
    "packages/core/narrare_core/prompts\\",
)

_TEST_PATTERNS = (
    "/tests/",
    "\\tests\\",
    "/test_",
    "\\test_",
    "_test.py",
    "/conftest.py",
)

_RULE = "RULE-02b"


# ── Helpers ────────────────────────────────────────────────────────


def _is_exempt(rel_path: str) -> bool:
    """Return True for paths outside the RULE-02b channel-check surface."""
    if any(rel_path.startswith(p) for p in _EXEMPT_PREFIXES):
        return True
    return any(pat in rel_path for pat in _TEST_PATTERNS)


def _channel_attr_kind(node: ast.AST) -> str | None:
    """Return ``"system"``/``"user"`` for an ``x.system``/``x.user`` attribute.

    Only matches attribute access on an object (Name/Attribute/Call) — bare
    ``"system"`` string literals are ignored.
    """
    if not isinstance(node, ast.Attribute):
        return None
    if node.attr not in {"system", "user"}:
        return None
    # Require a non-trivial base: Name, Attribute, Subscript, or Call.
    # (A bare ``.system`` with no base is not valid Python anyway.)
    if isinstance(node.value, (ast.Name, ast.Attribute, ast.Subscript, ast.Call)):
        return node.attr
    return None


def _flatten_add(node: ast.AST) -> list[ast.AST]:
    """Flatten a ``+`` chain into its leaf operands.

    ``a + b + c`` -> ``[a, b, c]`` (in source order).
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten_add(node.left) + _flatten_add(node.right)
    return [node]


def _joined_str_channels(node: ast.JoinedStr) -> set[str]:
    """Return the set of channel attrs interpolated by an f-string."""
    kinds: set[str] = set()
    for value in node.values:
        if isinstance(value, ast.FormattedValue):
            kind = _channel_attr_kind(value.value)
            if kind is not None:
                kinds.add(kind)
    return kinds


# ── Public API ─────────────────────────────────────────────────────


def check_prompt_channel_injection(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """RULE-02b: feature system prompt must not be concatenated into user channel.

    Flags string-concatenation (``+``) and f-string interpolation that merge a
    ``.system`` and ``.user`` attribute of the same object into a single string.

    Tuple returns such as ``(composed.system, composed.user)`` keep the channels
    separate and are NOT flagged.
    """
    if _is_exempt(rel_path):
        return []

    tc_lines = compute_type_checking_lines(tree)
    violations: list[Violation] = []

    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", None)
        if lineno is not None and lineno in tc_lines:
            continue

        # --- Concatenation: a.system + ... + b.user ---
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            leaves = _flatten_add(node)
            kinds = {kind for leaf in leaves if (kind := _channel_attr_kind(leaf)) is not None}
            if "system" in kinds and "user" in kinds:
                approved, reason = is_approved_exception(source_lines, node.lineno)
                violations.append(
                    Violation(
                        file=Path(rel_path),
                        line=node.lineno,
                        rule=_RULE,
                        detail=(
                            "System prompt concatenated with user prompt "
                            "(composed.system + composed.user) — pass "
                            "composed.system as agent instructions and "
                            "composed.user as the user prompt"
                        ),
                        approved=approved,
                        approval_reason=reason,
                    )
                )

        # --- f-string: f"{x.system} ... {x.user}" ---
        elif isinstance(node, ast.JoinedStr):
            kinds = _joined_str_channels(node)
            if "system" in kinds and "user" in kinds:
                approved, reason = is_approved_exception(source_lines, node.lineno)
                violations.append(
                    Violation(
                        file=Path(rel_path),
                        line=node.lineno,
                        rule=_RULE,
                        detail=(
                            "System and user prompts merged in one f-string "
                            "(f-string interpolates both composed.system and "
                            "composed.user) — keep channels separate"
                        ),
                        approved=approved,
                        approval_reason=reason,
                    )
                )

    return violations
