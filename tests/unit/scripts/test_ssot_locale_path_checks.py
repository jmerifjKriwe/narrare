"""Tests for doc_drift.ssot_locale_path_checks — RULE-16 locale-path parity.

Verifies the SSOT locale-path guard that pins CONSTRAINTS.md RULE-16 to the
real frontend-loader import path (packages/i18n/messages/, per ADR-013).

See: ADR-041 Decision 2, docs/_shared/CONSTRAINTS.md RULE-16.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


from doc_drift.ssot_locale_path_checks import check_ssot_locale_path  # noqa: E402

# A minimal valid request.ts snippet mirroring the real dynamic import.
_VALID_REQUEST_TS = "const mod = await import(`../../../i18n/messages/${locale}/${ns}.json`);\n"

# CONSTRAINTS.md body referencing the canonical locale path (RULE-16 happy path).
_VALID_CONSTRAINTS = """\
### RULE-16 · ...
Files must exist: packages/i18n/messages/en/generation.json
"""


class TestHappyPath:
    """When CONSTRAINTS.md matches reality, no findings."""

    def test_valid_constraints_and_request_yields_no_findings(self, tmp_path: Path) -> None:
        constraints = tmp_path / "CONSTRAINTS.md"
        constraints.write_text(_VALID_CONSTRAINTS, encoding="utf-8")
        request_ts = tmp_path / "request.ts"
        request_ts.write_text(_VALID_REQUEST_TS, encoding="utf-8")

        findings = check_ssot_locale_path(constraints_path=constraints, request_ts_path=request_ts)

        assert findings == []


class TestStalePathGuard:
    """The stale packages/web/messages path must be flagged as critical."""

    def test_stale_locale_path_in_constraints_is_critical(self, tmp_path: Path) -> None:
        constraints = tmp_path / "CONSTRAINTS.md"
        constraints.write_text(
            "// packages/web/messages/en/generation.json  <- must exist\n"
            "and packages/i18n/messages/de/generation.json\n",
            encoding="utf-8",
        )
        request_ts = tmp_path / "request.ts"
        request_ts.write_text(_VALID_REQUEST_TS, encoding="utf-8")

        findings = check_ssot_locale_path(constraints_path=constraints, request_ts_path=request_ts)

        stale = [f for f in findings if "stale locale path" in f.message]
        assert len(stale) == 1
        assert stale[0].severity == "critical"
        # File reference must pinpoint the offending line.
        assert "CONSTRAINTS.md:1" in stale[0].file

    def test_multiple_stale_lines_each_reported(self, tmp_path: Path) -> None:
        constraints = tmp_path / "CONSTRAINTS.md"
        constraints.write_text(
            "// packages/web/messages/en/x.json\n"
            "// packages/web/messages/de/x.json\n"
            "// packages/web/messages/fr/x.json\n",
            encoding="utf-8",
        )
        request_ts = tmp_path / "request.ts"
        request_ts.write_text(_VALID_REQUEST_TS, encoding="utf-8")

        findings = check_ssot_locale_path(constraints_path=constraints, request_ts_path=request_ts)

        stale = [f for f in findings if "stale locale path" in f.message]
        assert len(stale) == 3
        # The canonical path is also absent here -> presence guard fires too.
        presence = [f for f in findings if "no longer references the canonical" in f.message]
        assert len(presence) == 1


class TestCanonicalPresenceGuard:
    """Absence of the canonical path is flagged."""

    def test_missing_canonical_path_is_critical(self, tmp_path: Path) -> None:
        constraints = tmp_path / "CONSTRAINTS.md"
        # Neither stale nor canonical path present.
        constraints.write_text("### RULE-16 · ... some unrelated text\n", encoding="utf-8")
        request_ts = tmp_path / "request.ts"
        request_ts.write_text(_VALID_REQUEST_TS, encoding="utf-8")

        findings = check_ssot_locale_path(constraints_path=constraints, request_ts_path=request_ts)

        presence = [f for f in findings if "no longer references the canonical" in f.message]
        assert len(presence) == 1
        assert presence[0].severity == "critical"


class TestRealityCrossCheck:
    """If request.ts stops importing the canonical path, that is flagged."""

    def test_request_ts_no_longer_imports_canonical_path(self, tmp_path: Path) -> None:
        constraints = tmp_path / "CONSTRAINTS.md"
        constraints.write_text(_VALID_CONSTRAINTS, encoding="utf-8")
        request_ts = tmp_path / "request.ts"
        request_ts.write_text(
            "const mod = await import(`some/other/path/${locale}.json`);\n",
            encoding="utf-8",
        )

        findings = check_ssot_locale_path(constraints_path=constraints, request_ts_path=request_ts)

        cross = [f for f in findings if "no longer imports from" in f.message]
        assert len(cross) == 1
        assert cross[0].severity == "critical"


class TestMissingInputs:
    """Graceful handling of missing files."""

    def test_missing_constraints_returns_critical_only(self, tmp_path: Path) -> None:
        request_ts = tmp_path / "request.ts"
        request_ts.write_text(_VALID_REQUEST_TS, encoding="utf-8")

        findings = check_ssot_locale_path(
            constraints_path=tmp_path / "missing.md", request_ts_path=request_ts
        )

        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "not found" in findings[0].message

    def test_missing_request_ts_skips_cross_check(self, tmp_path: Path) -> None:
        # When request.ts is absent, the cross-check is skipped (only doc
        # assertions run) rather than erroring.
        constraints = tmp_path / "CONSTRAINTS.md"
        constraints.write_text(_VALID_CONSTRAINTS, encoding="utf-8")

        findings = check_ssot_locale_path(
            constraints_path=constraints,
            request_ts_path=tmp_path / "missing.ts",
        )

        assert findings == []


class TestRealRepoIntegration:
    """Smoke test against the real committed SSOT files (must pass post-fix)."""

    def test_real_constraints_and_request_ts_have_no_drift(self) -> None:
        findings = check_ssot_locale_path()
        assert findings == [], (
            "CONSTRAINTS.md RULE-16 locale path drifted from request.ts: "
            + "; ".join(f.message for f in findings)
        )
