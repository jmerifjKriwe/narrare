"""Drift checks for extracted context (lookup) files.

The ``.opencode/context/narrare-dev/`` directory mirrors SSOT documents
(``docs/_shared/TECH_STACK.md``, ``CURRENT_STATE.md``, the justfile,
``ci.yml``). Mirrors drift fast: review-04 found these files stale by
weeks, with AI agents loading them as ``Priority: critical`` and operating
on wrong assumptions (pydantic-ai 1.x vs 2.x, ``fastapi-limiter`` active
vs. ``pyrate-limiter`` direct, 60% vs 80% coverage gate, phantom
``just dev-up`` command, hardcoded hook/job counts).

Rather than trying to keep these numbers in sync manually (the root cause
analysis in review-04 shows that fails within days), this checker enforces
**Strategy 1 + 2**: it detects the *known drift patterns* in the lookup
files and fails fast. The patterns are intentionally literal strings —
when the SSOT changes, the lookup file must change too, or this gate
goes red.

Check families:
    - Stale pydantic-ai / mem0 / fastapi-limiter references (TECH_STACK drift)
    - Stale coverage-threshold references (60% transition is resolved)
    - Phantom justfile commands (``just dev-up`` does not exist)
    - Hardcoded pre-commit hook counts (must point at the config as SSOT)

See: review-04-dx-tooling.md AUFG-04-11 / AUFG-04-13.
     docs/_shared/CONSTRAINTS.md §8 (SSOT hierarchy).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from doc_drift import safe_relative
from doc_drift.adr_checks import DocDriftFinding

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LOOKUP_DIR = REPO_ROOT / ".opencode" / "context" / "narrare-dev"

# ── Pattern catalog ──────────────────────────────────────────────
#
# Each entry: (id, relative-path, compiled-regex, severity, message).
# Patterns are literal/anored so a finding means a real drift, not a
# substring coincidence. ``severity="critical"`` fails CI; ``"warning"``
# surfaces in the governance report without blocking.


@dataclass(frozen=True)
class _Pattern:
    check_id: str
    rel_path: str
    pattern: re.Pattern[str]
    severity: str
    message: str


_PATTERNS: tuple[_Pattern, ...] = (
    # ── TECH_STACK drift: version pins that age out within days ──
    _Pattern(
        check_id="LOOKUP-PYDANTIC-AI-1X",
        rel_path="lookup/tech-stack.md",
        # pydantic-ai 1.x is the canonical drift signal (1.x → 2.x is a
        # breaking migration). Match a pinned 1.x version specifically.
        # Avoid \b at the "ai/-slim" junction (hyphen is a non-word char).
        pattern=re.compile(r"pydantic-ai(?:-slim)?[^a-z0-9]*>=?\s*1\.", re.IGNORECASE),
        severity="critical",
        message=(
            "Lookup file references pydantic-ai 1.x. The project is on the "
            "pydantic-ai 2.x line (see packages/core/pyproject.toml). "
            "Replace the hard pin with a major-version reference + a pointer "
            "to packages/core/pyproject.toml (Strategy 1)."
        ),
    ),
    _Pattern(
        check_id="LOOKUP-MEM0-1X",
        rel_path="lookup/tech-stack.md",
        pattern=re.compile(r"\bmem0\b[^a-z0-9]*>=?\s*1\.", re.IGNORECASE),
        severity="critical",
        message=(
            "Lookup file references mem0 1.x. The project uses mem0ai 2.0.x "
            "(see packages/core/pyproject.toml, ADR-033). Replace the hard "
            "pin with a major-version reference + a manifest pointer."
        ),
    ),
    _Pattern(
        check_id="LOOKUP-FASTAPI-LIMITER",
        rel_path="lookup/tech-stack.md",
        # Match fastapi-limiter only when it appears as an active pin/usage
        # (``>=``/``==`` or a parenthesised/quoted dependency form), NOT when
        # it is mentioned in a "do-not-use" explanation. This avoids false
        # positives on the legitimate "fastapi-limiter is not used" note.
        pattern=re.compile(r"fastapi-limiter\b\s*(?:>=|==|\()\s*[\d<]"),
        severity="critical",
        message=(
            "Lookup file lists fastapi-limiter as an active dependency. "
            "fastapi-limiter is unmaintained and not used; the project uses "
            "pyrate-limiter directly via apps/api/narrare/_app/rate_limiter_dep.py. "
            "(See docs/_shared/TECH_STACK.md for the authoritative statement.)"
        ),
    ),
    # ── Coverage-gate drift: the 60% transition is resolved ──
    _Pattern(
        check_id="LOOKUP-COVERAGE-60-FLOOR",
        rel_path="processes/quality-gates.md",
        # Match the resolved 60% hard floor only when framed as *current*
        # policy. We allow the historical marker "Resolved am …" / "resolved"
        # by requiring the surrounding context to read as active.
        pattern=re.compile(r"(?i)hard\s+floor\s*[:=]?\s*60\s*%|cov-fail-under\s*=?\s*'?60"),
        severity="critical",
        message=(
            "Lookup file documents a 60% coverage hard floor as current. "
            "The 60% transition was resolved; CI enforces --cov-fail-under=80 "
            "(see .github/workflows/ci.yml). Update to 80% or remove the "
            "stale 60% statement."
        ),
    ),
    # ── Phantom justfile commands ──
    _Pattern(
        check_id="LOOKUP-PHANTOM-DEV-UP",
        rel_path="guides/deployment.md",
        # Match `just dev-up` when presented as an actionable command, i.e.
        # introduced by an action verb (run/use/start/execute) OR standing
        # alone on a line (e.g. inside a code block). A leading negation
        # ("No `just dev-up`", "there is no `just dev-up`", "without `just …`")
        # is explicitly exempted via lookbehind so a clarifying note that
        # tells readers the command does NOT exist does not false-positive.
        pattern=re.compile(
            r"(?i)"
            r"(?<![Nn]o )(?<!not )(?<!without )"
            r"(?:run|use|start with|execute)\b[^.`\n]{0,40}`just\s+dev-up`"
            r"|^\s*`?just\s+dev-up`?\s*$"
        ),
        severity="critical",
        message=(
            "Lookup file references `just dev-up`, which does not exist in "
            "the justfile. Use `just dev-services` / `just dev-services-stop`, "
            "or `just dev` (which calls _ensure-services internally). A "
            'clarifying note like "No `just dev-up`" is fine and will not '
            "trigger this check."
        ),
    ),
    # ── Hardcoded pre-commit hook counts ──
    _Pattern(
        check_id="LOOKUP-HOOK-COUNT",
        rel_path="guides/deployment.md",
        # "9 hooks", "27 hooks" — any "<number> hooks" claim is fragile
        # because hooks are added/removed over time.
        pattern=re.compile(r"\b\d+\s+hooks\b"),
        severity="warning",
        message=(
            "Lookup file states a hardcoded pre-commit hook count. Hook "
            "counts drift whenever a hook is added or removed. Replace with "
            "a pointer to .pre-commit-config.yaml (the SSOT) instead of a "
            "number (Strategy 1)."
        ),
    ),
)


def _check_one(pattern: _Pattern) -> DocDriftFinding | None:
    """Return a finding if *pattern* matches its file, else ``None``.

    ``pattern.rel_path`` is relative to the lookup root
    (``.opencode/context/narrare-dev/``), not the repo root.
    """
    full = _LOOKUP_DIR / pattern.rel_path
    if not full.is_file():
        # Missing files are out of scope here (other gates own existence).
        return None
    try:
        content = full.read_text(encoding="utf-8")
    except OSError:
        return None
    if pattern.pattern.search(content):
        return DocDriftFinding(
            severity=pattern.severity,
            file=safe_relative(full),
            message=f"[{pattern.check_id}] {pattern.message}",
        )
    return None


def check_lookup_drift() -> list[DocDriftFinding]:
    """Run all lookup-context drift checks and return findings.

    Returns an empty list when every lookup file is clean against the
    known drift patterns. Critical findings fail CI via check_doc_drift.py;
    warnings surface in the governance report.
    """
    findings: list[DocDriftFinding] = []
    for pattern in _PATTERNS:
        finding = _check_one(pattern)
        if finding is not None:
            findings.append(finding)
    return findings
