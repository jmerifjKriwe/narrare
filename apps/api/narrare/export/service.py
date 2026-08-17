"""``ExportServiceImpl`` — the concrete RULE-12 public API.

Implements :class:`narrare.export.contracts.ExportService`. The service is job
orchestration only: it queries renderer availability (RULE-11 fast-fail),
creates a registry job, and hands dispatch to the injected enqueuer. It does
NOT touch the database (the runner in :mod:`narrare.export.tasks` does, with
its own session) and does NOT spawn any binary (RULE-08 — that is confined to
the renderer adapters).

No ``AsyncSession`` dependency: the entire request path (list/export/get/
consume) operates on the in-memory registry + the stateless renderer
availability probes. The read-only DB work (loading chapters) happens in the
background runner, outside the request lifecycle. This is deliberate — export
is the one domain whose request surface is purely in-memory (D1).

Non-LLM (no ``narrare_core.agents`` / ``narrare_core.prompts`` imports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.export import registry
from narrare.export.errors import ExportFormatUnavailableError
from narrare.export.tasks import ExportEnqueuer, enqueue_export

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.export.contracts import (
        Artifact,
        ExportFormat,
        ExportJob,
        ExportOptions,
        ManuscriptRenderer,
    )


class ExportServiceImpl:
    """Concrete :class:`ExportService` (the RULE-12 public API)."""

    def __init__(
        self,
        renderers: dict[ExportFormat, ManuscriptRenderer],
        enqueue: ExportEnqueuer = enqueue_export,
    ) -> None:
        self._renderers = renderers
        self._enqueue = enqueue

    async def list_formats(self) -> list[tuple[ExportFormat, bool]]:
        """Each format + its renderer's ``is_available()`` (RULE-11).

        Iterates the injected renderer map in insertion order — a single
        registration surface: whatever the DI factory registers is exactly
        what the UI sees (deterministic in production because the factory
        builds the dict from a fixed literal). Lets the UI disable
        unavailable formats before the user clicks Export.
        """
        return [(fmt, renderer.is_available()) for fmt, renderer in self._renderers.items()]

    async def export(
        self,
        novel_id: UUID,
        options: ExportOptions,
    ) -> ExportJob:
        """Create + dispatch an export job (RULE-11 fast-fail).

        Raises :class:`ExportFormatUnavailableError` synchronously — BEFORE
        creating a job — when the requested format's binary is missing, so the
        client gets an immediate structured error instead of polling a doomed
        job.
        """
        renderer = self._renderer_for(options.format)
        if not renderer.is_available():
            raise ExportFormatUnavailableError(
                f"Format '{options.format.value}' is unavailable: its render binary "
                f"is not installed on this server.",
            )

        job = registry.create(novel_id, options.format)
        await self._enqueue(job.job_id, novel_id, options)
        return job

    async def get_job(self, job_id: str) -> ExportJob:
        """Poll job status. Raises :class:`ExportJobNotFoundError`."""
        return registry.get(job_id)

    async def consume_artifact(self, job_id: str, token: str) -> Artifact:
        """Validate the token + return the single-use :class:`Artifact`.

        Raises :class:`ExportArtifactExpiredError` (consumed / expired / wrong
        token) or :class:`ExportJobNotFoundError`. The router streams the file
        and unlinks it after the response completes.
        """
        return registry.consume_artifact(job_id, token)

    def _renderer_for(self, fmt: ExportFormat) -> ManuscriptRenderer:
        """Resolve a renderer, raising if the format is not registered at all."""
        renderer = self._renderers.get(fmt)
        if renderer is None:
            raise ExportFormatUnavailableError(
                f"No renderer registered for format '{fmt.value}'.",
            )
        return renderer
