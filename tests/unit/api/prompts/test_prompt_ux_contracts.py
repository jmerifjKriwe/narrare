"""PROMPT-003 backend contract-shape tests (CR-AUFG-07-16).

Verifies that the API-layer Protocols exist and expose the expected
methods BEFORE any service implementation is written. This is the
RULE-03 gate: contracts precede services.
"""

from __future__ import annotations

from narrare.prompts.contracts import (
    PromptLiveTestApiProtocol,
    PromptPreviewApiProtocol,
    PromptResetApiProtocol,
)


def test_preview_protocol_has_preview_method() -> None:
    """PromptPreviewApiProtocol must expose a ``preview`` coroutine."""
    assert hasattr(PromptPreviewApiProtocol, "preview")


def test_reset_protocol_has_reset_with_metadata_method() -> None:
    """PromptResetApiProtocol must expose ``reset_with_metadata``."""
    assert hasattr(PromptResetApiProtocol, "reset_with_metadata")


def test_live_test_protocol_has_stream_live_test_method() -> None:
    """PromptLiveTestApiProtocol must expose ``stream_live_test``."""
    assert hasattr(PromptLiveTestApiProtocol, "stream_live_test")


def test_live_test_protocol_has_validate_live_test_method() -> None:
    """PromptLiveTestApiProtocol must expose ``validate_live_test`` for gating."""
    assert hasattr(PromptLiveTestApiProtocol, "validate_live_test")
