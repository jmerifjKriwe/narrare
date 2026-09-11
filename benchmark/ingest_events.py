"""Run-scoped raw-event sink for ingest steps — event type + sanitization.

Every build-path HTTP exchange is appended to a caller-owned ``list`` as one
frozen ``IngestEvent`` (plan Task 6 "raw-events sink"; consumed by the
Task 14 run artifacts). Events carry the step name, chapter scope, method,
path, status, wall-time cost, and BOTH bodies. Headers are NEVER recorded:
the auth plane lives exclusively in ``Authorization`` headers, so omitting
headers makes token leakage structurally impossible instead of filtered.

Sanitization is a recursive rebuild: every dict/list on the way down becomes
a NEW container (an event never aliases caller or backend objects), and any
key whose lowercased name is in ``SENSITIVE_KEYS`` has its value replaced by
``REDACTED``; values under other keys pass through unchanged. JSON-shaped
payloads only (dict/list/scalars) — exactly what the API exchanges carry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final, cast

REDACTED: Final[str] = "[REDACTED]"
"""Replacement value for every sensitive field (artifact-visible marker)."""

SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "password",
        "refresh_token",
        "secret_key",
    }
)
"""Keys redacted wherever they appear (case-insensitive), at any depth."""


@dataclass(frozen=True)
class IngestEvent:
    """One recorded HTTP exchange of the build path (artifact evidence)."""

    step: str
    chapter_stem: str | None
    method: str
    path: str
    status: int
    elapsed_seconds: float
    request_body: object | None
    response_body: object


def sanitize(value: object) -> object:
    """Deep-copy ``value`` with every sensitive key's value replaced."""
    if isinstance(value, dict):
        mapping = cast("dict[str, object]", value)
        return {
            key: (REDACTED if key.lower() in SENSITIVE_KEYS else sanitize(item))
            for key, item in mapping.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in cast("list[object]", value)]
    return value


def record(
    events: list[IngestEvent],
    *,
    step: str,
    chapter_stem: str | None,
    method: str,
    path: str,
    status: int,
    started: float,
    request_body: object | None,
    response_body: object,
) -> None:
    """Append one timed, sanitized event to the caller-owned sink.

    ``started`` is the exchange's ``time.perf_counter()`` start; the
    elapsed time covers the full request/response round trip plus parsing.
    """
    events.append(
        IngestEvent(
            step=step,
            chapter_stem=chapter_stem,
            method=method,
            path=path,
            status=status,
            elapsed_seconds=time.perf_counter() - started,
            request_body=sanitize(request_body),
            response_body=sanitize(response_body),
        )
    )
