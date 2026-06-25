"""INLINE-FEATURE-PROMPT · Service-layer f-string feature prompts to agent.run() (ADR-049 A5).

Detects the FIND-011 pattern: a service-layer file assembles a feature/task
prompt via f-string or string concatenation and passes it directly to
``agent.run(prompt=...)`` or ``agent.run_stream(prompt=...)``.

RULE-02 / RULE-02a / RULE-02b require feature/task framing to flow through
the PromptComposer cascade, not through inline f-strings.  Runtime data
(chapter text, user messages, extracted entities) MAY be passed as the run
prompt — only feature/task framing is forbidden.

**Detection heuristic:**

The checker flags ``agent.run(prompt=f"...")`` and ``agent.run(prompt="..." + ...)``
call sites where the f-string/concatenation contains feature-framing
indicators (imperatives like "Analyse", "Generate", "Summarise", or role/task
descriptions).  Pure-runtime-data prompts (e.g. ``agent.run(prompt=chapter.text)``)
are allowed.

This checker complements the existing ``inline_prompts.py`` (which detects
long inline string *assignments*) and ``prompt_path.py`` (which detects
direct ``PromptRegistry.resolve()`` access).  All three together cover the
RULE-02/02a/02b enforcement surface.

See: ``docs/architecture/decisions/ADR-049-prompt-surface-identity-path-contract.md``
      (A5 - Inline Feature-Prompt Gate, lines 642-659)
See: ``docs/_shared/CONSTRAINTS.md`` RULE-02 / RULE-02a / RULE-02b
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scripts.architecture.helpers import is_approved_exception
from scripts.architecture.types import Violation

# ── Constants ──────────────────────────────────────────────────────

# Feature-framing indicator patterns. These are imperatives and role/task
# phrases that signal feature-prompt content (not runtime data).
_FEATURE_FRAMING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\banaly[sz]e\b",
        r"\bgenerate\b",
        r"\bsummar[iz]e\b",
        r"\bextract\b",
        r"\breview\b",
        r"\bidentify\b",
        r"\bcreate\b",
        r"\bwrite\b",
        r"\byou are\b",
        r"\byour task\b",
        r"\byour job\b",
        r"\byour role\b",
        r"\bact as\b",
        r"\bproduce\b",
        r"\bevaluat[ei]\b",
        r"\bcheck\b",
        r"\bcompare\b",
    )
)

# Methods on agent-like receivers that accept a ``prompt`` kwarg.
_AGENT_RUN_METHODS = frozenset({"run", "run_sync", "run_stream"})

# Service-layer directories where this check applies.
_SERVICE_DIRS = ("apps/api",)

# Rule identifier.
_RULE = "INLINE-FEATURE-PROMPT"

# ── Baseline (ratchet) ─────────────────────────────────────────────
#
# Pre-existing inline feature-prompt violations discovered when the A5
# checker was introduced (ADR-049 Phase D).  These are RULE-02 violations
# that existed before Phase D but were not detected by any prior checker.
#
# ADR-054 retired the last three ratcheted entries (CharacterArcService,
# TimelineExtractionService, KBMergeService) by migrating them to
# PromptComposer Mode 1.  The ratchet floor is now **zero**: any new
# inline feature-prompt is blocking, and there is no approved debt
# baseline left to hide behind.
#
# The ``is_approved_exception`` baseline path remains in the checker for
# future temporary ratchets (e.g. a newly-discovered clone migrated under
# a follow-up ADR); add entries here only with an ADR that discloses the
# deferral, and empty them again once the migration ships.
#
# Each entry: (relative_path, lineno) — must match exactly.
_BASELINE_VIOLATIONS: frozenset[tuple[str, int]] = frozenset()


# ── Helpers ────────────────────────────────────────────────────────


def _is_service_file(rel_path: str) -> bool:
    """Return True for files in the service layer (apps/api/)."""
    return any(rel_path.startswith(d) for d in _SERVICE_DIRS)


def _is_agent_run_call(node: ast.Call) -> bool:
    """Return True if *node* is an ``agent.run(...)`` / ``run_stream(...)`` call."""
    if not isinstance(node.func, ast.Attribute):
        return False
    return node.func.attr in _AGENT_RUN_METHODS


def _extract_f_string_text(node: ast.JoinedStr) -> str:
    """Extract a best-effort text representation from an f-string node.

    Static parts are concatenated; format-value interpolations are replaced
    with a placeholder so feature-framing patterns can still be detected.
    """
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        else:
            parts.append("{}")
    return "".join(parts)


def _extract_concat_text(node: ast.BinOp) -> str:
    """Extract text from a string concatenation (``"a" + "b" + var``)."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.BinOp) and isinstance(current.op, ast.Add):
        right_text = _single_node_text(current.right)
        if right_text is not None:
            parts.append(right_text)
        else:
            parts.append("{}")
        current = current.left
    left_text = _single_node_text(current)
    if left_text is not None:
        parts.append(left_text)
    else:
        parts.append("{}")
    return "".join(reversed(parts))


def _single_node_text(node: ast.expr) -> str | None:
    """Extract static text from a single AST node (str, f-string, or concat)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return _extract_f_string_text(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _extract_concat_text(node)
    return None


def _has_feature_framing(text: str) -> bool:
    """Return True if *text* contains feature-framing indicators."""
    return any(pat.search(text) for pat in _FEATURE_FRAMING_PATTERNS)


# ── Public API ─────────────────────────────────────────────────────


def check_inline_feature_prompt(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
) -> list[Violation]:
    """ADR-049 A5: No service-layer f-string feature prompts to agent.run().

    Flags ``agent.run(prompt=f"...")`` and ``agent.run(prompt="..." + ...)``
    call sites in ``apps/api/`` where the f-string/concatenation contains
    feature-framing content.  Pure-runtime-data prompts are allowed.
    """
    if not _is_service_file(rel_path):
        return []

    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_agent_run_call(node):
            continue

        # Find the prompt= keyword argument
        prompt_node: ast.expr | None = None
        for kw in node.keywords:
            if kw.arg == "prompt":
                prompt_node = kw.value
                break

        if prompt_node is None:
            continue

        # Only flag f-strings and concatenations — not variable references
        is_fstring = isinstance(prompt_node, ast.JoinedStr)
        is_concat = isinstance(prompt_node, ast.BinOp) and isinstance(prompt_node.op, ast.Add)
        if not (is_fstring or is_concat):
            continue

        text = _single_node_text(prompt_node)
        if text is None:
            continue

        if not _has_feature_framing(text):
            continue

        # node.func is ast.Attribute (guaranteed by _is_agent_run_call)
        method_name = node.func.attr if isinstance(node.func, ast.Attribute) else "run"
        approved, reason = is_approved_exception(source_lines, node.lineno)

        # Ratchet: pre-existing baseline violations are approved exceptions.
        # New violations (not in baseline) are blocking.
        baseline_key = (rel_path, node.lineno)
        if not approved and baseline_key in _BASELINE_VIOLATIONS:
            approved = True
            reason = (
                "Pre-existing A5 baseline violation (ADR-049 Phase D ratchet) — "
                "migrate to PromptComposer to clear this debt"
            )

        violations.append(
            Violation(
                file=Path(rel_path),
                line=node.lineno,
                rule=_RULE,
                detail=(
                    "Service-layer f-string feature prompt passed to "
                    f"agent.{method_name}(prompt=...). Feature/task "
                    "framing must flow through PromptComposer (RULE-02/02a/02b). "
                    "Runtime data (chapter text, user messages) may be passed "
                    "as the run prompt, but feature instructions must not be "
                    "inlined. (ADR-049 A5)"
                ),
                approved=approved,
                approval_reason=reason,
            )
        )

    return violations
