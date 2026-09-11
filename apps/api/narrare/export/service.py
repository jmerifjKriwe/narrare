"""``ExportServiceImpl`` — the concrete RULE-12 public API.

Implements :class:`narrare.export.contracts.ExportService`. The service is job
orchestration only: it gates novel ownership (Pattern B — P-SEC S1), queries
renderer availability (RULE-11 fast-fail), creates a registry job, and hands
dispatch to the injected enqueuer. It does NOT spawn any binary (RULE-08 —
that is confined to the renderer adapters).

The only database touch on the request path is the ownership gate: an injected
``OwnedLinkLookupProtocol`` adapter (user-scoped ``NovelRepository.get_by_id``,
mirroring the notes/chat pattern) resolves the novel BEFORE any job creation —
a foreign or unknown novel raises core ``NotFoundError`` (→ HTTP 404 via the
global handler; the two are indistinguishable by design). Manuscript loading
stays in the background runner (:mod:`narrare.export.tasks`, own session)
outside the request lifecycle.

Non-LLM (no ``narrare_core.agents`` / ``narrare_core.prompts`` imports).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.export import registry
from narrare.export.errors import ExportFormatUnavailableError
from narrare.export.tasks import ExportEnqueuer, enqueue_export
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.export.contracts import (
        Artifact,
        ExportFormat,
        ExportJob,
        ExportOptions,
        ManuscriptRenderer,
    )
    from narrare.notes.contracts import OwnedLinkLookupProtocol


class ExportServiceImpl:
    """Concrete :class:`ExportService` (the RULE-12 public API)."""

    def __init__(
        self,
        renderers: dict[ExportFormat, ManuscriptRenderer],
        novel_lookup: OwnedLinkLookupProtocol,
        enqueue: ExportEnqueuer = enqueue_export,
    ) -> None:
        self._renderers = renderers
        self._novel_lookup = novel_lookup
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
        user_id: UUID,
    ) -> ExportJob:
        """Create + dispatch an export job (RULE-11 fast-fail).

        FIRST statement — the Pattern B ownership gate: the novel must exist
        AND belong to ``user_id``, else core ``NotFoundError`` (→ 404,
        foreign ≡ unknown) BEFORE any job creation or dispatch. The runner's
        own novel load is NOT the gate — gating there would leave a created
        job pollable (enumeration + stolen-token vectors).

        Then raises :class:`ExportFormatUnavailableError` synchronously —
        BEFORE creating a job — when the requested format's binary is missing,
        so the client gets an immediate structured error instead of polling a
        doomed job.
        """
        if await self._novel_lookup.get_owned(novel_id, user_id) is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        renderer = self._renderer_for(options.format)
        if not renderer.is_available():
            raise ExportFormatUnavailableError(
                f"Format '{options.format.value}' is unavailable: its render binary "
                f"is not installed on this server.",
            )

        job = registry.create(novel_id, user_id, options.format)
        await self._enqueue(job.job_id, novel_id, options)
        return job

    async def get_job(self, job_id: str, user_id: UUID) -> ExportJob:
        """Poll job status (owner-only). Raises :class:`ExportJobNotFoundError`."""
        return registry.get(job_id, user_id)

    async def consume_artifact(self, job_id: str, token: str, user_id: UUID) -> Artifact:
        """Validate the token + return the single-use :class:`Artifact`.

        Raises :class:`ExportArtifactExpiredError` (consumed / expired / wrong
        token) or :class:`ExportJobNotFoundError` (unknown or foreign-owned
        job). The router streams the file and unlinks it after the response
        completes.
        """
        return registry.consume_artifact(job_id, token, user_id)

    def _renderer_for(self, fmt: ExportFormat) -> ManuscriptRenderer:
        """Resolve a renderer, raising if the format is not registered at all."""
        renderer = self._renderers.get(fmt)
        if renderer is None:
            raise ExportFormatUnavailableError(
                f"No renderer registered for format '{fmt.value}'.",
            )
        return renderer
