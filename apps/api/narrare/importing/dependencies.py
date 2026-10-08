"""Import service FastAPI factories (RULE-19: SessionDep, never bare AsyncSession)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Form
from pydantic import ValidationError as PydanticValidationError

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI
from narrare.analytics.dependencies import (  # noqa: TC001 - needed at runtime for FastAPI DI
    WritingStatsRecorderDep,
)
from narrare.importing.contracts import build_import_service
from narrare.importing.schemas import ImportCommitAdjustments
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from narrare.importing.contracts import ImportServiceProtocol


def get_import_service(
    session: SessionDep,
    writing_stats_recorder: WritingStatsRecorderDep,
) -> ImportServiceProtocol:
    """Production wiring incl. the STATS-001 content-write capture seam.

    The recorder is inert for preview (no call sites) and records one
    delta per imported chapter on commit. Like E3a's chapters routers,
    FastAPI resolves it via ``WritingStatsRecorderDep``; it opens its own
    short-lived session per event (RULE-08), never joining the request
    transaction (ADR-091 append stays atomic).
    """
    return build_import_service(session, writing_stats_recorder=writing_stats_recorder)


def get_commit_adjustments(
    adjustments: Annotated[str, Form()],
) -> ImportCommitAdjustments:
    """Parse the ``adjustments`` JSON form field into the commit schema.

    Scoped request dependency (coordinator ruling): malformed or wrongly
    shaped JSON becomes the domain :class:`ValidationError` here, so the
    global NarrareError handler answers 422 (spec error contract) instead
    of an unhandled 500 — keeping the router itself free of try/except
    (RULE-06). Field name ``adjustments`` is the wire contract the frontend
    client sends (``body.append("adjustments", JSON.stringify(...))``).
    """
    try:
        return ImportCommitAdjustments.model_validate_json(adjustments)
    except PydanticValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "adjustments"
        reason = str(first["msg"])[:200]
        raise ValidationError(f"Invalid adjustments JSON ({location}: {reason}).") from exc
