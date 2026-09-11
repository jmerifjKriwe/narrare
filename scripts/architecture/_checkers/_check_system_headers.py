"""PROMPT-L2-HEADERS · Level-2 header governance for system.md templates (R2 Slice 0).

Approved ruling (2026-09-10 prompt-boundary defect): every registry-governed
template ``prompts/_bundled/**/system.md`` may use ``^## `` level-2 headers
ONLY for ``System Prompt`` and ``First Message``.

Rationale: ``PromptRegistry._parse_prompt`` (prompts/registry.py) builds the
system prompt via ``extract_section(body, "System Prompt")`` whose regex
terminates the section at the NEXT ``^##\\s`` header (shared/frontmatter.py).
Any other level-2 header silently truncates the prompt before variable
substitution — the 2026-09-10 boundary defect (``{{user_preferences}}`` /
``{{cross_session_context}}`` / ``{{avoidance_patterns}}`` tail dropped from
``writing/en/new_chapter``).

Out of scope — un-governed, full-body loaders (verified discriminator, SSOT
``_check_prompt_identity.CAPABILITY_CATEGORIES``):
- ``meta/`` and ``universal/`` — loaded directly by Capabilities (ADR-026)
- ``wiki/`` — rendered by ``WikiPromptLoader``

Explicit allowlist (ratcheting, mirrors T3 stale-baseline semantics):
``ai-gate-baseline.json`` → ``system_prompt_l2_header_allowlist``, one entry
per template that currently carries rogue level-2 headers:
``"<template_path> | <one-line reason> | <slice reference>"``.
- Rogue headers in an allowlisted template → approved exception (advisory).
- Rogue headers in any other template → ``[UNALLOWED]`` violation (blocking).
- Allowlist entry matching no rogue template (fixed / deleted) →
  ``[STALE-ALLOWLIST]`` violation (blocking) — prune, never carry phantoms.
- Malformed or duplicate entries → violations (allowlist self-governance).
Growth beyond the seeded set requires an approved baseline update.

Header semantics deliberately mirror ``extract_section``'s LINE regex (not a
Markdown AST): any body line matching ``^##\\s`` counts — including inside
code fences — because the runtime parser is regex-based and would truncate
there too. Allowed headers match ``^##\\s+(System Prompt|First Message)\\s*$``
case-insensitively, exactly like the runtime section lookup.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

from scripts.architecture._checkers._check_prompt_identity import CAPABILITY_CATEGORIES
from scripts.architecture.helpers import ROOT
from scripts.architecture.types import CheckResult, Violation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RULE_ID = "PROMPT-L2-HEADERS"

_ALLOWED_L2_HEADER_RE = re.compile(r"^##\s+(?:System Prompt|First Message)\s*$", re.IGNORECASE)
_L2_HEADER_RE = re.compile(r"^##\s")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Baseline location, relative to ROOT (label for violations) — derived at call
# time so tests/simulations can repoint the repo root with a single patch.
_BASELINE_REL = Path("scripts") / "architecture" / "ai-gate-baseline.json"
_ALLOWLIST_KEY = "system_prompt_l2_header_allowlist"
_BUNDLED_REL = ("packages", "core", "narrare_core", "prompts", "_bundled")


def _baseline_path() -> Path:
    """Absolute baseline path (resolved from the current module ROOT)."""
    return ROOT / _BASELINE_REL


# ---------------------------------------------------------------------------
# Template scanning
# ---------------------------------------------------------------------------


def _strip_frontmatter(text: str) -> tuple[str, int]:
    """Return ``(body, body_line_offset)`` for a template file.

    The offset is the number of lines consumed by the frontmatter block so
    that header line numbers can be reported as absolute file lines.
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return text, 0
    return text[match.end() :], text[: match.end()].count("\n")


def _rogue_l2_headers(path: Path) -> list[tuple[int, str]]:
    """Collect ``(absolute_line, header_text)`` for every rogue level-2 header.

    Rogue = body line matching ``^##\\s`` that is NOT an allowed section
    header (``System Prompt`` / ``First Message``, case-insensitive) —
    mirroring ``extract_section`` semantics (see module docstring).
    """
    text = path.read_text(encoding="utf-8")
    body, offset = _strip_frontmatter(text)
    rogues: list[tuple[int, str]] = []
    for index, line in enumerate(body.splitlines()):
        if _L2_HEADER_RE.match(line) and not _ALLOWED_L2_HEADER_RE.match(line):
            rogues.append((offset + index + 1, line.strip()))
    return rogues


def _scan_governed_templates(bundled_root: Path) -> dict[str, list[tuple[int, str]]]:
    """Map template rel-path → rogue headers for all registry-governed system.md.

    Registry-governed = every ``_bundled/**/system.md`` whose category is NOT
    a capability-loaded one (``meta``/``universal``/``wiki`` render the full
    body via Capabilities / WikiPromptLoader, so ``extract_section``
    truncation cannot occur there).
    """
    rogues: dict[str, list[tuple[int, str]]] = {}
    if not bundled_root.is_dir():
        return rogues
    for path in sorted(bundled_root.rglob("system.md")):
        rel_parts = path.relative_to(bundled_root).parts
        if rel_parts and rel_parts[0] in CAPABILITY_CATEGORIES:
            continue
        found = _rogue_l2_headers(path)
        if found:
            rogues[path.relative_to(ROOT).as_posix()] = found
    return rogues


# ---------------------------------------------------------------------------
# Allowlist handling
# ---------------------------------------------------------------------------


def _load_allowlist() -> list[str]:
    """Load the ``system_prompt_l2_header_allowlist`` entries from the baseline.

    Tolerant of a missing file/section (empty allowlist → every rogue header
    fails loudly as ``[UNALLOWED]``); a corrupted baseline file also surfaces
    as violations rather than being silently skipped.
    """
    try:
        with open(_baseline_path()) as f:
            data: dict[str, object] = json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        return []
    entries = data.get(_ALLOWLIST_KEY, [])
    if not isinstance(entries, list):
        return []
    return [entry for entry in cast("list[object]", entries) if isinstance(entry, str)]


def _parse_entry(entry: str) -> tuple[str, str, str] | None:
    """Split ``"<path> | <reason> | <slice-ref>"`` into its three fields."""
    parts = [part.strip() for part in entry.split(" | ")]
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


# ---------------------------------------------------------------------------
# Gate entry point
# ---------------------------------------------------------------------------


def check_system_prompt_l2_headers(result: CheckResult) -> None:
    """Run the PROMPT-L2-HEADERS gate (R2 Slice 0).

    - Rogue headers, template allowlisted → ``result.approved_exceptions``.
    - Rogue headers, not allowlisted → ``result.violations`` (``[UNALLOWED]``).
    - Allowlist entries matching no rogue template → ``result.violations``
      (``[STALE-ALLOWLIST]``) — ratchet pruning, same policy as T3.
    - Malformed / duplicate entries → ``result.violations``.
    """
    bundled_root = ROOT.joinpath(*_BUNDLED_REL)
    rogues = _scan_governed_templates(bundled_root)

    allowlist: dict[str, tuple[str, str]] = {}
    for entry in _load_allowlist():
        parsed = _parse_entry(entry)
        if parsed is None:
            result.violations.append(
                Violation(
                    file=_BASELINE_REL,
                    line=0,
                    rule=RULE_ID,
                    detail=(
                        f"[MALFORMED-ALLOWLIST] Entry does not follow "
                        f"'<template_path> | <reason> | <slice-ref>': {entry!r}"
                    ),
                )
            )
            continue
        path, reason, slice_ref = parsed
        if path in allowlist:
            result.violations.append(
                Violation(
                    file=_BASELINE_REL,
                    line=0,
                    rule=RULE_ID,
                    detail=f"[DUPLICATE-ALLOWLIST] Duplicate template path: {path}",
                )
            )
            continue
        allowlist[path] = (reason, slice_ref)

    for rel_path, found in rogues.items():
        header_summary = ", ".join(f"{header!r} (L{line})" for line, header in found)
        if rel_path in allowlist:
            reason, slice_ref = allowlist[rel_path]
            result.approved_exceptions.append(
                Violation(
                    file=Path(rel_path),
                    line=found[0][0],
                    rule=RULE_ID,
                    detail=(f"Rogue level-2 header(s) {header_summary} — allowlisted, {reason}"),
                    approved=True,
                    approval_reason=f"{reason} ({slice_ref})",
                )
            )
        else:
            result.violations.append(
                Violation(
                    file=Path(rel_path),
                    line=found[0][0],
                    rule=RULE_ID,
                    detail=(
                        f"[UNALLOWED] {rel_path}: rogue level-2 header(s) beyond "
                        f"'System Prompt'/'First Message': {header_summary}. "
                        f"extract_section terminates the System Prompt at any "
                        f"'^## ' header (2026-09-10 boundary defect) — demote to "
                        f"'###' or get an approved allowlist entry in "
                        f"ai-gate-baseline.json {_ALLOWLIST_KEY}"
                    ),
                )
            )

    for rel_path, (reason, slice_ref) in sorted(allowlist.items()):
        if rel_path not in rogues:
            result.violations.append(
                Violation(
                    file=_BASELINE_REL,
                    line=0,
                    rule=RULE_ID,
                    detail=(
                        f"[STALE-ALLOWLIST] Entry matches no governed template with "
                        f"rogue level-2 headers — remove: {rel_path} "
                        f"({reason}; {slice_ref})"
                    ),
                )
            )
