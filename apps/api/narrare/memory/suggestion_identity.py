"""Canonical suggestion identity resolution (CR-AUFG-07-24).

Derives a deterministic UUID from canonical frontend suggestion identifiers so
the API boundary can accept non-UUID ``source_id`` values while the core layer
and the database remain UUID-only — no migration, no raw ``source_id`` leak
(RULE-17 cross-layer contract, RULE-22 privacy).

Inputs to the derivation (canonical tuple):
    ``(user_id, project_id, source_type, normalized source_id)``

Privacy:
    Raw ``source_id`` values never leave this module unhashed. A one-way,
    namespace-salted SHA-256 prefix (``source_id_hash``) may be attached to
    the feedback event context for mem0 traceability without revealing the
    original identifier.
"""

from __future__ import annotations

import hashlib
import uuid

# Backend-owned, stable namespace for ``uuid5`` derivation.
#
# This is an opaque, pinned constant — NOT derived from a DNS name. Changing
# it shifts every derived ``suggestion_id`` and silently breaks historical
# feedback joins. Treat as write-once.
_SUGGESTION_IDENTITY_NAMESPACE = uuid.UUID("56399992-b641-4795-8444-0fe3941ade29")

# Length of the ``source_id_hash`` prefix exposed in context metadata.
# 16 hex chars = 64 bits of entropy — enough for traceability without
# leaking the full digest; raw ``source_id`` stays unrecoverable.
# This is a pinned stability constant, NOT runtime configuration: changing
# it shifts every derived hash and breaks mem0 traceability correlation.
# narrare: allow reason="pinned hash-length constant; configurability breaks determinism"
_SOURCE_ID_HASH_PREFIX_LEN = 16

# Bumped when the derivation inputs or algorithm change. Recorded in
# ``event.context["feedback_source_version"]`` so future migrations can
# detect and re-derive legacy UUIDs if ever needed.
FEEDBACK_SOURCE_VERSION = "1"


def resolve_suggestion_id(
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    source_type: str,
    source_id: str,
) -> uuid.UUID:
    """Derive a deterministic UUIDv5 from canonical suggestion identity.

    Same ``(user_id, project_id, source_type, source_id)`` tuple always
    yields the same UUID; changing any component yields a different UUID.
    The raw ``source_id`` never reaches core or DB through this path.

    Args:
        user_id: Authenticated user ID (scopes the derivation per user).
        project_id: Project the feedback belongs to.
        source_type: Canonical source taxonomy value (see FeedbackSourceType).
        source_id: Normalized (trimmed, non-empty) frontend canonical ID.

    Returns:
        A deterministic UUIDv5 suitable for ``FeedbackEvent.suggestion_id``.
    """
    canonical = "|".join((str(user_id), str(project_id), source_type, source_id))
    return uuid.uuid5(_SUGGESTION_IDENTITY_NAMESPACE, canonical)


def hash_source_id(source_id: str) -> str:
    """Return a one-way, namespace-salted SHA-256 prefix of ``source_id``.

    Suitable for mem0 context metadata (``source_id_hash``) — provides
    traceability without revealing the raw identifier (RULE-22).

    Args:
        source_id: Normalized frontend canonical ID.

    Returns:
        A 16-character hex string (64-bit prefix of SHA-256).
    """
    salted = f"{_SUGGESTION_IDENTITY_NAMESPACE}{source_id}".encode()
    return hashlib.sha256(salted).hexdigest()[:_SOURCE_ID_HASH_PREFIX_LEN]
