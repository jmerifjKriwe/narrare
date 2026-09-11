"""Unit tests for the in-memory export-job registry (D1).

Covers the full job lifecycle (create → running → completed → consume), the
token security model (sha256-hashed, single-use, TTL), and the periodic sweep
(drops expired records + unlinks their temp files).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest

from narrare.export import registry
from narrare.export.contracts import Artifact, ExportJobStatus
from narrare.export.errors import (
    ExportArtifactExpiredError,
    ExportJobNotFoundError,
)
from narrare.export.options import ExportFormat
from tests.unit.api.export.conftest import make_options

NOVEL_ID = UUID("00000000-0000-0000-0000-000000000001")
# Caller that owns every seeded job (owner-binding tests live in
# test_export_ownership.py; here OWNER is just the mechanical caller).
OWNER = UUID("00000000-0000-0000-0000-0000000000ff")


def _token_from_url(artifact_url: str) -> str:
    """Extract the raw token the registry embedded in the delivery URL."""
    return parse_qs(urlparse(artifact_url).query)["token"][0]


def _make_artifact(path: Path, fmt: ExportFormat = ExportFormat.MARKDOWN) -> Artifact:
    path.write_text("payload", encoding="utf-8")
    return Artifact(
        format=fmt,
        path=path,
        media_type=f"application/x-{fmt.value}",
        suggested_filename=f"out.{fmt.value}",
    )


class TestJobLifecycle:
    """create → mark_running → mark_completed → consume_artifact (single-use)."""

    @pytest.mark.asyncio
    async def test_create_returns_pending_job(self) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.PDF)
        assert job.status is ExportJobStatus.PENDING
        assert job.format is ExportFormat.PDF
        assert job.artifact_url is None
        assert job.error is None
        # The job is retrievable by id.
        assert registry.get(job.job_id, OWNER).job_id == job.job_id

    @pytest.mark.asyncio
    async def test_full_lifecycle_consume_then_second_consume_raises(self, tmp_path: Path) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.MARKDOWN)
        registry.mark_running(job.job_id)
        assert registry.get(job.job_id, OWNER).status is ExportJobStatus.RUNNING

        artifact = _make_artifact(tmp_path / "art.md")
        registry.mark_completed(job.job_id, artifact)

        completed = registry.get(job.job_id, OWNER)
        assert completed.status is ExportJobStatus.COMPLETED
        assert completed.artifact_url is not None

        token = _token_from_url(completed.artifact_url)  # type: ignore[arg-type]
        consumed = registry.consume_artifact(job.job_id, token, OWNER)
        assert consumed.path == artifact.path

        # Single-use: the second consume raises.
        with pytest.raises(ExportArtifactExpiredError):
            registry.consume_artifact(job.job_id, token, OWNER)


class TestTokenSecurity:
    """The token is validated by sha256 comparison — the raw token is never the
    validation credential (it appears only in the delivery artifact_url)."""

    @pytest.mark.asyncio
    async def test_stored_hash_is_sha256_not_raw_token(self, tmp_path: Path) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.PDF)
        registry.mark_completed(job.job_id, _make_artifact(tmp_path / "a.pdf", ExportFormat.PDF))

        record = registry._JOBS[job.job_id]
        token = _token_from_url(registry.get(job.job_id, OWNER).artifact_url)  # type: ignore[arg-type]

        expected_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        assert record.artifact_token_hash == expected_hash
        # The validation credential is the hash, never the raw token.
        assert record.artifact_token_hash != token

    @pytest.mark.asyncio
    async def test_wrong_token_is_rejected_as_expired(self, tmp_path: Path) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.EPUB)
        registry.mark_completed(job.job_id, _make_artifact(tmp_path / "a.epub", ExportFormat.EPUB))

        with pytest.raises(ExportArtifactExpiredError):
            registry.consume_artifact(job.job_id, "totally-wrong-token", OWNER)

    @pytest.mark.asyncio
    async def test_consume_before_completed_raises(self) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.MARKDOWN)
        registry.mark_running(job.job_id)
        with pytest.raises(ExportArtifactExpiredError):
            registry.consume_artifact(job.job_id, "any", OWNER)


class TestSweepExpired:
    """sweep_expired drops expired COMPLETED records + unlinks temp files."""

    @pytest.mark.asyncio
    async def test_sweep_drops_expired_job_and_unlinks_file(self, tmp_path: Path) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.MARKDOWN)
        artifact = _make_artifact(tmp_path / "gone.md")
        registry.mark_completed(job.job_id, artifact)
        assert artifact.path.exists()

        # Force the artifact past its TTL (set the expiry clearly in the past).
        record = registry._JOBS[job.job_id]
        record.artifact_expires_at = datetime.now(UTC) - timedelta(minutes=1)

        dropped = registry.sweep_expired()

        assert dropped == 1
        assert job.job_id not in registry._JOBS
        assert not artifact.path.exists()  # temp file unlinked

    @pytest.mark.asyncio
    async def test_sweep_keeps_unexpired_jobs(self, tmp_path: Path) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.MARKDOWN)
        registry.mark_completed(job.job_id, _make_artifact(tmp_path / "keep.md"))

        assert registry.sweep_expired() == 0
        assert job.job_id in registry._JOBS

    @pytest.mark.asyncio
    async def test_sweep_is_idempotent(self, tmp_path: Path) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.MARKDOWN)
        registry.mark_completed(job.job_id, _make_artifact(tmp_path / "idem.md"))
        record = registry._JOBS[job.job_id]
        assert record.artifact_expires_at is not None
        record.artifact_expires_at = record.artifact_expires_at - timedelta(hours=1)

        assert registry.sweep_expired() == 1
        # Second sweep has nothing left to drop.
        assert registry.sweep_expired() == 0


class TestGetAndMarkFailed:
    """get/mark_failed edge cases."""

    @pytest.mark.asyncio
    async def test_get_unknown_raises(self) -> None:
        with pytest.raises(ExportJobNotFoundError):
            registry.get("does-not-exist", OWNER)

    @pytest.mark.asyncio
    async def test_consume_unknown_raises_not_found(self) -> None:
        with pytest.raises(ExportJobNotFoundError):
            registry.consume_artifact("nope", "token", OWNER)

    @pytest.mark.asyncio
    async def test_mark_failed_records_reason(self) -> None:
        job = registry.create(NOVEL_ID, OWNER, ExportFormat.PDF)
        registry.mark_failed(job.job_id, "renderer exploded")
        failed = registry.get(job.job_id, OWNER)
        assert failed.status is ExportJobStatus.FAILED
        assert failed.error == "renderer exploded"

    @pytest.mark.asyncio
    async def test_mark_running_on_swept_job_is_safe_noop(self) -> None:
        # A mark_* call on a job that no longer exists must not raise (the
        # drain _on_done callback relies on this tolerance).
        registry.mark_running("ghost-job")
        registry.mark_failed("ghost-job", "late")
        registry.mark_completed("ghost-job", _make_artifact(Path("/tmp/x")))

    @pytest.mark.asyncio
    async def test_options_roundtrip(self) -> None:
        # Sanity: the options helper builds a valid MARKDOWN ExportOptions.
        opts = make_options(ExportFormat.EPUB)
        assert opts.format is ExportFormat.EPUB
