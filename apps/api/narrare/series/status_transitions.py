"""Series status-transition rules + patch builder (RULE-04 split from service.py).

Extracted so ``service.py`` stays under the 300-line hard limit after the
Spec 2 Task 5 auto-trigger addition. Contains the adjacency matrix, the
patchable-fields whitelist, and ``InvalidStatusTransitionError`` — all pure
functions / constants with no DB access (RULE-06).

``InvalidStatusTransitionError`` is re-exported from ``service.py`` for
backward compatibility with existing imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import ConflictError

if TYPE_CHECKING:
    from narrare.series.schemas import SeriesUpdateRequest
    from narrare_core.series.schemas import SeriesStatus

# Only adjacent status moves are allowed. Same-status "transitions" are
# no-ops and handled before this lookup (never reach the matrix).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"active"}),
    "active": frozenset({"completed", "draft"}),
    "completed": frozenset({"draft"}),
}

# Columns the service may patch through the repository. ``status`` is added
# back separately in ``build_patch`` (after transition validation).
PATCHABLE_FIELDS = frozenset(
    {"title", "subtitle", "description", "genre", "writing_language", "planned_novel_count"}
)


class InvalidStatusTransitionError(ConflictError):
    """Raised when a requested Series status transition is not allowed.

    Subclasses :class:`ConflictError` so the app's global ``NarrareError``
    handler (``_app/main.py``) maps it to HTTP 409 (state conflict), mirroring
    :class:`~narrare.series.join_service.NovelAlreadyInSeriesError`.
    """

    def __init__(self, current: SeriesStatus, target: SeriesStatus) -> None:
        super().__init__(f"Cannot transition series status from '{current}' to '{target}'")
        # Preserve the specific code (ConflictError defaults to "CONFLICT").
        self.code = "INVALID_STATUS_TRANSITION"
        self.current_status = current
        self.target_status = target


def validate_transition(current: SeriesStatus, target: SeriesStatus) -> None:
    """Raise ``InvalidStatusTransitionError`` if ``current``→``target`` is not allowed."""
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidStatusTransitionError(current, target)


def build_patch(request: SeriesUpdateRequest) -> dict[str, object]:
    """Filter the request to known columns, excluding unset fields.

    ``exclude_unset`` implements PATCH semantics: only fields the caller
    explicitly provided appear. The whitelist (``PATCHABLE_FIELDS`` plus
    ``status``) keeps arbitrary keys out of the repository's ``setattr``
    loop (Task 3.3 note).
    """
    allowed = PATCHABLE_FIELDS | {"status"}
    provided = request.model_dump(exclude_unset=True)
    return {key: value for key, value in provided.items() if key in allowed}
