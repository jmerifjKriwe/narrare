"""DI factories for the export domain (RULE-06: router → service → renderer).

Two factories:

- :func:`get_export_renderers` — instantiates the three renderer adapters
  (stateless; each caches a ``shutil.which`` availability probe).
- :func:`get_export_service` — wires those renderers + the production
  :func:`enqueue_export` into an :class:`ExportServiceImpl`.

No ``SessionDep`` here: the entire export **request** surface
(``list_formats`` / ``export`` / ``get_job`` / ``consume_artifact``) operates
on the in-memory registry + the stateless renderer probes. The read-only DB
work (loading chapters) happens in the background runner
(:func:`narrare.export.tasks.run_export_inprocess`), which builds its own
session via ``get_session_factory()`` — outside the request lifecycle. So
there is no session to inject on the request path; RULE-19 (use ``SessionDep``
rather than bare ``AsyncSession``) is vacuously satisfied because no session
is used at all.

Tests bypass these factories and construct ``ExportServiceImpl`` directly with
fake renderers + a recording enqueuer (RULE-07).
"""

from __future__ import annotations

from narrare.export.contracts import ExportFormat, ManuscriptRenderer
from narrare.export.renderers.pandoc_epub import PandocEpubRenderer
from narrare.export.renderers.pandoc_md import PandocMarkdownRenderer
from narrare.export.renderers.typst import TypstPdfRenderer
from narrare.export.service import ExportServiceImpl
from narrare.export.tasks import enqueue_export


def get_export_renderers() -> dict[ExportFormat, ManuscriptRenderer]:
    """Instantiate the three renderer adapters (PDF / EPUB / Markdown)."""
    return {
        ExportFormat.PDF: TypstPdfRenderer(),
        ExportFormat.MARKDOWN: PandocMarkdownRenderer(),
        ExportFormat.EPUB: PandocEpubRenderer(),
    }


def get_export_service() -> ExportServiceImpl:
    """Request-scoped ``ExportService`` (the RULE-12 public API)."""
    return ExportServiceImpl(
        renderers=get_export_renderers(),
        enqueue=enqueue_export,
    )
