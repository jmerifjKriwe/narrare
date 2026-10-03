"""Bulk extraction DI — production wiring for the router surface (ADR-092).

RULE-19: the factory stays SessionDep-based. Two thin adapters bind the T1
Protocols to the real collaborators (pure delegation, zero logic — RULE-06):

- :class:`RegistryJobStore` — the async ``BulkExtractionJobStore`` Protocol
  over the synchronous module-level registry functions. The registry's
  mutations are synchronous by design (single asyncio loop, no ``await``
  between read and write); the façade keeps the service transport-agnostic
  and unit-testable against Protocol fakes.
- :class:`RunnerDispatcher` — the ``BulkExtractionDispatcher`` over
  ``runner.dispatch`` (a module attribute is a plain function, not a bound
  method, so the Protocol needs this one-method façade).

``get_bulk_dispatcher`` exists as its OWN dependency so integration tests
can swap in a no-op dispatcher via ``app.dependency_overrides`` without
touching the store/gate wiring (the plan's prescribed runner bypass).

The pacer is deliberately NOT wired here: the runner resolves it lazily
(``runner._resolve_pacer_acquire``) until the pacer module lands in its
re-sliced task — the lazy seam stays, per the plan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID  # noqa: TC003 — FastAPI DI runtime annotation resolution

from fastapi import Depends

from narrare._app.dependencies import (  # noqa: TC001 — FastAPI DI runtime
    CurrentUserIdDep,
    SessionDep,
)
from narrare.kb.bulk_extraction import registry, runner
from narrare.kb.bulk_extraction.contracts import (
    BulkExtractionDispatcher,
    BulkExtractionJobStore,
)
from narrare.kb.bulk_extraction.service import BulkExtractionService

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare.kb.bulk_extraction.contracts import BulkChapterRef
    from narrare.kb.bulk_extraction.schemas import (
        BulkExtractionJobView,
        BulkExtractionResultsView,
        BulkExtractionStatusView,
    )


class RegistryJobStore:
    """``BulkExtractionJobStore`` façade over the in-memory registry."""

    async def create_job(
        self, novel_id: UUID, owner_user_id: UUID, chapters: Sequence[BulkChapterRef]
    ) -> BulkExtractionJobView:
        return registry.create(novel_id, owner_user_id, chapters)

    async def get_status(self, job_id: str, user_id: UUID) -> BulkExtractionStatusView:
        return registry.status(job_id, user_id)

    async def get_results(self, job_id: str, user_id: UUID) -> BulkExtractionResultsView:
        return registry.results(job_id, user_id)

    async def cancel_job(self, job_id: str, user_id: UUID) -> BulkExtractionJobView:
        return registry.request_cancel(job_id, user_id)

    async def resume_job(self, job_id: str, user_id: UUID) -> BulkExtractionJobView:
        return registry.reset_for_resume(job_id, user_id)

    async def has_active_for(self, novel_id: UUID) -> bool:
        return registry.find_active_for_novel(novel_id) is not None


class RunnerDispatcher:
    """``BulkExtractionDispatcher`` façade over the in-process runner."""

    async def dispatch(self, job_id: str, novel_id: UUID, owner_id: UUID) -> None:
        await runner.dispatch(job_id, novel_id, owner_id)


def get_bulk_job_store() -> BulkExtractionJobStore:
    """The real registry-backed store (in-memory, owner-pinned, ADR-092 §6)."""
    return RegistryJobStore()


def get_bulk_dispatcher() -> BulkExtractionDispatcher:
    """The real runner dispatcher (integration tests override with a no-op)."""
    return RunnerDispatcher()


#: Annotated aliases (the ``entity_resolution/dependencies.py`` idiom) — the
#: overridable sub-dependencies stay visible to ``app.dependency_overrides``
#: without ``Depends(...)`` call defaults.
StoreDep = Annotated[BulkExtractionJobStore, Depends(get_bulk_job_store)]
DispatcherDep = Annotated[BulkExtractionDispatcher, Depends(get_bulk_dispatcher)]


async def get_bulk_extraction_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: CurrentUserIdDep,
    store: StoreDep,
    dispatcher: DispatcherDep,
) -> BulkExtractionService:
    """Wire the REAL store/reader/dispatcher/gate into the service.

    The novel gate and the chapter reader share the request session
    (``NovelRepository`` / ``ChapterRepository``); the job store and the
    dispatcher are session-free (in-memory registry + in-process runner).
    No AI limiter here: no LLM call happens in-request on this surface —
    the runner paces agent calls in the background against the shared
    budget (ADR-092 D7a).
    """
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.bulk_extraction.reader import ChapterReader
    from narrare.novels.repository import NovelRepository

    return BulkExtractionService(
        store=store,
        reader=ChapterReader(ChapterRepository(session)),
        dispatcher=dispatcher,
        novel_repo=NovelRepository(session),
    )
