"""DI factories for the export domain (RULE-06: router → service → renderer).

Two factories:

- :func:`get_export_renderers` — instantiates the four renderer adapters
  (stateless; each caches a ``shutil.which`` availability probe).
- :func:`get_export_service` — wires those renderers + the production
  :func:`enqueue_export` + the novel-ownership lookup adapter into an
  :class:`ExportServiceImpl`.

``SessionDep`` is used for exactly one request-path read: the Pattern B
ownership gate (P-SEC S1) — ``_NovelOwnedLookup`` resolves the novel through
the user-scoped ``NovelRepository.get_by_id`` BEFORE any job creation
(fail-closed: the lookup is a required service dependency, never optional).
Everything else on the request surface stays on the in-memory registry + the
stateless renderer probes; the manuscript-loading DB work happens in the
background runner (:func:`narrare.export.tasks.run_export_inprocess`), which
builds its own session via ``get_session_factory()`` — outside the request
lifecycle.

Tests bypass these factories and construct ``ExportServiceImpl`` directly with
fake renderers + a recording enqueuer + a fake lookup (RULE-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI
from narrare.export.contracts import ExportFormat, ManuscriptRenderer
from narrare.export.renderers.pandoc_docx import PandocDocxRenderer
from narrare.export.renderers.pandoc_epub import PandocEpubRenderer
from narrare.export.renderers.pandoc_md import PandocMarkdownRenderer
from narrare.export.renderers.typst import TypstPdfRenderer
from narrare.export.service import ExportServiceImpl
from narrare.export.tasks import enqueue_export

if TYPE_CHECKING:
    import uuid

    from narrare.novels.repository import NovelRepository


class _NovelOwnedLookup:
    """OwnedLinkLookupProtocol adapter over NovelRepository.get_by_id.

    Same pattern as ``narrare.notes.dependencies._NovelOwnedLookup``
    (module-local: notes' adapter is private to its module). get_by_id is
    already ownership-filtered, so this is pure delegation.
    """

    def __init__(self, repo: NovelRepository) -> None:
        self._repo = repo

    async def get_owned(self, entity_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        return await self._repo.get_by_id(entity_id, user_id)


def get_export_renderers() -> dict[ExportFormat, ManuscriptRenderer]:
    """Instantiate the four renderer adapters (PDF / EPUB / Markdown / DOCX)."""
    return {
        ExportFormat.PDF: TypstPdfRenderer(),
        ExportFormat.MARKDOWN: PandocMarkdownRenderer(),
        ExportFormat.EPUB: PandocEpubRenderer(),
        ExportFormat.DOCX: PandocDocxRenderer(),
    }


def get_export_service(session: SessionDep) -> ExportServiceImpl:
    """Request-scoped ``ExportService`` (the RULE-12 public API)."""
    from narrare.novels.repository import NovelRepository

    return ExportServiceImpl(
        renderers=get_export_renderers(),
        novel_lookup=_NovelOwnedLookup(NovelRepository(session)),
        enqueue=enqueue_export,
    )
