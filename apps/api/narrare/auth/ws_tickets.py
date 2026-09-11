"""In-memory WebSocket ticket registry (ADR-084 — no migration, RULE-14).

Owns the ``_TICKETS`` dict (SHA-256 hex → :class:`_TicketRecord`) and the
mint/consume machinery behind the writing-session WebSocket handshake.
**Process-local by design**: tickets live in memory for the API process's
lifetime and are lost on restart — valid because the deployment is
single-process post-ADR-080, and meaningless to persist anyway (60 s TTL,
single-use: a restart-invalidated client simply fetches a new ticket on its
next ``connect()``).

This module mirrors the security model of the export artifact token
(``narrare.export.registry``, ADR-081) exactly.

Token security model
--------------------
The ticket is generated with :func:`secrets.token_urlsafe(32)` and the
registry is keyed by the **SHA-256 hash** of the token — the raw token is
never stored and is handed to the client exactly once, inside the
``WsTicketResponse`` from ``POST /api/v1/auth/ws-ticket`` (which is
JWT-authenticated via ``CurrentUserIdDep``, so the ticket is bound to a
verified identity by construction). A consumer who only reads the registry
cannot forge a consume (they would need the preimage).

Single-use: the first successful :func:`consume` **deletes** the record;
every later presentment (expired, unknown, replayed) raises the same typed
:class:`WsTicketError` (RULE-11).

Anti-enumeration
----------------
Unknown ≡ expired ≡ consumed ≡ foreign: :func:`consume` raises one typed
error carrying a single uniform message — the client never receives a
distinguishing reason. The precise reason is logged server-side (structlog)
only, mirroring the ``foreign ≡ unknown`` stance of the export registry.

Sweep
-----
Expired-but-unused records are dropped lazily on lookup and by
:func:`sweep_expired`, hooked into the lifespan periodic cleanup loop
beside the export sweep (``_app/lifespan.py``).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

logger = structlog.get_logger(__name__)

#: Ticket lifetime from mint to handshake (PO decision D1:a). Single-use;
#: after it elapses the record is dropped lazily and by ``sweep_expired``.
WS_TICKET_TTL: timedelta = timedelta(seconds=60)

#: The one client-facing rejection message — shared by every failure mode
#: (anti-enumeration: no oracle on why a ticket was refused).
_TICKET_REJECTED_MESSAGE = "Invalid or expired session ticket"


class WsTicketError(Exception):
    """Ticket missing, unknown, expired, or already consumed (RULE-11).

    Carries a single uniform message for all failure modes; the precise
    reason is logged server-side only.
    """


def _now() -> datetime:
    """Timezone-aware "now" (mirrors the tz-aware DB columns)."""
    return datetime.now(UTC)


def _hash_token(token: str) -> str:
    """SHA-256 hex digest of the ticket (the validation credential)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _TicketRecord:
    """Immutable in-memory state for one outstanding ticket.

    ``user_id`` is the identity bound at :func:`issue` (the
    JWT-authenticated caller of the mint route) — :func:`consume` derives
    the session identity from it, never from client input.
    """

    user_id: UUID
    expires_at: datetime


#: SHA-256 hex → record. Process-local (post-ADR-080). Safe under the
#: single-threaded asyncio loop: every mutation is synchronous (no await
#: between read and write).
_TICKETS: dict[str, _TicketRecord] = {}


def issue(user_id: UUID, now: Callable[[], datetime] = _now) -> str:
    """Mint a single-use ticket bound to ``user_id``; return the raw token once.

    The mint route calls this only AFTER ``CurrentUserIdDep`` authenticated
    the caller, so the owner binding is trustworthy by construction.
    """
    token = secrets.token_urlsafe(32)
    _TICKETS[_hash_token(token)] = _TicketRecord(
        user_id=user_id,
        expires_at=now() + WS_TICKET_TTL,
    )
    logger.info("ws_ticket_issued", user_id=str(user_id))
    return token


def consume(token: str, now: Callable[[], datetime] = _now) -> UUID:
    """Validate + burn the ticket; return the bound ``user_id``.

    Raises :class:`WsTicketError` for unknown, expired, or
    already-consumed tickets — identical typed error and identical message
    for all three (anti-enumeration); the specific reason is logged
    server-side. Never logs the raw token or its hash.
    """
    token_hash = _hash_token(token)
    record = _TICKETS.get(token_hash)
    if record is None:
        # Unknown — also the post-consume (replay) and foreign cases.
        logger.info("ws_ticket_rejected", reason="unknown_or_consumed")
        raise WsTicketError(_TICKET_REJECTED_MESSAGE)
    if now() > record.expires_at:
        # Lazy drop of an expired-unused record.
        del _TICKETS[token_hash]
        logger.info("ws_ticket_rejected", reason="expired")
        raise WsTicketError(_TICKET_REJECTED_MESSAGE)
    del _TICKETS[token_hash]
    logger.info("ws_ticket_consumed", user_id=str(record.user_id))
    return record.user_id


def sweep_expired(now: Callable[[], datetime] = _now) -> int:
    """Drop expired-unused records (lifespan periodic cleanup).

    Idempotent. Returns the number of records dropped. Tickets are
    deleted on consume, so every remaining record is unused by
    definition — only the TTL can retire it.
    """
    dropped = 0
    for token_hash in list(_TICKETS):
        if now() > _TICKETS[token_hash].expires_at:
            del _TICKETS[token_hash]
            dropped += 1
    if dropped > 0:
        logger.info("ws_ticket_sweep", tickets_dropped=dropped)
    return dropped
