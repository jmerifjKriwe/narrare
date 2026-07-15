"""WARNING-ONLY guard for references to removed governance artifacts.

Context
-------
The governance teardown in commit ``f8abb42c`` removed the Configuration
Adoption Matrix (``configuration-adoption-matrix.yaml``), the CI-blocking
``check_configuration_matrix.py`` checker, the ``scripts/governance/`` package
and its modules (``_matrix_review_gate.py``, ``configuration_matrix.py``,
``aufg_registry.py`` …), the ``aufg-registry.md`` / ``matrix-effect-evidence.yaml``
/ ``status_vocabulary.yaml`` data files, and the retired ``just
check-configuration-matrix`` target. Stale references to those deleted artifacts
remained in docs. This guard makes such dangling references visible so the
incomplete-cleanup regression class is caught next time — WITHOUT
re-introducing the heavy matrix toolchain.

Severity / ratchet
------------------
This check is **WARNING-ONLY**: every finding it emits has ``severity="warning"``,
so ``check_doc_drift.py`` reports it but exits 0 (it never fails CI or
pre-commit on its own). A ratcheted **file-level allowlist** records the files
that legitimately discuss the removal historically (ADRs, implementation plans,
audit/review findings, and curated standards that annotate the deletion). The
current post-cleanup tree therefore starts clean (zero new warnings).

To ratchet this guard to **blocking** later:

    1. Triage every warning — reword to clearly-historical, or add the file to
       the allowlist below with a one-line justification.
    2. Once the baseline is clean, change ``_SEVERITY`` to ``"critical"``.
       ``check_doc_drift.py`` will then fail CI on any new dangling reference.

RULE-11: the guard never fails silently — if the scan root is unreadable or
missing, it emits a warning describing the problem.

See: docs/_shared/CONSTRAINTS.md (RULE-11)
     docs/development/finding-lifecycle.md (enforcement ⇒ ✅ Resolved)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from doc_drift import safe_relative
from doc_drift.adr_checks import DocDriftFinding

if TYPE_CHECKING:
    from collections.abc import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Removed-artifact token catalog ──────────────────────────────
#
# Literal substrings (case-sensitive — these are filenames/paths, not prose).
# A match means the surrounding doc mentions a deleted artifact; the allowlist
# below decides whether that mention is a legitimate historical reference or a
# dangling reference that needs reviewer triage.
_REMOVED_TOKENS: tuple[str, ...] = (
    "configuration-adoption-matrix.yaml",
    "configuration-adoption-matrix.schema.json",
    "check_configuration_matrix.py",
    "_matrix_review_gate.py",
    "configuration_matrix.py",
    "aufg_registry.py",
    "aufg-registry.md",
    "matrix-effect-evidence.yaml",
    "status_vocabulary.yaml",
    "scripts/governance/",
    "check-configuration-matrix",
)

# ── Ratcheted file-level allowlist (clean starting state) ───────
#
# Files/directories that legitimately reference the removed artifacts because
# they record the decision/history of the removal. Inherently-historical trees
# are allowlisted by directory prefix; curated standards/governance docs are
# allowlisted by exact relative path. Paths are POSIX-style (repo-relative).

_ALLOWED_DIRS: tuple[str, ...] = (
    "docs/architecture/decisions/",  # ADRs — frozen historical decision records
    "docs/superpowers/plans/",  # historical implementation plans
    "_audit/",  # review/finding/audit files — historical
)

_ALLOWED_FILES: tuple[str, ...] = (
    "docs/_shared/CONSTRAINTS.md",
    "docs/_shared/CURRENT_STATE.md",
    "docs/development/testing-standards.md",
    "docs/architecture/governance/ai-ux-compliance-v2.md",
    "docs/architecture/governance/cr-08-p1-token-limits-and-suitability-policy.md",
    "docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md",
    "docs/features/remediation/cr-08-configuration-effect-drift.md",
    # Mirrors the (allowlisted) ADR INDEX — ADR-047 (⛔ Superseded) scope rows
    # legitimately name scripts/governance/ as historical context.
    ".opencode/context/narrare-dev/lookup/adr-index.md",
)

# WARNING-ONLY this cycle. Flip to "critical" to ratchet to blocking (after the
# baseline is clean). See module docstring "Severity / ratchet".
_SEVERITY = "warning"

# Directories never scanned (build artefacts, vendored deps, caches).
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".code-review-graph",
        "dist",
        "build",
        ".next",
        ".turbo",
    }
)


def _is_allowlisted(rel_path: str) -> bool:
    """True if *rel_path* (repo-relative, POSIX-style) is in the baseline."""
    posix = rel_path.replace("\\", "/")
    if any(posix.startswith(d) for d in _ALLOWED_DIRS):
        return True
    return posix in _ALLOWED_FILES


def _iter_markdown(scan_root: Path) -> Iterator[Path]:
    """Yield ``*.md`` files under *scan_root*, skipping vendored/cache dirs."""
    if not scan_root.exists():
        return
    for path in scan_root.rglob("*.md"):
        if any(part in _SKIP_DIRS for part in path.relative_to(scan_root).parts):
            continue
        yield path


def check_removed_governance_refs(
    scan_root: Path | None = None,
) -> list[DocDriftFinding]:
    """Scan markdown for references to removed governance artifacts.

    Emits a ``warning``-severity :class:`DocDriftFinding` for every ``*.md`` file
    under *scan_root* (default: the repository root) that mentions a removed
    artifact token and is NOT in the ratcheted allowlist. WARNING-ONLY: findings
    surface in the doc-drift governance report but never fail CI.

    Args:
        scan_root: Root to scan (repo-relative allowlist paths apply). Defaults
            to the repository root.

    Returns:
        Findings list (empty when the baseline is clean). Never raises — a
        missing/unreadable scan root or file is reported as a warning (RULE-11).
    """
    root = scan_root or REPO_ROOT

    if not root.exists():
        return [
            DocDriftFinding(
                severity=_SEVERITY,
                file=str(root),
                message=(
                    "[REMOVED-GOVERNANCE-REFS] cannot scan: scan root does not "
                    f"exist ({root}). Verify the path; dangling references to "
                    "removed governance artifacts may go undetected."
                ),
            )
        ]

    findings: list[DocDriftFinding] = []

    for md_path in _iter_markdown(root):
        try:
            content = md_path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(
                DocDriftFinding(
                    severity=_SEVERITY,
                    file=safe_relative(md_path, repo_root=root),
                    message=(
                        "[REMOVED-GOVERNANCE-REFS] cannot read file "
                        f"({exc.__class__.__name__}): dangling references to "
                        "removed governance artifacts may go undetected."
                    ),
                )
            )
            continue

        matched_tokens = [token for token in _REMOVED_TOKENS if token in content]
        if not matched_tokens:
            continue

        rel = safe_relative(md_path, repo_root=root)
        if _is_allowlisted(rel):
            continue

        findings.append(
            DocDriftFinding(
                severity=_SEVERITY,
                file=rel,
                message=(
                    "[REMOVED-GOVERNANCE-REFS] references removed governance "
                    f"artifact(s): {', '.join(matched_tokens)}. Either reword to "
                    "make the historical context explicit, or add this file to "
                    "the allowlist in removed_governance_refs_checks.py with a "
                    "one-line justification."
                ),
            )
        )

    return findings
