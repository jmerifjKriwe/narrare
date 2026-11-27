"""Shared refusal shapes: the machine-readable detail the surfaces localize.

The wire's failures carry ``{"detail": {"code": …, "detail": …}}`` — a code
the UI names in its own words and a sentence for the log and the curious.
The kernel owns the shape and the one closed list of codes; every router
raises its own ``HTTPException`` with it, so the kernel imports no web
framework.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Every code a failure can carry, in one list both trees read.

    The generator writes these members to ``web/lib/generated/errorCodes.ts``,
    so the backend's refusals and the web's exhaustive mapping cannot name
    different vocabularies. A member's value is the wire's own string and
    serializes as itself.
    """

    ARCHIVE_INVALID = "archive_invalid"
    DEFAULT_PROFILE = "default-profile"
    DOCUMENT_EMPTY = "document-empty"
    EMBEDDING_MISMATCH = "embedding-mismatch"
    ENTITY_INVALID = "entity-invalid"
    ENTITY_TYPE_REQUIRED = "entity-type-required"
    ENTITY_TYPE_UNKNOWN = "entity-type-unknown"
    EXTRACTION_FAILED = "extraction-failed"
    KEY_UNAVAILABLE = "key-unavailable"
    MODE_UNKNOWN = "mode-unknown"
    MODEL_NOT_FOUND = "model-not-found"
    NO_CONTEXT = "no-context"
    NOT_FOUND = "not-found"
    ORDER_MISMATCH = "order_mismatch"
    PROMPT_REFUSED = "prompt-refused"
    PROVIDER_AUTH = "provider-auth"
    PROVIDER_ERROR = "provider-error"
    PROVIDER_HAS_MODELS = "provider-has-models"
    PROVIDER_UNAVAILABLE = "provider-unavailable"
    RATE_LIMITED = "rate-limited"
    RELATION_DUPLICATE = "relation-duplicate"
    RELATION_LIMIT = "relation-limit"
    RELATION_TARGET_INVALID = "relation-target-invalid"
    SESSION_CLOSED = "session-closed"
    SUGGESTION_MISMATCH = "suggestion-mismatch"
    TARGET_NOT_EMPTY = "target_not_empty"
    UNKNOWN = "unknown"


def coded(code: ErrorCode, **facts: object) -> dict[str, object]:
    """A refusal that carries its own facts instead of a sentence.

    The code stays first — the key order the wire has always had — and each
    fact follows in the caller's order, so a dict built here serializes exactly
    as the inline one it replaces.
    """
    return {"code": code, **facts}


def coded_detail(
    code: ErrorCode,
    detail: str = "",
    *,
    row: int | None = None,
    field: str | None = None,
    **facts: object,
) -> dict[str, object]:
    """The refusal's detail: the code the surfaces localize, its sentence,
    then the optional structure the surface reads or marks instead of
    printing — ``row`` for a relation line's index in the sent list, ``field``
    for an entity field's name, and any further fact as a sibling key in the
    caller's order. Absent structure adds no key."""
    payload: dict[str, object] = {"code": code, "detail": detail}
    if row is not None:
        payload["row"] = row
    if field is not None:
        payload["field"] = field
    payload.update(facts)
    return payload
