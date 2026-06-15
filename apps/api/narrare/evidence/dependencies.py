"""Dependency injection factories for the evidence module.

Selects the appropriate ``FeatureInvocationEvidenceSink`` based on the
``use_persistent_evidence`` setting (ADR-042 § Wiring in Production).

- ``use_persistent_evidence=True``  → ``PersistentEvidenceSink`` (PostgreSQL)
- ``use_persistent_evidence=False`` → ``LoggingEvidenceSink`` (ephemeral logs)

Default is ``False`` so dev/test environments are unaffected.

See ADR-042 for the hybrid evidence architecture.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.config import get_settings
from narrare._app.database import get_session_factory
from narrare.evidence.sink import PersistentEvidenceSink

if TYPE_CHECKING:
    from narrare_core.ai_invocation.contracts import FeatureInvocationEvidenceSink


def get_evidence_sink() -> FeatureInvocationEvidenceSink:
    """Return the configured evidence sink.

    Reads ``settings.use_persistent_evidence`` at call time. Because
    ``get_invocation_pipeline`` is ``@lru_cache``'d (singleton), this factory
    is invoked exactly once per process and the chosen sink lives for the
    application lifetime.

    The ``PersistentEvidenceSink`` holds a session *factory* (callable), not a
    single session — correct for a singleton lifecycle, since each
    ``record()`` call acquires and releases its own session.

    Returns:
        ``PersistentEvidenceSink`` when persistent evidence is enabled,
        otherwise ``LoggingEvidenceSink``.
    """
    from narrare_core.ai_invocation import LoggingEvidenceSink

    if get_settings().use_persistent_evidence:
        return PersistentEvidenceSink(session_factory=get_session_factory())
    return LoggingEvidenceSink()
