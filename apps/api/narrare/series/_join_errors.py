"""IntegrityError → domain-error translation for the Series join flow (T10).

Extracted from ``join_service.py`` to respect the RULE-04 300-line service
file-size limit. This is the cohesive "translate a commit-time
``sqlalchemy.exc.IntegrityError`` into a typed Narrare domain error" concern —
kept separate so the join service stays focused on Policy alpha.

Mapping (per ADR-075 / Series Foundation):
* ``uq_novels_series_position`` → :class:`ConflictError` ("Position occupied").
* ``uq_kb_canon_per_series``    → :class:`ConflictError` ("Slug conflict …").
* anything else (a membership FK firing because the series vanished in a
  commit race) → :class:`NotFoundError` ("Series").
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.shared.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.exc import IntegrityError


def constraint_name(orig: object | None) -> str | None:
    """Best-effort extraction of the Postgres constraint name from a DBAPI error.

    ``asyncpg`` exposes ``constraint_name`` directly on the exception;
    ``psycopg2`` nests it under ``orig.diag.constraint_name``. Returns ``None``
    when no constraint is identifiable.
    """
    diag = getattr(orig, "diag", None)
    if diag is not None:
        name = getattr(diag, "constraint_name", None)
        if name:
            return str(name)
    name = getattr(orig, "constraint_name", None)
    return str(name) if name else None


def map_join_integrity_error(exc: IntegrityError, series_id: uuid.UUID) -> Exception:
    """Translate a join-flow commit ``IntegrityError`` into a domain error.

    The returned error is intended to be ``raise``d (``from exc``) by the caller
    so the original is chained for diagnostics (RULE-11).
    """
    match constraint_name(getattr(exc, "orig", None)):
        case "uq_novels_series_position":
            return ConflictError("Position occupied")
        case "uq_kb_canon_per_series":
            return ConflictError("Slug conflict: a Canon entry with this slug exists")
        case _:
            # An unrecognised violation is treated as a membership FK firing
            # because the series vanished in a commit race (anti-enumeration
            # makes a vanished series indistinguishable here → 404).
            return NotFoundError("Series", identifier=str(series_id))
