"""Tests for _TONE_INSTRUCTIONS expansion.

Task 2.5: Verify all 9 tones present, balanced is empty, others have content.
"""

from narrare_core.writing.pipeline import _TONE_INSTRUCTIONS


class TestToneInstructions:
    def test_all_nine_tones_present(self) -> None:
        ALL_TONES = {
            "balanced",
            "dramatic",
            "humorous",
            "suspenseful",
            "contemplative",
            "romantic",
            "dark",
            "adventurous",
            "quiet",
        }
        assert set(_TONE_INSTRUCTIONS.keys()) == ALL_TONES

    def test_balanced_is_empty(self) -> None:
        assert _TONE_INSTRUCTIONS["balanced"] == ""

    def test_other_tones_have_instructions(self) -> None:
        for tone, instr in _TONE_INSTRUCTIONS.items():
            if tone != "balanced":
                assert instr.strip(), f"{tone} should have non-empty instructions"
