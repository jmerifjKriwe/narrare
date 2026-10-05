"""Shared fakes + fixtures for the bulk extraction runner tests.

One helper module so ``test_runner.py`` stays under the RULE-04 hard
limit; mirrors the ``tests/unit/api/kb/_apply_extraction_helpers.py``
precedent (underscore-prefixed, import-only helpers — no tests here).

The fakes sit at the plan's seams (monkeypatch style of
``tests/unit/api/export/test_tasks.py``): ``runner.registry`` (recording
wrapper over the real registry), ``runner._service_factory``,
``runner._pacer_acquire``, and ``narrare._app.database.get_session_factory``.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.kb.bulk_extraction import registry
from narrare.kb.bulk_extraction.contracts import BulkChapterRef
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from narrare.kb.bulk_extraction.contracts import BulkJobKind

NOVEL_ID = uuid4()
OWNER = uuid4()

#: Sentinel outcome: the fake service blocks forever (drain test).
_BLOCK = object()


async def _noop_pacer() -> None:
    return None


def _ref(position: int) -> BulkChapterRef:
    return BulkChapterRef(uuid4(), f"Chapter {position}", position)


def _output(n_items: int) -> ExtractionOutput:
    return ExtractionOutput(
        results=[
            ExtractionItem(
                item_type="new_entity", name=f"item-{i}", confidence=0.9, source_text="s"
            )
            for i in range(n_items)
        ],
    )


def _make_job(*positions: int) -> tuple[str, list[UUID]]:
    """Create a real registry job; return (job_id, position-sorted chapter ids)."""
    job_id = registry.create(NOVEL_ID, OWNER, [_ref(p) for p in positions]).job_id
    ids = [c.chapter_id for c in registry.status(job_id, OWNER).chapters]
    return job_id, ids


async def _wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met before timeout")
        await asyncio.sleep(0.01)


class _RecordingRegistry:
    """Delegates to the real registry while recording the mutation order."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def mark_job_running(self, job_id: str) -> None:
        self.calls.append("mark_job_running")
        registry.mark_job_running(job_id)

    def mark_chapter_running(self, job_id: str, chapter_id: UUID) -> None:
        self.calls.append("mark_chapter_running")
        registry.mark_chapter_running(job_id, chapter_id)

    def mark_chapter_done(self, job_id: str, chapter_id: UUID, output: ExtractionOutput) -> None:
        self.calls.append("mark_chapter_done")
        registry.mark_chapter_done(job_id, chapter_id, output)

    def mark_chapter_failed(self, job_id: str, chapter_id: UUID, error: str) -> None:
        self.calls.append("mark_chapter_failed")
        registry.mark_chapter_failed(job_id, chapter_id, error)

    def mark_job_completed(self, job_id: str) -> None:
        self.calls.append("mark_job_completed")
        registry.mark_job_completed(job_id)

    def mark_job_failed(self, job_id: str, error: str) -> None:
        self.calls.append("mark_job_failed")
        registry.mark_job_failed(job_id, error)

    def mark_cancelled(self, job_id: str, reason: str) -> None:
        self.calls.append("mark_cancelled")
        registry.mark_cancelled(job_id, reason)

    def kind_of(self, job_id: str) -> BulkJobKind:
        return registry.kind_of(job_id)

    def mark_dedup(self, job_id: str, suggestion_count: int) -> None:
        self.calls.append("mark_dedup")
        registry.mark_dedup(job_id, suggestion_count)

    def mark_dedup_unavailable(self, job_id: str) -> None:
        self.calls.append("mark_dedup_unavailable")
        registry.mark_dedup_unavailable(job_id)

    def cancel_requested(self, job_id: str) -> bool:
        return registry.cancel_requested(job_id)

    def pending_chapter_ids(self, job_id: str) -> list[UUID]:
        return registry.pending_chapter_ids(job_id)


class _ScriptedService:
    """ExtractionService stand-in: per-chapter scripted outcomes.

    Outcome values: ``ExtractionOutput`` (success), ``BaseException``
    instance (raise — incl. ``CancelledError``), ``_BLOCK`` (never
    returns; drain test). The ``on_extract`` hook fires at the START of
    each extraction (sync — it must never await).
    """

    def __init__(
        self,
        outcomes: dict[UUID, ExtractionOutput | BaseException | object],
        log: _ScriptedServiceFactory,
    ) -> None:
        self._outcomes = outcomes
        self._log = log

    async def extract_from_chapter(
        self, novel_id: UUID, chapter_id: UUID, user_id: UUID
    ) -> ExtractionOutput:
        outcome = self._outcomes[chapter_id]
        self._log.extract_calls.append((chapter_id, self._log.last_session))
        if self._log.on_extract is not None:
            self._log.on_extract(chapter_id)
        if outcome is _BLOCK:
            await asyncio.Event().wait()
        if isinstance(outcome, BaseException):  # incl. CancelledError (not an Exception)
            raise outcome
        assert isinstance(outcome, ExtractionOutput)
        return outcome


class _ScriptedServiceFactory:
    """The ``_service_factory`` seam fake: builds scripted services.

    Records the session each chapter's service was built with — the
    runner must hand a fresh own-session to every chapter.
    """

    def __init__(
        self,
        outcomes: dict[UUID, ExtractionOutput | BaseException | object],
        *,
        on_extract: Callable[[UUID], None] | None = None,
    ) -> None:
        self.outcomes = outcomes
        self.on_extract = on_extract
        self.extract_calls: list[tuple[UUID, object]] = []
        self.built_with: list[object] = []
        self.last_session: object = None

    def __call__(self, session: object, owner_id: UUID, novel_id: UUID) -> _ScriptedService:
        self.built_with.append((session, owner_id, novel_id))
        self.last_session = session
        return _ScriptedService(self.outcomes, self)


class _FakeSession:
    def __init__(self, log: _FakeSessions) -> None:
        self._log = log

    async def __aenter__(self) -> _FakeSession:
        self._log.entered.append(self)
        return self

    async def __aexit__(self, *exc: object) -> bool:
        self._log.closed.append(self)
        return False


class _FakeSessions:
    """Session factory fake: captures one session context per ``__call__``."""

    def __init__(self) -> None:
        self.open_calls = 0
        self.entered: list[_FakeSession] = []
        self.closed: list[_FakeSession] = []

    def __call__(self) -> _FakeSession:
        self.open_calls += 1
        return _FakeSession(self)
