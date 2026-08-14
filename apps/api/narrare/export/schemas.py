"""FastAPI request/response schemas for the export router (RULE-06 thin router).

These are thin API-layer shapes only. The domain option types
(:class:`ExportOptions`, :class:`ExportFormat`) and the job model
(:class:`ExportJob`) live in :mod:`narrare.export.options` /
:mod:`narrare.export.contracts` and are **referenced**, not duplicated — the
POST body embeds :class:`ExportOptions` directly, and the job endpoints return
the public :class:`ExportJob` model verbatim. Only the two API-specific shapes
with no domain analogue (the formats-availability list item, the create
request envelope carrying ``novel_id``) are defined here.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003 — runtime Pydantic field

from pydantic import BaseModel

from narrare.export.options import (  # noqa: TC001 — Pydantic resolves fields at runtime
    ExportFormat,
    ExportOptions,
)


class FormatAvailability(BaseModel):
    """One row of ``GET /export/formats``: a format + its availability flag.

    Carried as an object (not a bare ``[format, bool]`` tuple) so the JSON is
    self-describing for API consumers.
    """

    format: ExportFormat
    available: bool


class ExportRequest(BaseModel):
    """Body of ``POST /api/v1/export``: which novel + which options.

    ``options.format`` selects the renderer; the renderer-specific options block
    (``pdf_options`` / ``epub_options`` / ``markdown_options``) is the only one
    consumed. The domain :class:`ExportOptions` is embedded directly — no field
    duplication.
    """

    novel_id: UUID
    options: ExportOptions
