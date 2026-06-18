"""Unit tests for the Backend-local RefIntegrityIssueSink.

The sink is the write-side advisory channel consumers use to surface
``RefIntegrityIssue`` instances the moment a KB lifecycle event happens
(ADR-050 P1-B). The authoritative read-side remains
``CrossFeatureRefIndex.check_refs``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.consistency.ref_integrity_sink import (
    InMemoryRefIntegrityIssueSink,
    LoggingRefIntegrityIssueSink,
    RefIntegrityIssueSink,
)
from narrare_core.context.integration_contracts import RefIntegrityIssue

if TYPE_CHECKING:
    import pytest


def _make_issue(reason: str = "deleted_ref_without_tombstone") -> RefIntegrityIssue:
    return RefIntegrityIssue(
        consumer_feature="timeline",
        consumer_location="timeline_events[0].character_refs[1]",
        ref_kind="id",
        ref_value=str(uuid4()),
        resolved_status="deleted",
        reason=reason,  # type: ignore[arg-type]
        suggested_action="warn_only",  # type: ignore[arg-type]
    )


class TestInMemorySink:
    async def test_emit_collects_issues_in_order(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        first = _make_issue("deleted_ref_without_tombstone")
        second = _make_issue("stale_name_ref")

        await sink.emit(first)
        await sink.emit(second)

        assert sink.issues == [first, second]

    async def test_drain_returns_and_clears_collected_issues(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        issue = _make_issue()
        await sink.emit(issue)

        drained = sink.drain()

        assert drained == [issue]
        assert sink.issues == []

    async def test_drain_on_empty_returns_empty_list(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        assert sink.drain() == []

    def test_in_memory_sink_satisfies_protocol(self) -> None:
        sink = InMemoryRefIntegrityIssueSink()
        assert isinstance(sink, RefIntegrityIssueSink)


class TestLoggingSink:
    async def test_emit_does_not_raise(self, caplog: pytest.LogCaptureFixture) -> None:
        sink = LoggingRefIntegrityIssueSink()
        # Must not raise — logging is the emission; failure here would violate
        # the contract that observers never block the KB operation.
        await sink.emit(_make_issue())

    def test_logging_sink_satisfies_protocol(self) -> None:
        sink = LoggingRefIntegrityIssueSink()
        assert isinstance(sink, RefIntegrityIssueSink)


class TestProtocol:
    def test_protocol_is_runtime_checkable(self) -> None:
        # A custom object implementing async emit() must satisfy the Protocol.
        class _Custom:
            async def emit(self, issue: RefIntegrityIssue) -> None:
                del issue

        assert isinstance(_Custom(), RefIntegrityIssueSink)
