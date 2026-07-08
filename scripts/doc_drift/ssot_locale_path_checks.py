"""SSOT locale-path parity check (CONSTRAINTS.md RULE-16 vs request.ts).

Ensures the normative i18n locale path documented in CONSTRAINTS.md RULE-16
matches the path the frontend loader actually imports at runtime.

Guards against recurrence of the review-01 drift where RULE-16 documented
``packages/web/messages/{locale}/...`` while the real files — and the
``packages/web/lib/i18n/request.ts`` import — live in
``packages/i18n/messages/{locale}/{ns}.json`` (ADR-013 Decision Option B).

Scope: CONSTRAINTS.md (the living normative SSOT) and request.ts (the
runtime import) only. Historical ADRs and implementation-plan milestone
tables that reference the old path are intentionally NOT flagged here —
they are immutable historical records, not existence claims.

See: docs/_shared/CONSTRAINTS.md RULE-16, ADR-013, ADR-041.
"""

from __future__ import annotations

import re
from pathlib import Path

from doc_drift import safe_relative
from doc_drift.adr_checks import DocDriftFinding

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONSTRAINTS_PATH = REPO_ROOT / "docs" / "_shared" / "CONSTRAINTS.md"
REQUEST_TS_PATH = REPO_ROOT / "packages" / "web" / "lib" / "i18n" / "request.ts"

# The stale locale path. The normative SSOT must NEVER reference it — the
# real locale files were relocated to packages/i18n/ by ADR-013 Option B.
STALE_LOCALE_PATH = "packages/web/messages"

# The canonical locale path (ADR-013 Decision Option B). RULE-16 MUST
# document this path. If the frontend loader ever moves, update this
# constant AND CONSTRAINTS.md together.
CANONICAL_LOCALE_PATH = "packages/i18n/messages"

# The request.ts dynamic import that reveals the real on-disk path, e.g.
#   await import(`../../../i18n/messages/${locale}/${ns}.json`)
# Used for the doc-vs-reality cross-check.
_REQUEST_IMPORT_RE = re.compile(r"import\([^)]*i18n/messages/\$\{locale\}/")


def _read(path: Path) -> str | None:
    """Return file text, or ``None`` if the path does not exist."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


# ── Check function ─────────────────────────────────────────────


def check_ssot_locale_path(
    constraints_path: Path | None = None,
    request_ts_path: Path | None = None,
) -> list[DocDriftFinding]:
    """Assert CONSTRAINTS.md RULE-16 locale path matches the request.ts import.

    Three complementary, CRITICAL assertions keep the SSOT pinned to reality:

    1. **Stale-path guard** — CONSTRAINTS.md must not reference
       ``packages/web/messages`` anywhere. It is the living normative SSOT;
       the only valid locale path is ``packages/i18n/messages/``.
    2. **Canonical-presence guard** — CONSTRAINTS.md must document the
       canonical path ``packages/i18n/messages`` (catches accidental removal
       of the RULE-16 locale-path examples).
    3. **Reality cross-check** — request.ts must still import from
       ``i18n/messages/${locale}/``. If the runtime path genuinely changes,
       this fires so RULE-16 in CONSTRAINTS.md AND ``CANONICAL_LOCALE_PATH``
       in this checker are updated together (enforcing "documented =
       implemented", architectural-discipline §7).

    Args:
        constraints_path: Override CONSTRAINTS.md path (for testing).
        request_ts_path: Override request.ts path (for testing).

    Returns:
        List of CRITICAL ``DocDriftFinding`` for any drift.
    """
    effective_constraints = constraints_path or CONSTRAINTS_PATH
    effective_request_ts = request_ts_path or REQUEST_TS_PATH
    findings: list[DocDriftFinding] = []

    constraints_text = _read(effective_constraints)
    if constraints_text is None:
        findings.append(
            DocDriftFinding(
                severity="critical",
                file=str(effective_constraints),
                message="CONSTRAINTS.md not found — cannot validate RULE-16 locale path.",
            )
        )
        return findings

    # 1. Stale-path guard — flag every line in the SSOT that names the old path.
    for lineno, line in enumerate(constraints_text.splitlines(), start=1):
        if STALE_LOCALE_PATH in line:
            findings.append(
                DocDriftFinding(
                    severity="critical",
                    file=f"{safe_relative(effective_constraints)}:{lineno}",
                    message=(
                        f"RULE-16 documents stale locale path "
                        f"'{STALE_LOCALE_PATH}/'. The frontend loader "
                        f"(packages/web/lib/i18n/request.ts) imports from "
                        f"'{CANONICAL_LOCALE_PATH}/'. Update CONSTRAINTS.md "
                        f"to match reality (ADR-013 Decision Option B)."
                    ),
                )
            )

    # 2. Canonical-presence guard — RULE-16 must name the real locale dir.
    if CANONICAL_LOCALE_PATH not in constraints_text:
        findings.append(
            DocDriftFinding(
                severity="critical",
                file=safe_relative(effective_constraints),
                message=(
                    f"CONSTRAINTS.md no longer references the canonical locale "
                    f"path '{CANONICAL_LOCALE_PATH}/'. RULE-16 must document "
                    f"the real i18n message location (ADR-013)."
                ),
            )
        )

    # 3. Reality cross-check — the runtime import must still resolve to the
    #    canonical dir; if it moves, force a joint doc+checker update.
    request_text = _read(effective_request_ts)
    if request_text is not None and not _REQUEST_IMPORT_RE.search(request_text):
        findings.append(
            DocDriftFinding(
                severity="critical",
                file=safe_relative(effective_request_ts),
                message=(
                    "request.ts no longer imports from "
                    "'i18n/messages/${locale}/'. If the locale path really "
                    "changed, update RULE-16 in CONSTRAINTS.md AND "
                    "CANONICAL_LOCALE_PATH/STALE_LOCALE_PATH in this checker "
                    "together (architectural-discipline §7)."
                ),
            )
        )

    return findings
