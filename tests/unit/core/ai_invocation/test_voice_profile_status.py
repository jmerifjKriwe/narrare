"""Tests for VoiceProfileStatus enum.

Covers: enum values, string conversion, membership, and construction.

See: ADR-040, ADR-038, INFRA-013.
"""

from __future__ import annotations

from narrare_core.ai_invocation._enums import VoiceProfileStatus


class TestVoiceProfileStatus:
    """VoiceProfileStatus enum values and string conversion."""

    def test_provided_value(self) -> None:
        """PROVIDED enum value is 'provided'."""
        assert VoiceProfileStatus.PROVIDED == "provided"

    def test_not_applicable_value(self) -> None:
        """NOT_APPLICABLE enum value is 'not_applicable'."""
        assert VoiceProfileStatus.NOT_APPLICABLE == "not_applicable"

    def test_missing_value(self) -> None:
        """MISSING enum value is 'missing'."""
        assert VoiceProfileStatus.MISSING == "missing"

    def test_str_conversion(self) -> None:
        """str() on enum returns the value string."""
        assert str(VoiceProfileStatus.PROVIDED) == "provided"
        assert str(VoiceProfileStatus.NOT_APPLICABLE) == "not_applicable"
        assert str(VoiceProfileStatus.MISSING) == "missing"

    def test_all_members(self) -> None:
        """Enum has exactly three members."""
        members = list(VoiceProfileStatus)
        assert len(members) == 3
        assert set(members) == {
            VoiceProfileStatus.PROVIDED,
            VoiceProfileStatus.NOT_APPLICABLE,
            VoiceProfileStatus.MISSING,
        }

    def test_from_value(self) -> None:
        """Enum can be constructed from string value."""
        assert VoiceProfileStatus("provided") == VoiceProfileStatus.PROVIDED
        assert VoiceProfileStatus("missing") == VoiceProfileStatus.MISSING
