"""PROMPT-003 backend Pydantic schema tests (CR-AUFG-07-16).

Validates request/response models for the preview, reset, and live-test
endpoints. All models are Pydantic v2 with ``from_attributes=True`` so
Core dataclasses can be mapped via ``model_validate``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare.prompts.schemas_prompt_ux import (
    LiveTestRequest,
    PreviewDiagnosticResponse,
    PreviewRequest,
    PreviewResponse,
    PreviewVariableMetadataResponse,
    ResetResponse,
)


def test_preview_request_accepts_empty_variables() -> None:
    """PreviewRequest defaults to empty variables and English language."""
    req = PreviewRequest(variables={}, language="en")
    assert req.language == "en"
    assert req.variables == {}
    assert req.edited_override is None
    assert req.genre is None
    assert req.mode is None


def test_preview_request_rejects_invalid_language() -> None:
    """Only the three supported locales are accepted."""
    with pytest.raises(ValidationError):
        PreviewRequest(
            variables={},
            language="english",  # type: ignore[reportArgumentType] # intentionally invalid
        )


def test_preview_request_accepts_all_supported_locales() -> None:
    """de, en, fr must all be valid."""
    for lang in ("en", "de", "fr"):
        req = PreviewRequest(variables={}, language=lang)
        assert req.language == lang


def test_preview_variable_metadata_round_trips() -> None:
    """Per-variable metadata serializes name + provenance + security."""
    meta = PreviewVariableMetadataResponse(
        name="language",
        description="ISO language code",
        variable_type="text",
        required=True,
        provenance="system_generated",
        security="system_only",
    )
    dumped = meta.model_dump()
    assert dumped["name"] == "language"
    assert dumped["provenance"] == "system_generated"
    assert dumped["security"] == "system_only"


def test_preview_diagnostic_rejects_unknown_kind() -> None:
    """Diagnostic kind is a closed Literal — unknown values are rejected."""
    with pytest.raises(ValidationError):
        PreviewDiagnosticResponse(
            kind="not_a_real_kind",  # type: ignore[reportArgumentType] # intentionally invalid
            variable_name="x",
            message="msg",
        )


def test_preview_diagnostic_accepts_all_documented_kinds() -> None:
    """All three documented diagnostic kinds must be accepted."""
    for kind in ("missing_variable", "unused_variable", "validation_note"):
        d = PreviewDiagnosticResponse(
            kind=kind,
            variable_name="x",
            message="msg",
        )
        assert d.kind == kind


def test_preview_response_round_trips() -> None:
    """PreviewResponse carries resolved text + variables + diagnostics."""
    resp = PreviewResponse(
        system_prompt="sys",
        user_prompt="usr",
        first_message=None,
        cascade_source="bundled",
        variables=[
            PreviewVariableMetadataResponse(
                name="language",
                description="ISO language code",
                variable_type="text",
                required=True,
                provenance="system_generated",
                security="system_only",
            ),
        ],
        diagnostics=[
            PreviewDiagnosticResponse(
                kind="missing_variable",
                variable_name="project_title",
                message="missing_required_variable:project_title",
            ),
        ],
    )
    dumped = resp.model_dump()
    assert dumped["system_prompt"] == "sys"
    assert dumped["variables"][0]["name"] == "language"
    assert dumped["diagnostics"][0]["kind"] == "missing_variable"
    assert dumped["first_message"] is None


def test_reset_response_carries_metadata() -> None:
    """ResetResponse surfaces effective_source + effective_content, not just bool."""
    resp = ResetResponse(
        reset=True,
        effective_source="bundled",
        effective_content="x",
    )
    assert resp.reset is True
    assert resp.effective_source == "bundled"
    assert resp.effective_content == "x"


def test_reset_response_false_when_no_override_existed() -> None:
    """Reset can be False (nothing to delete) with empty effective content."""
    resp = ResetResponse(reset=False, effective_source="bundled", effective_content="x")
    assert resp.reset is False


def test_live_test_request_defaults_acknowledge_to_false() -> None:
    """Token-cost acknowledgement defaults to False — clients must opt in."""
    req = LiveTestRequest(variables={"language": "en"})
    assert req.acknowledge_token_cost is False
    assert req.user_prompt == ""


def test_live_test_request_rejects_invalid_language() -> None:
    """LiveTestRequest language follows the same closed Literal as PreviewRequest."""
    with pytest.raises(ValidationError):
        LiveTestRequest(
            variables={},
            language="es",  # type: ignore[reportArgumentType] # intentionally invalid
        )
