"""Bulk extraction job service — start/status/results/cancel/resume (ADR-092 §4).

Thin orchestration over the four T1 Protocol seams (store, reader,
dispatcher, novel gate — RULE-03): the start path enforces the normative
check order ownership-gate → reader validation → single-active-job →
create → dispatch (spec §4.6); the read/cancel/resume paths gate once and
delegate. The service holds no SQLAlchemy (repos live behind the gate and
reader seams) and never mutates job state directly — the store Protocol
is the only job-state writer, the runner owns per-chapter transitions.

Resume re-dispatches the runner on the same job id (spec §4.5): a reset
without a fresh runner would strand the job in PENDING forever — a hung
job is exactly what RULE-11 forbids.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.kb._novel_gate import verify_novel_owned
from narrare.kb.bulk_extraction.corpus import build_estimate, select_corpus_prefix
from narrare.kb.bulk_extraction.schemas_corpus import CorpusEstimateView
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.kb.bulk_extraction.contracts import (
        BulkChapterReader,
        BulkChapterRef,
        BulkExtractionDispatcher,
        BulkExtractionJobStore,
        CorpusChapterSource,
    )
    from narrare.kb.bulk_extraction.schemas import (
        BulkExtractionJobView,
        BulkExtractionResultsView,
        BulkExtractionStatusView,
    )
    from narrare.novels.contracts import NovelRepositoryProtocol


class BulkExtractionService:
    """User-facing bulk extraction operations for one novel per call."""

    def __init__(
        self,
        store: BulkExtractionJobStore,
        reader: BulkChapterReader,
        corpus_source: CorpusChapterSource,
        dispatcher: BulkExtractionDispatcher,
        novel_repo: NovelRepositoryProtocol,
    ) -> None:
        self._store = store
        self._reader = reader
        self._corpus_source = corpus_source
        self._dispatcher = dispatcher
        self._novel_repo = novel_repo

    async def start(
        self, novel_id: UUID, user_id: UUID, chapter_ids: Sequence[UUID]
    ) -> BulkExtractionJobView:
        """Validate + register a job, then dispatch its runner (201 path).

        Check order is normative (spec §4.6): the ownership gate runs
        BEFORE the reader load (IDOR ordering — a foreign novel is a 404
        that never touches chapter data); reader validation collects the
        422s (duplicates, unknown/foreign ids, empty content, cap); an
        active job for the same novel is a 409 before any record exists.
        Chapters are stored in position order regardless of request order.
        """
        await self._gate(novel_id, user_id)
        refs: list[BulkChapterRef] = await self._reader.load(novel_id, chapter_ids)
        refs = sorted(refs, key=lambda ref: ref.position)
        if await self._store.has_active_for(novel_id):
            raise ConflictError("A bulk extraction job is already active for this novel")
        view = await self._store.create_job(novel_id, user_id, refs)
        await self._dispatcher.dispatch(view.job_id, novel_id, user_id)
        return view

    async def corpus_estimate(self, novel_id: UUID, user_id: UUID) -> CorpusEstimateView:
        """Honest pre-run estimate over the novel's position-order prefix (F3 §4.3).

        Gate → enumerate ALL rows (``CorpusChapterSource``, position order)
        → pure prefix selection → wire view. A zero-chapter novel is an
        HONEST zero here (the FE hides the sidebar entry for empty novels);
        only :meth:`start_corpus` turns an empty selection into a 422
        (rider b — the estimate endpoint never lies, the start endpoint
        never runs nothing silently).
        """
        await self._gate(novel_id, user_id)
        rows = await self._corpus_source.load_all(novel_id)
        selection = select_corpus_prefix(rows)
        return CorpusEstimateView.model_validate(build_estimate(selection), from_attributes=True)

    async def start_corpus(self, novel_id: UUID, user_id: UUID) -> BulkExtractionJobView:
        """Start a corpus pass over the START-time prefix (F3 §4.4).

        Mirrors ``start``'s normative check order: ownership gate → scope
        selection → single-active-job 409 → create → dispatch. The scope is
        RE-selected at start time — the estimate may be stale (chapters
        added/removed since the confirm dialog) and the job runs over what
        exists NOW, never a silent superset of what was shown (spec R3/R4,
        rider d). An empty selection (a novel without chapters —
        ``select_corpus_prefix`` itself already 422s a first-chapter-over-cap
        novel) is rejected with honest counts (rider b).
        """
        await self._gate(novel_id, user_id)
        rows = await self._corpus_source.load_all(novel_id)
        selection = select_corpus_prefix(rows)
        if not selection.selected:
            raise ValidationError(
                f"Corpus pass cannot start: the novel has {selection.total_chapters} "
                f"chapters — import or write chapters first."
            )
        if await self._store.has_active_for(novel_id):
            raise ConflictError("A bulk extraction job is already active for this novel")
        view = await self._store.create_job(novel_id, user_id, selection.selected, kind="corpus")
        await self._dispatcher.dispatch(view.job_id, novel_id, user_id)
        return view

    async def status(self, novel_id: UUID, job_id: str, user_id: UUID) -> BulkExtractionStatusView:
        """Poll one job (owner-only, enforced again by the store)."""
        await self._gate(novel_id, user_id)
        view = await self._store.get_status(job_id, user_id)
        self._ensure_novel_binding(novel_id, job_id, view.novel_id)
        return view

    async def results(
        self, novel_id: UUID, job_id: str, user_id: UUID
    ) -> BulkExtractionResultsView:
        """Full outputs for the review panel (owner-only)."""
        await self._gate(novel_id, user_id)
        view = await self._store.get_results(job_id, user_id)
        self._ensure_novel_binding(novel_id, job_id, view.novel_id)
        return view

    async def cancel(self, novel_id: UUID, job_id: str, user_id: UUID) -> BulkExtractionJobView:
        """Cooperative cancel; terminal jobs conflict (409 from the store)."""
        await self._gate(novel_id, user_id)
        # Pre-read binding guard: ``cancel_job`` MUTATES, so a job bound to a
        # different novel must be rejected BEFORE the flip — the check after
        # the write alone would leave a self-inflicted "cancelling" flag on
        # the caller's own job under its correct URL.
        bound = await self._store.get_status(job_id, user_id)
        self._ensure_novel_binding(novel_id, job_id, bound.novel_id)
        view = await self._store.cancel_job(job_id, user_id)
        self._ensure_novel_binding(novel_id, job_id, view.novel_id)  # belt-and-braces
        return view

    async def resume(self, novel_id: UUID, job_id: str, user_id: UUID) -> BulkExtractionJobView:
        """Reset a cancelled/failed job and dispatch a fresh runner (spec §4.5)."""
        await self._gate(novel_id, user_id)
        # Pre-read binding guard (fix round 1): ``resume_job`` MUTATES. With
        # only the check after the write, a misrouted resume reset the job to
        # PENDING and the check-before-dispatch then blocked the runner — a
        # stranded PENDING job that ``find_active_for_novel`` counts active:
        # the novel locked until restart.
        bound = await self._store.get_status(job_id, user_id)
        self._ensure_novel_binding(novel_id, job_id, bound.novel_id)
        view = await self._store.resume_job(job_id, user_id)
        self._ensure_novel_binding(novel_id, job_id, view.novel_id)  # belt-and-braces
        await self._dispatcher.dispatch(view.job_id, view.novel_id, user_id)
        return view

    @staticmethod
    def _ensure_novel_binding(path_novel_id: UUID, job_id: str, view_novel_id: UUID) -> None:
        """Reject a store hit bound to a DIFFERENT novel than the path (rider).

        Owner pinning alone does not bind a job to the novel in the URL:
        a user owning novels A and B could otherwise operate B's job under
        A's URL (the gate passes — A is theirs; the store lookup passes —
        the job is theirs). The mismatch is answered with the registry's
        foreign ≡ unknown ``NotFoundError`` (anti-enumeration, same
        message). The MUTATING paths (cancel/resume) run this guard on a
        pre-read BEFORE the store write, so a mis-bound job is never
        mutated; the pure reads check after their read; the post-write
        re-check is belt-and-braces.
        """
        if view_novel_id != path_novel_id:
            raise NotFoundError(f"Bulk extraction job '{job_id}'")

    async def _gate(self, novel_id: UUID, user_id: UUID) -> None:
        """Novel ownership gate — foreign ≡ unknown (404), always first."""
        await verify_novel_owned(self._novel_repo, novel_id, user_id)
