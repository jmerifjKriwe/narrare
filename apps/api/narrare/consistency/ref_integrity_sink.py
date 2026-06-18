"""Backend-local sink for ``RefIntegrityIssue`` (ADR-050 P1-B).

Consumers of KB entity lifecycle events surface stale/dangling refs as
:class:`RefIntegrityIssue` instances. The Core Protocol
:class:`KBEntityLifecycleObserver` returns ``None`` from its notification
methods, so consumers need a channel to hand issues to. This module
provides that channel as a Backend-local Protocol plus two
implementations.

Why a Backend-local Protocol and not a Core contract: the Core
``RefIntegrityIssue`` type is the shared vocabulary (RULE-07 — Core owns
vocabulary), but *where* an issue goes is a Backend policy decision
(logging vs. in-memory collection vs. future persistence). Core stays
frozen; Backend owns the sink shape.

Authoritative read-side: :class:`CrossFeatureRefIndex.check_refs`
recomputes issues on demand so the system stays consistent even if an
observer event is missed (ADR-050 Option B — eventual consistency
window mitigated by the next consistency check).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    from narrare_core.context.integration_contracts import RefIntegrityIssue

logger = structlog.get_logger(__name__)


@runtime_checkable
class RefIntegrityIssueSink(Protocol):
    """Write-side channel for :class:`RefIntegrityIssue` instances.

    Consumers call :meth:`emit` from within their
    :class:`KBEntityLifecycleObserver` notification methods. Emission is
    advisory — it must never block or fail the KB operation (RULE-11).
    """

    async def emit(self, issue: RefIntegrityIssue) -> None:
        """Record a single ref-integrity issue.

        Args:
            issue: The issue produced by a consumer observing a KB
                lifecycle change. Implementations MUST NOT raise.
        """
        ...


class LoggingRefIntegrityIssueSink:
    """Default sink that logs every issue via structlog.

    Used in production wiring where the authoritative issue list is
    recomputed by :class:`CrossFeatureRefIndex.check_refs` at
    consistency-check time. Logging here gives observability of the
    write-side notification without coupling KB mutations to issue
    persistence.
    """

    async def emit(self, issue: RefIntegrityIssue) -> None:
        logger.info(
            "ref_integrity_issue",
            consumer_feature=issue.consumer_feature,
            consumer_location=issue.consumer_location,
            ref_kind=issue.ref_kind,
            ref_value=issue.ref_value,
            resolved_status=issue.resolved_status,
            reason=issue.reason,
            suggested_action=issue.suggested_action,
        )


class InMemoryRefIntegrityIssueSink:
    """Collects issues into a list. Primarily for tests and request-scoped drains.

    ``drain()`` returns and clears the collected issues so a caller
    (e.g. a consistency pipeline or a test) can inspect what was
    emitted without holding references across the observer call.
    """

    def __init__(self) -> None:
        self._issues: list[RefIntegrityIssue] = []

    @property
    def issues(self) -> list[RefIntegrityIssue]:
        """Snapshot of collected issues (in emission order)."""
        return list(self._issues)

    async def emit(self, issue: RefIntegrityIssue) -> None:
        self._issues.append(issue)

    def drain(self) -> list[RefIntegrityIssue]:
        """Return collected issues and clear the buffer."""
        collected = self._issues
        self._issues = []
        return collected
