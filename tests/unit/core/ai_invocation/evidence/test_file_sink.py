"""Tests for FileEvidenceSink.

Covers:
1. Writes evidence to file — each line is valid JSON.
2. Each record has ISO-8601 timestamp.
3. Multiple records produce multiple lines (append).
4. Graceful degradation on I/O error (no exception propagated).
5. Creates evidence directory if missing.
6. No raw prompt text in output (privacy guarantee).
7. evidence_path property returns correct path.

See:
    ADR-041, INFRA-013 §P3, CONSTRAINTS.md RULE-03/RULE-10.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.evidence import FileEvidenceSink
from narrare_core.ai_invocation.models import FeatureInvocationEvidence

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_evidence(**overrides: object) -> FeatureInvocationEvidence:
    """Create a minimal FeatureInvocationEvidence for tests."""
    defaults: dict[str, object] = {
        "feature_id": "writing/new_chapter",
        "intent": "write",
        "prompt_route": "writing/en/new_chapter",
        "preference_status": PreferenceStatus.PROVIDED,
        "kb_suggested_status": KBSuggestedStatus.PROVIDED,
        "final_prompt_validated": True,
        "audit_state": AuditState.RUNTIME_VERIFIED,
    }
    defaults.update(overrides)
    return FeatureInvocationEvidence(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def evidence_dir(tmp_path: Path) -> Generator[Path]:
    """Provide an isolated evidence directory under tmp_path."""
    ev_dir = tmp_path / "evidence"
    yield ev_dir


@pytest.fixture
def sink(evidence_dir: Path) -> Generator[FileEvidenceSink]:
    """Create a FileEvidenceSink pointing at the temp evidence dir."""
    s = FileEvidenceSink(evidence_dir=evidence_dir)
    yield s


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestFileEvidenceSinkWrites:
    """Writes evidence to file; each line is valid JSON."""

    @pytest.mark.asyncio
    async def test_writes_valid_json_line(self, sink: FileEvidenceSink, evidence_dir: Path) -> None:
        """record() writes exactly one valid JSON line."""
        evidence = make_evidence()
        await sink.record(evidence)

        file_path = evidence_dir / "invocations.jsonl"
        assert file_path.exists()
        lines = file_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        assert parsed["feature_id"] == "writing/new_chapter"

    @pytest.mark.asyncio
    async def test_all_evidence_fields_present(
        self, sink: FileEvidenceSink, evidence_dir: Path
    ) -> None:
        """All FeatureInvocationEvidence fields appear in the JSON record."""
        evidence = make_evidence(
            feature_id="writing/extend",
            intent="extend",
            mode="extend",
            prompt_route="writing/en/extend",
            preference_status=PreferenceStatus.MANUAL,
            kb_suggested_status=KBSuggestedStatus.BUDGET_REJECTED,
            output_budget_profile="long_texts",
            final_prompt_validated=True,
            validation_errors=("missing_var:kb_context",),
            audit_state=AuditState.ADOPTED,
        )
        await sink.record(evidence)

        file_path = evidence_dir / "invocations.jsonl"
        parsed = json.loads(file_path.read_text(encoding="utf-8"))

        assert parsed["feature_id"] == "writing/extend"
        assert parsed["intent"] == "extend"
        assert parsed["mode"] == "extend"
        assert parsed["prompt_route"] == "writing/en/extend"
        assert parsed["preference_status"] == "manual"
        assert parsed["kb_suggested_status"] == "budget_rejected"
        assert parsed["output_budget_profile"] == "long_texts"
        assert parsed["final_prompt_validated"] is True
        assert parsed["validation_errors"] == ["missing_var:kb_context"]
        assert parsed["audit_state"] == "adopted"


class TestFileEvidenceSinkTimestamp:
    """Each record has an ISO-8601 timestamp."""

    @pytest.mark.asyncio
    async def test_timestamp_is_iso8601(self, sink: FileEvidenceSink, evidence_dir: Path) -> None:
        """Written JSON contains a parseable ISO-8601 timestamp."""
        evidence = make_evidence()
        await sink.record(evidence)

        file_path = evidence_dir / "invocations.jsonl"
        parsed = json.loads(file_path.read_text(encoding="utf-8"))

        assert "timestamp" in parsed
        timestamp_str = parsed["timestamp"]
        assert isinstance(timestamp_str, str)
        # Verify ISO-8601 by parsing
        parsed_dt = datetime.fromisoformat(timestamp_str)
        assert parsed_dt.tzinfo is not None  # timezone-aware

    @pytest.mark.asyncio
    async def test_timestamp_is_recent(self, sink: FileEvidenceSink, evidence_dir: Path) -> None:
        """Timestamp is within the last few seconds."""
        evidence = make_evidence()
        await sink.record(evidence)

        file_path = evidence_dir / "invocations.jsonl"
        parsed = json.loads(file_path.read_text(encoding="utf-8"))

        parsed_dt = datetime.fromisoformat(parsed["timestamp"])
        now = datetime.now(parsed_dt.tzinfo)
        delta_seconds = abs((now - parsed_dt).total_seconds())
        assert delta_seconds < 5, f"Timestamp is {delta_seconds}s from now"


class TestFileEvidenceSinkAppends:
    """Multiple records produce multiple lines."""

    @pytest.mark.asyncio
    async def test_appends_multiple_records(
        self, sink: FileEvidenceSink, evidence_dir: Path
    ) -> None:
        """Multiple record() calls produce one line each."""
        ev1 = make_evidence(feature_id="writing/new_chapter")
        ev2 = make_evidence(feature_id="writing/extend")
        ev3 = make_evidence(feature_id="writing/revise")

        await sink.record(ev1)
        await sink.record(ev2)
        await sink.record(ev3)

        file_path = evidence_dir / "invocations.jsonl"
        lines = file_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3

        parsed = [json.loads(line) for line in lines]
        assert parsed[0]["feature_id"] == "writing/new_chapter"
        assert parsed[1]["feature_id"] == "writing/extend"
        assert parsed[2]["feature_id"] == "writing/revise"


class TestFileEvidenceSinkIOError:
    """Graceful degradation on I/O error — no exception propagated."""

    @pytest.mark.asyncio
    async def test_io_error_does_not_raise(self, evidence_dir: Path) -> None:
        """record() logs and swallows I/O errors instead of raising."""
        sink = FileEvidenceSink(evidence_dir=evidence_dir)

        # Make mkdir succeed but open fail
        evidence_dir.mkdir(parents=True, exist_ok=True)
        target_file = evidence_dir / "invocations.jsonl"
        target_file.mkdir()  # make it a directory so open() fails

        evidence = make_evidence()
        # Should NOT raise
        await sink.record(evidence)

    @pytest.mark.asyncio
    async def test_permission_error_does_not_raise(self, evidence_dir: Path) -> None:
        """record() handles permission errors gracefully."""
        sink = FileEvidenceSink(evidence_dir=evidence_dir)

        with patch("builtins.open", side_effect=PermissionError("denied")):
            evidence = make_evidence()
            await sink.record(evidence)  # Should not raise


class TestFileEvidenceSinkCreatesDir:
    """Creates .evidence/ directory if missing."""

    @pytest.mark.asyncio
    async def test_creates_missing_directory(self, tmp_path: Path) -> None:
        """record() creates the evidence directory when it does not exist."""
        ev_dir = tmp_path / "nested" / "evidence"
        sink = FileEvidenceSink(evidence_dir=ev_dir)

        assert not ev_dir.exists()
        await sink.record(make_evidence())
        assert ev_dir.exists()
        assert (ev_dir / "invocations.jsonl").exists()


class TestFileEvidenceSinkPrivacy:
    """No raw prompt text in output (privacy guarantee)."""

    @pytest.mark.asyncio
    async def test_no_prompt_text_in_json(self, sink: FileEvidenceSink, evidence_dir: Path) -> None:
        """Written JSON does not contain raw prompt text or user prose."""
        evidence = make_evidence()
        await sink.record(evidence)

        file_path = evidence_dir / "invocations.jsonl"
        content = file_path.read_text(encoding="utf-8")

        # FeatureInvocationEvidence is privacy-safe by design:
        # only identifiers, statuses, booleans, and structured metadata.
        # Verify no unexpected prose-like fields snuck in.
        parsed = json.loads(content)
        # All values should be primitives, enums-as-strings, or lists of strings
        for key, value in parsed.items():
            if isinstance(value, str):
                # No multi-sentence prose — max a short identifier
                assert "." not in value or len(value) < 50, (
                    f"Field '{key}' looks like prose: {value!r}"
                )


class TestFileEvidenceSinkPath:
    """evidence_path property returns the correct path."""

    def test_evidence_path_default_filename(self, evidence_dir: Path) -> None:
        """evidence_path uses default filename 'invocations.jsonl'."""
        sink = FileEvidenceSink(evidence_dir=evidence_dir)
        assert sink.evidence_path == evidence_dir / "invocations.jsonl"

    def test_evidence_path_custom_filename(self, evidence_dir: Path) -> None:
        """evidence_path uses custom filename when provided."""
        sink = FileEvidenceSink(evidence_dir=evidence_dir, filename="custom.jsonl")
        assert sink.evidence_path == evidence_dir / "custom.jsonl"

    def test_evidence_path_string_dir(self, tmp_path: Path) -> None:
        """evidence_path works with string evidence_dir."""
        sink = FileEvidenceSink(evidence_dir=str(tmp_path / "ev"))
        assert sink.evidence_path == tmp_path / "ev" / "invocations.jsonl"
