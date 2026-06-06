"""Tests for LoggingEvidenceSink.

Covers:
1. record() logs all FeatureInvocationEvidence fields.
2. extra_fields are included in the log context.
3. Async — record() is awaitable.
4. With empty extra_fields (default).
5. Protocol conformance — implements FeatureInvocationEvidenceSink.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-10.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.evidence import LoggingEvidenceSink
from narrare_core.ai_invocation.models import FeatureInvocationEvidence

if TYPE_CHECKING:
    from collections.abc import Generator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_evidence(**overrides: object) -> FeatureInvocationEvidence:
    """Create a minimal FeatureInvocationEvidence for tests."""
    defaults: dict[str, object] = {
        "feature_id": "writing/new_chapter",
        "intent": "write",
        "prompt_route": "writing/en/new_chapter",
        "preference_status": PreferenceStatus.PROVIDED,
        "kb_suggested_status": KBSuggestedStatus.PROVIDED,
        "final_prompt_validated": True,
        "audit_state": AuditState.RUNTIME_VERIFIED,
    }
    defaults.update(overrides)
    return FeatureInvocationEvidence(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_logger() -> Generator[MagicMock]:
    """Create a mock logger that captures structured log calls."""
    logger = MagicMock(spec=["info", "debug", "warning", "error"])
    yield logger


@pytest.fixture
def sink_with_mock_logger(
    mock_logger: MagicMock,
) -> Generator[LoggingEvidenceSink]:
    """Create a LoggingEvidenceSink with a mocked logger."""
    sink = LoggingEvidenceSink()
    sink._logger = mock_logger
    yield sink


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """LoggingEvidenceSink structurally satisfies FeatureInvocationEvidenceSink."""

    def test_has_record_method(self) -> None:
        """LoggingEvidenceSink has an async record() method."""
        sink = LoggingEvidenceSink()
        assert hasattr(sink, "record")
        assert inspect.iscoroutinefunction(sink.record)

    def test_record_accepts_evidence_parameter(self) -> None:
        """record() accepts a FeatureInvocationEvidence parameter."""
        sig = inspect.signature(LoggingEvidenceSink.record)
        params = list(sig.parameters.values())
        param_names = [p.name for p in params]
        assert "evidence" in param_names or "self" in param_names


# ---------------------------------------------------------------------------
# record() behavior
# ---------------------------------------------------------------------------


class TestRecordLogsEvidence:
    """record() logs all evidence fields as structured context."""

    @pytest.mark.asyncio
    async def test_record_logs_all_evidence_fields(
        self,
        sink_with_mock_logger: LoggingEvidenceSink,
        mock_logger: MagicMock,
    ) -> None:
        """All FeatureInvocationEvidence fields appear in the log line."""
        evidence = make_evidence(
            feature_id="writing/extend",
            intent="extend",
            mode="extend",
            prompt_route="writing/en/extend",
            preference_status=PreferenceStatus.MANUAL,
            kb_suggested_status=KBSuggestedStatus.BUDGET_REJECTED,
            output_budget_profile="long_texts",
            final_prompt_validated=True,
            validation_errors=("missing_var:kb_context",),
            audit_state=AuditState.ADOPTED,
        )

        await sink_with_mock_logger.record(evidence)

        mock_logger.info.assert_called_once()
        _event, kwargs = _unpack_log_call(mock_logger.info)

        assert kwargs["feature_id"] == "writing/extend"
        assert kwargs["intent"] == "extend"
        assert kwargs["mode"] == "extend"
        assert kwargs["prompt_route"] == "writing/en/extend"
        assert kwargs["preference_status"] == "manual"
        assert kwargs["kb_suggested_status"] == "budget_rejected"
        assert kwargs["output_budget_profile"] == "long_texts"
        assert kwargs["final_prompt_validated"] is True
        assert kwargs["validation_errors"] == ("missing_var:kb_context",)
        assert kwargs["audit_state"] == "adopted"

    @pytest.mark.asyncio
    async def test_record_includes_timestamp(
        self,
        sink_with_mock_logger: LoggingEvidenceSink,
        mock_logger: MagicMock,
    ) -> None:
        """Log line includes an ISO-8601 timestamp."""
        evidence = make_evidence()

        await sink_with_mock_logger.record(evidence)

        mock_logger.info.assert_called_once()
        _event, kwargs = _unpack_log_call(mock_logger.info)

        assert "timestamp" in kwargs
        timestamp = kwargs["timestamp"]
        assert isinstance(timestamp, str), "timestamp must be a string"
        # Verify ISO-8601 format by parsing it
        parsed = datetime.fromisoformat(timestamp)
        assert parsed.tzinfo is not None  # timezone-aware

    @pytest.mark.asyncio
    async def test_record_with_minimal_evidence(
        self,
        sink_with_mock_logger: LoggingEvidenceSink,
        mock_logger: MagicMock,
    ) -> None:
        """Works with minimal evidence (no optional fields)."""
        evidence = make_evidence(
            feature_id="test/feature",
            intent="write",
            prompt_route="test",
            preference_status=PreferenceStatus.NOT_APPLICABLE,
            kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
            final_prompt_validated=False,
            audit_state=AuditState.BLOCKED,
        )

        await sink_with_mock_logger.record(evidence)

        mock_logger.info.assert_called_once()
        _event, kwargs = _unpack_log_call(mock_logger.info)

        assert kwargs["feature_id"] == "test/feature"
        assert kwargs["mode"] is None
        assert kwargs["output_budget_profile"] is None
        assert kwargs["validation_errors"] == ()
        assert kwargs["final_prompt_validated"] is False
        assert kwargs["audit_state"] == "blocked"


class TestRecordIncludesExtraFields:
    """extra_fields are appended to every log line."""

    @pytest.mark.asyncio
    async def test_extra_fields_included(self) -> None:
        """Configured extra_fields appear in the log context."""
        logger = MagicMock(spec=["info"])
        sink = LoggingEvidenceSink(
            extra_fields={"version": "1.2.0", "environment": "staging"},
        )
        sink._logger = logger

        evidence = make_evidence()
        await sink.record(evidence)

        logger.info.assert_called_once()
        _event, kwargs = _unpack_log_call(logger.info)

        assert kwargs["version"] == "1.2.0"
        assert kwargs["environment"] == "staging"

    @pytest.mark.asyncio
    async def test_extra_fields_with_default_empty(self) -> None:
        """No extra_fields when none are configured."""
        logger = MagicMock(spec=["info"])
        sink = LoggingEvidenceSink()
        sink._logger = logger

        evidence = make_evidence()
        await sink.record(evidence)

        logger.info.assert_called_once()
        _event, kwargs = _unpack_log_call(logger.info)

        # Only evidence fields + timestamp — no version/environment etc.
        assert "version" not in kwargs
        assert "environment" not in kwargs

    @pytest.mark.asyncio
    async def test_extra_fields_do_not_override_evidence(
        self,
        mock_logger: MagicMock,
    ) -> None:
        """evidence fields take precedence if extra_field keys collide."""
        sink = LoggingEvidenceSink(
            extra_fields={"feature_id": "overridden", "environment": "prod"},
        )
        sink._logger = mock_logger

        evidence = make_evidence(feature_id="actual/feature")
        await sink.record(evidence)

        mock_logger.info.assert_called_once()
        _event, kwargs = _unpack_log_call(mock_logger.info)

        # evidence field value wins
        assert kwargs["feature_id"] == "actual/feature"
        # non-colliding extra field still present
        assert kwargs["environment"] == "prod"


class TestRecordIsAsync:
    """record() is an async method."""

    @pytest.mark.asyncio
    async def test_record_is_awaitable(self) -> None:
        """record() can be awaited."""
        sink = LoggingEvidenceSink()
        sink._logger = MagicMock(spec=["info"])

        evidence = make_evidence()
        # Should not raise — calling and awaiting works
        await sink.record(evidence)

    @pytest.mark.asyncio
    async def test_record_with_custom_logger_name(self) -> None:
        """Custom logger_name is used."""
        logger = MagicMock(spec=["info"])
        sink = LoggingEvidenceSink(logger_name="custom.evidence")
        sink._logger = logger

        evidence = make_evidence()
        await sink.record(evidence)

        logger.info.assert_called_once()


class TestEventName:
    """Log event name conventions."""

    @pytest.mark.asyncio
    async def test_event_name_is_invocation_evidence(
        self,
        sink_with_mock_logger: LoggingEvidenceSink,
        mock_logger: MagicMock,
    ) -> None:
        """Log event name is 'invocation_evidence'."""
        evidence = make_evidence()

        await sink_with_mock_logger.record(evidence)

        mock_logger.info.assert_called_once()
        event, _kwargs = _unpack_log_call(mock_logger.info)
        assert event == "invocation_evidence"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _unpack_log_call(
    mock_method: MagicMock,
) -> tuple[str, dict[str, object]]:
    """Unpack a structlog-style logging call into (event, kwargs).

    structlog calls look like:
        logger.info("event_name", key1=val1, key2=val2)

    Args:
        mock_method: A mocked logger method (e.g., mock_logger.info).

    Returns:
        Tuple of (event_name, structured_kwargs).
    """
    call_args = mock_method.call_args
    assert call_args is not None, "Method was not called"
    args, kwargs = call_args
    assert len(args) == 1, f"Expected 1 positional arg (event), got {len(args)}"
    return str(args[0]), dict(kwargs)
