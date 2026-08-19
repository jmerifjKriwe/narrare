"""In-memory export-job registry (D1 — no Alembic migration, RULE-14).

Owns the ``_JOBS`` dict (``job_id`` → :class:`_JobRecord`) and the token-based
artifact-delivery machinery. **Process-local by design**: jobs + artifact
metadata live in memory for the API process's lifetime and are lost on restart
(D1). A polled job whose record vanished on restart surfaces as a typed
:class:`ExportJobNotFoundError` (RULE-11 — queryable, never silent).

This module is **data, not a task** — it is NOT drained on shutdown. The
in-flight export *coroutines* live in :mod:`narrare.export.tasks`
(``_INFLIGHT_TASKS``); their drain flips a cancelled job to FAILED via
:func:`mark_failed`. The registry itself is just the state those coroutines
mutate.

Token security model
--------------------
The artifact token is generated with :func:`secrets.token_urlsafe(32)` and
validated by **hash comparison** — ``sha256(provided) == stored_hash`` — never
by storing the raw token as the validation credential. The raw token appears
*only* in the ``artifact_url`` delivery string (so :func:`get` can hand the
legitimate client the signed URL via polling); the validation secret stored on
the record is the one-way hash. A consumer who only reads
``artifact_token_hash`` cannot forge a consume (they would need the preimage).

Single-use: the first successful :func:`consume_artifact` flips
``artifact_consumed``; every subsequent attempt raises
:class:`ExportArtifactExpiredError`. Temp-file cleanup is belt-and-braces:
(1) the router unlinks the file via a ``BackgroundTask`` once the stream
completes, and (2) :func:`sweep_expired` (hooked into the lifespan periodic
cleanup) drops expired records and unlinks any remaining file.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote

import structlog

from narrare.export.contracts import (
    Artifact,
    ExportFormat,
    ExportJob,
    ExportJobStatus,
)
from narrare.export.errors import (
    ExportArtifactExpiredError,
    ExportJobNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from uuid import UUID

logger = structlog.get_logger(__name__)

#: Artifact download-token lifetime from :func:`mark_completed`. Single-use;
#: after it elapses :func:`sweep_expired` drops the record + unlinks the file.
ARTIFACT_TTL: timedelta = timedelta(minutes=30)


def _now() -> datetime:
    """Timezone-aware "now" (mirrors the tz-aware DB columns)."""
    return datetime.now(UTC)


def _hash_token(token: str) -> str:
    """SHA-256 hex digest of the artifact token (the validation credential)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class _JobRecord:
    """Mutable in-memory state for one export job.

    ``artifact`` carries the full :class:`Artifact` (path + media_type +
    suggested_filename) so :func:`consume_artifact` can return it without
    re-reading disk. ``artifact_token_hash`` is the SHA-256 of the raw token —
    the raw token is NEVER stored as a field (only embedded in the delivery
    ``artifact_url`` on the public :class:`ExportJob`).
    """

    job: ExportJob
    artifact: Artifact | None = None
    artifact_token_hash: str | None = None
    artifact_expires_at: datetime | None = None
    artifact_consumed: bool = False


#: ``job_id`` → record. Process-local (D1). Accessed from the request path
#: (``get``/``consume_artifact``) and the background runner (``mark_*``).
#: Safe under the single-threaded asyncio loop: every mutation is synchronous
#: (no await between read and write).
_JOBS: dict[str, _JobRecord] = {}


def _artifact_url(job_id: str, token: str) -> str:
    """Build the signed download URL (token URL-encoded for safety)."""
    return f"/api/v1/export/jobs/{job_id}/artifact?token={quote(token, safe='')}"


def create(novel_id: UUID, fmt: ExportFormat) -> ExportJob:
    """Register a PENDING job and return its public view."""
    job = ExportJob(
        job_id=secrets.token_urlsafe(16),
        novel_id=novel_id,
        format=fmt,
        status=ExportJobStatus.PENDING,
        created_at=_now(),
        updated_at=_now(),
    )
    _JOBS[job.job_id] = _JobRecord(job=job)
    logger.info("export_job_created", job_id=job.job_id, novel_id=str(novel_id), format=fmt.value)
    return job


def get(job_id: str) -> ExportJob:
    """Return the public job view. Raises :class:`ExportJobNotFoundError`."""
    record = _JOBS.get(job_id)
    if record is None:
        raise ExportJobNotFoundError(f"Export job '{job_id}' not found")
    return record.job


def _touch(record: _JobRecord) -> None:
    record.job.updated_at = _now()


def mark_running(job_id: str) -> None:
    """Flip a PENDING job to RUNNING (idempotent no-op if the job was swept)."""
    record = _JOBS.get(job_id)
    if record is None:
        logger.warning("export_mark_running_unknown_job", job_id=job_id)
        return
    record.job.status = ExportJobStatus.RUNNING
    _touch(record)


def mark_completed(job_id: str, artifact: Artifact) -> None:
    """Flip a job to COMPLETED + register its artifact + issue a single-use token.

    Generates the token internally (``secrets.token_urlsafe(32)``), stores only
    its SHA-256 hash as the validation credential, and embeds the raw token in
    the delivery ``artifact_url`` on the public job (so polling clients receive
    the signed URL). Idempotent no-op if the job was swept.
    """
    record = _JOBS.get(job_id)
    if record is None:
        logger.warning("export_mark_completed_unknown_job", job_id=job_id)
        return
    token = secrets.token_urlsafe(32)
    record.artifact = artifact
    record.artifact_token_hash = _hash_token(token)
    record.artifact_expires_at = _now() + ARTIFACT_TTL
    record.artifact_consumed = False
    record.job.status = ExportJobStatus.COMPLETED
    record.job.artifact_url = _artifact_url(job_id, token)
    record.job.error = None
    _touch(record)
    logger.info(
        "export_job_completed",
        job_id=job_id,
        format=artifact.format.value,
        expires_at=record.artifact_expires_at.isoformat(),
    )


def mark_failed(job_id: str, error: str) -> None:
    """Flip a job to FAILED with a typed reason (RULE-11 queryable lost-job).

    Used by the runner on renderer failure and by the drain ``_on_done``
    callback on cancellation (``"cancelled (server shutdown)"``). Idempotent
    no-op if the job was already swept.
    """
    record = _JOBS.get(job_id)
    if record is None:
        logger.warning("export_mark_failed_unknown_job", job_id=job_id)
        return
    record.job.status = ExportJobStatus.FAILED
    record.job.error = error
    _touch(record)
    logger.warning("export_job_failed", job_id=job_id, error=error)


def consume_artifact(job_id: str, token: str) -> Artifact:
    """Validate the token and return the single-use :class:`Artifact`.

    Raises :class:`ExportJobNotFoundError` for unknown ids and
    :class:`ExportArtifactExpiredError` if the job is not COMPLETED, the token
    is wrong, the artifact was already consumed, or the TTL elapsed. The
    caller (router) is responsible for unlinking the temp file after streaming.
    """
    record = _JOBS.get(job_id)
    if record is None:
        raise ExportJobNotFoundError(f"Export job '{job_id}' not found")

    if record.artifact is None or record.artifact_token_hash is None:
        raise ExportArtifactExpiredError(f"Export job '{job_id}' has no artifact")
    if record.artifact_consumed:
        raise ExportArtifactExpiredError(f"Artifact for job '{job_id}' already consumed")
    if record.artifact_expires_at is not None and _now() > record.artifact_expires_at:
        raise ExportArtifactExpiredError(f"Artifact for job '{job_id}' has expired")
    if _hash_token(token) != record.artifact_token_hash:
        # Wrong token → treat as expired/gone (never reveal whether it existed).
        raise ExportArtifactExpiredError(f"Invalid artifact token for job '{job_id}'")

    record.artifact_consumed = True
    _touch(record)
    logger.info("export_artifact_consumed", job_id=job_id)
    return record.artifact


def sweep_expired(now: Callable[[], datetime] = _now) -> int:
    """Drop COMPLETED jobs past their artifact TTL + unlink their temp files.

    Idempotent. Returns the number of records dropped. Also unlinks the temp
    file of a record whose artifact was already consumed but whose file is
    still on disk (defence-in-depth — the router's BackgroundTask is the
    primary cleanup). Hooked into the lifespan periodic-cleanup loop.
    """
    dropped = 0
    for job_id in list(_JOBS):
        record = _JOBS[job_id]
        if record.artifact_expires_at is None:
            continue
        if now() <= record.artifact_expires_at:
            continue
        if record.artifact is not None:
            _safe_unlink(record.artifact.path)
        del _JOBS[job_id]
        dropped += 1
        logger.info("export_job_swept", job_id=job_id)
    return dropped


def _safe_unlink(path: Path) -> None:
    """Best-effort unlink (the file may already be gone)."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("export_artifact_unlink_failed", path=str(path), error=str(exc))
