"""Check 12 — Visible i18n fallback string scanner.

Prevents reintroduction of visible English fallback strings in KB and
editor Studio components.  When a ``t(...)`` call is followed by
``|| "English"`` or ``?? "English"``, the literal fallback silently
preserves untranslated drift — tests that mock ``t()`` as a key-returning
function never exercise the fallback path.

Motivated by CR-AUFG-07-14 (Visible i18n fallback prevention).

Scope (production only):
  - ``packages/web/components/studio/kb/**/*.{ts,tsx}``
  - ``packages/web/components/studio/editor/**/*.{ts,tsx}``

Excluded:
  - ``__tests__/`` directories
  - ``*.test.*`` files
  - ``*.spec.*`` files

Match patterns (per CR-07 v3 Phase A plan Task 5):
  1. ``t(...) || "..."`` — translation call with OR fallback
  2. ``t(...) ?? "..."`` — translation call with nullish fallback
  3. ``?? "Capital..."`` — nullish coalescing with capitalized literal
  4. ``|| "Capital..."`` — logical OR with capitalized literal

Patterns 1+2 catch all ``t()`` fallbacks (including lowercase).
Patterns 3+4 catch all capitalized-literal fallbacks from any LHS.
Lowercase literal fallbacks without a ``t()`` call (e.g. CSS class names)
are NOT flagged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from ._shared import REPO_ROOT, display_path, rg_files

GATE = "check_12_visible_i18n_fallbacks"

DEFAULT_ALLOWLIST = (
    REPO_ROOT
    / "scripts"
    / "checks"
    / "_ai_interaction_checks"
    / "visible_i18n_fallback_allowlist.yaml"
)

# Production directories in scope.
_SCAN_DIRS: tuple[str, ...] = (
    "packages/web/components/studio/kb",
    "packages/web/components/studio/editor",
)

# Pattern group A: ``t(...)`` call followed by ``||`` or ``??`` and any
# string literal (single, double, or backtick).  Allows for extra closing
# parens between the call and the operator, e.g. ``(t("key")) ?? "x"``.
_T_CALL_FALLBACK_RE = re.compile(
    r"""t\([^)]*\)\s*\)*\s*(?:\|\||\?\?)\s*["'`]""",
)

# Pattern group B: ``||`` or ``??`` followed by a Capitalized string
# literal.  Capitalized = starts with [A-Z].  Lowercase literals (CSS
# class names, data attributes) are intentionally NOT flagged.
_CAPITAL_LITERAL_FALLBACK_RE = re.compile(
    r"""(?:\|\||\?\?)\s*["'`][A-Z]""",
)

# Pre-filter pattern for rg: any ``||`` or ``??`` followed by a quote.
# Used to quickly narrow candidate files before line-level analysis.
_RG_CANDIDATE_PATTERN = r"""(\|\||\?\?)\s*["'`]"""

_REMEDIATION = (
    "Remove the literal fallback; rely on the registered i18n key. "
    "If this is a justified non-visible default, add a governed entry "
    "to visible_i18n_fallback_allowlist.yaml with path, line_regex, "
    "owner, reason, and review_trigger."
)


@dataclass(frozen=True, slots=True)
class VisibleI18nFallbackFinding:
    """A single visible i18n fallback violation."""

    path: Path
    line: int
    snippet: str
    remediation: str


def _is_test_path(path: Path) -> bool:
    """Return ``True`` if *path* is a test or spec file."""
    name = path.name
    return ".test." in name or ".spec." in name or "__tests__" in path.parts


def _find_visible_i18n_fallbacks_in_source(
    source: str,
    path: Path,
) -> list[VisibleI18nFallbackFinding]:
    """Find visible i18n fallback violations in *source* text.

    Scans line by line.  A line is flagged if it matches either pattern
    group.  Each line produces at most one finding (deduplicated).
    """
    findings: list[VisibleI18nFallbackFinding] = []

    for line_num, line in enumerate(source.splitlines(), start=1):
        matched = _T_CALL_FALLBACK_RE.search(line) is not None
        if not matched:
            matched = _CAPITAL_LITERAL_FALLBACK_RE.search(line) is not None

        if matched:
            snippet = line.strip()[:120]
            findings.append(
                VisibleI18nFallbackFinding(
                    path=path,
                    line=line_num,
                    snippet=snippet,
                    remediation=_REMEDIATION,
                )
            )

    return findings


def _load_allowlist(allowlist_path: Path) -> list[dict[str, str]]:
    """Load the YAML allowlist; returns ``[]`` if missing or empty."""
    if not allowlist_path.exists():
        return []
    data: Any = yaml.safe_load(allowlist_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    typed_data = cast("dict[str, Any]", data)
    raw: object = typed_data.get("entries", [])
    if not isinstance(raw, list):
        return []
    entries_list = cast("list[Any]", raw)
    entries: list[dict[str, str]] = []
    for entry in entries_list:
        if isinstance(entry, dict):
            entries.append(cast("dict[str, str]", entry))
    return entries


def _is_allowlisted(
    finding: VisibleI18nFallbackFinding,
    allowlist: list[dict[str, str]],
    root: Path,
) -> bool:
    """Return ``True`` if *finding* matches a governed allowlist entry."""
    rel_path = display_path(finding.path, base=root)
    for entry in allowlist:
        entry_path = entry.get("path", "")
        if entry_path != rel_path:
            continue
        line_regex = entry.get("line_regex")
        if not line_regex:
            # No regex means any line in this file is allowlisted.
            return True
        if re.search(line_regex, finding.snippet):
            return True
    return False


def check_visible_i18n_fallbacks(
    root: Path = REPO_ROOT,
    allowlist_path: Path = DEFAULT_ALLOWLIST,
) -> tuple[list[str], list[str]]:
    """Check 12: No visible i18n fallback strings in KB/editor components.

    Returns ``(passes, violations)``.  Each violation names the relative
    path, line number, snippet, and remediation guidance.
    """
    allowlist = _load_allowlist(allowlist_path)

    all_findings: list[VisibleI18nFallbackFinding] = []

    for scan_rel in _SCAN_DIRS:
        scan_dir = root / scan_rel
        if not scan_dir.exists():
            continue

        candidate_files = rg_files(
            _RG_CANDIDATE_PATTERN,
            "-g",
            "*.ts",
            "-g",
            "*.tsx",
            "-g",
            "!*.test.*",
            "-g",
            "!*.spec.*",
            "-g",
            "!__tests__/*",
            path=str(scan_dir),
        )

        for filepath_str in candidate_files:
            fp = Path(filepath_str)
            if _is_test_path(fp):
                continue

            source = fp.read_text(encoding="utf-8", errors="replace")
            findings = _find_visible_i18n_fallbacks_in_source(source, fp)
            all_findings.extend(findings)

    violations: list[str] = []
    suppressed = 0
    for finding in all_findings:
        if _is_allowlisted(finding, allowlist, root):
            suppressed += 1
            continue
        rel = display_path(finding.path, base=root)
        violations.append(
            f"{rel}:{finding.line}: visible i18n fallback string\n"
            f"    {finding.snippet}\n"
            f"  -> {finding.remediation}"
        )

    passes: list[str] = []
    if not violations:
        passes.append("No visible i18n fallback strings in KB/editor components +")

    return passes, violations
