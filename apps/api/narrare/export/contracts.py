"""Backend contracts for the manuscript export pipeline (IO-001 / ADR-081).

Home of the RULE-12 public API (``ExportService``), the RULE-08 renderer
Protocol (``ManuscriptRenderer``), the job/artifact models, and the
Typst-package config contract. Written before any implementation (RULE-03).

The option models (``ExportFormat`` … ``ExportOptions``) live in
:mod:`narrare.export.options` and the typed error hierarchy in
:mod:`narrare.export.errors` — both extracted to keep this file under the
RULE-04 200-line contracts limit (mirrors the ``analysis/`` split pattern).
The names imported below stay available from this module's namespace because
they are used by the Protocols and models defined here.

Non-LLM call-out (applies to this entire package)
-------------------------------------------------
Export defines *no* ``LLMIntent``, *no* ``PromptContext``, *no* agent, *no*
``ModelRegistry``/``PromptComposer`` injection. If an implementer finds
themselves importing ``narrare_core.agents`` or ``narrare_core.prompts`` here,
**stop** — that is a layering violation of the IO-001 plan. The normalizer is a
pure transformation; the renderers are subprocess adapters; the service is job
orchestration. None of these is an LLM operation.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — needed at runtime for Pydantic
from enum import StrEnum
from pathlib import Path  # noqa: TC003 — needed at runtime for Pydantic
from typing import Protocol
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic

from pydantic import BaseModel

from narrare.export.options import (
    ExportFormat,
    ExportOptions,
    MirroredMargins,
    PaperSize,
)
from narrare_core.export.contracts import (  # noqa: TC001 — runtime dep: Language (Pydantic field)
    Language,
    NormalizedManuscript,  # the renderer consumes the Core output
)

# ── Job lifecycle (in-memory; D1) ───────────────────────────────────────────


class ExportJobStatus(StrEnum):
    """Export job lifecycle states (no ``unavailable`` — see ExportFormatUnavailableError)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportJob(BaseModel):
    """Public job view returned by ExportService.

    The ``artifact_url`` is set only on COMPLETED and carries the signed token
    (D1).
    """

    job_id: str
    novel_id: UUID
    format: ExportFormat
    status: ExportJobStatus
    created_at: datetime
    updated_at: datetime
    artifact_url: str | None = None  # signed token URL when COMPLETED
    error: str | None = None  # typed failure reason when FAILED


# ── Renderer adapter contract (RULE-08) ─────────────────────────────────────


class Artifact(BaseModel):
    """Renderer output. ``path`` is a temp file the service registers for cleanup."""

    format: ExportFormat
    path: Path  # temp file written by the renderer
    media_type: str  # e.g. "application/pdf"
    suggested_filename: str  # e.g. "my-novel.pdf"


class ManuscriptRenderer(Protocol):
    """RULE-08: the external binary (Typst / pandoc) is invoked ONLY inside the
    renderer module that implements this Protocol.

    ``is_available()`` is the RULE-11 graceful-degradation contract: a renderer
    whose binary is missing returns False; the service reports the format
    unavailable (never silently produces a wrong-font / missing-font fallback —
    the bake-off's headline fire&forget failure).
    """

    @property
    def format(self) -> ExportFormat: ...

    def is_available(self) -> bool: ...

    async def render(
        self,
        manuscript: NormalizedManuscript,
        options: ExportOptions,
    ) -> Artifact: ...


# ── Typst-package config contract (stable Python↔Typst coupling) ────────────


class NarrareRomanConfig(BaseModel):
    """Config keys the TypstPdfRenderer builds and feeds to the narrare-roman
    wrapper. NOT a Python Protocol (narrare-roman is a Typst artifact) — but its
    keys are a stable contract: changing a key is a coordinated Python+Typst
    change. Mirrors PdfOptions + manuscript metadata (scalar strings — F-7).
    """

    paper_size: PaperSize = PaperSize.B_FORMAT_129_198
    margins: MirroredMargins | None = None
    body_font: str = "Libertinus Serif"  # bundled, OFL (D3)
    body_size_pt: float = 11.0
    leading_ratio: float = 1.2
    language: Language
    title: str  # scalar string (F-7)
    author: str  # scalar string (F-7)
    drop_caps: bool = False  # OPTIONAL, default OFF (D5)
    include_toc: bool = True
    running_head_preset: str = "default"  # recto≠verso, suppressed on openers/blanks
    scene_break_style: str = "asterism"  # "* * *" ornament (folklore pattern)
    widow_orphan_protection: bool = True


# ── The RULE-12 public API ──────────────────────────────────────────────────


class ExportService(Protocol):
    """The ONLY public API for manuscript export (RULE-12).

    Consumable by all four clients (WebUI download, MCP, A2A, CLI) — a new
    client is a new adapter, never a service change. NOT an LLM operation (see
    the non-LLM call-out): no ModelRegistry, no PromptComposer, no agent.
    """

    async def list_formats(self) -> list[tuple[ExportFormat, bool]]:
        """Formats + their availability (``is_available()``).

        Lets the UI disable unavailable formats before the user clicks Export.
        """
        ...

    async def export(
        self,
        novel_id: UUID,
        options: ExportOptions,
    ) -> ExportJob:
        """Create + dispatch an export job.

        Raises :class:`ExportFormatUnavailableError` synchronously if the
        format's binary is missing (RULE-11 fast-fail).
        """
        ...

    async def get_job(self, job_id: str) -> ExportJob:
        """Poll job status. Raises :class:`ExportJobNotFoundError` for unknown ids."""
        ...

    async def consume_artifact(self, job_id: str, token: str) -> Artifact:
        """Validate the signed token, return the ``Artifact`` (single-use), and
        schedule temp-file cleanup. Raises :class:`ExportArtifactExpiredError`.
        """
        ...
