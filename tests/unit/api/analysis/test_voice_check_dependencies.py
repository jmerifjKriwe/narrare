"""Unit tests for WRITE-010 voice-check dependency wiring."""

from __future__ import annotations

from typing import get_type_hints

from narrare._app.dependencies import SessionDep
from narrare.analysis.dependencies_voice_check import get_voice_check_service
from narrare.analysis.voice_check_service import CharacterVoiceCheckerService


def test_get_voice_check_service_uses_session_dep() -> None:
    """Dependency factory keeps FastAPI session injection on SessionDep (RULE-19)."""
    hints = get_type_hints(
        get_voice_check_service,
        localns={"CharacterVoiceCheckerService": CharacterVoiceCheckerService},
        include_extras=True,
    )

    assert hints["session"] == SessionDep


def test_get_voice_check_service_return_annotation_is_concrete_service() -> None:
    """Factory returns the WRITE-010 service type used by the router."""
    hints = get_type_hints(
        get_voice_check_service,
        localns={"CharacterVoiceCheckerService": CharacterVoiceCheckerService},
    )

    assert hints["return"] is CharacterVoiceCheckerService
