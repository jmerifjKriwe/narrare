"""Unit tests for setup/schemas.py"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare.setup.schemas import (
    AIProvider,
    StarterContent,
    Step1LocationRequest,
    Step2NovelRequest,
    Step4ProviderRequest,
    StoryStructure,
    StoryTone,
    WizardState,
)


class TestStep1LocationRequest:
    def test_valid_project_name(self) -> None:
        req = Step1LocationRequest(project_name="My Novel Project", writing_language="en")
        assert req.project_name == "My Novel Project"

    def test_invalid_characters_in_name(self) -> None:
        with pytest.raises(ValidationError, match="invalid characters"):
            Step1LocationRequest(project_name="Novel/Project", writing_language="en")

    def test_slash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="invalid characters"):
            Step1LocationRequest(project_name="a/b", writing_language="en")

    def test_backslash_rejected(self) -> None:
        with pytest.raises(ValidationError, match="invalid characters"):
            Step1LocationRequest(project_name="a\\b", writing_language="en")

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least 1"):
            Step1LocationRequest(project_name="", writing_language="en")

    def test_autosave_defaults_to_30(self) -> None:
        req = Step1LocationRequest(project_name="Novel", writing_language="en")
        assert req.autosave_interval == 30

    def test_autosave_zero_allowed(self) -> None:
        req = Step1LocationRequest(project_name="Novel", writing_language="en", autosave_interval=0)
        assert req.autosave_interval == 0

    def test_autosave_above_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match="less than or equal to 3600"):
            Step1LocationRequest(
                project_name="Novel", writing_language="en", autosave_interval=3601
            )


class TestStoryStructureEnum:
    def test_all_values_valid(self) -> None:
        for value in StoryStructure:
            assert StoryStructure(value) == value

    def test_default_is_three_act(self) -> None:
        from narrare.setup.schemas import Step2NovelRequest

        req = Step2NovelRequest(title="My Novel")
        assert req.story_structure == StoryStructure.THREE_ACT


class TestStoryToneEnum:
    """RULE-17 parity: backend ``StoryTone`` must match the frontend wizard type.

    Source of truth for the expected value set is
    ``packages/web/types/wizard.ts`` (``StoryTone`` union). When a tone is
    added here, the frontend type AND
    ``packages/core/narrare_core/writing/_tone_data.py`` (``TONE_INSTRUCTIONS``)
    must carry the same value — otherwise the wizard selection is rejected by
    backend validation (CR: ``balanced``/``quiet`` were once missing here while
    the frontend already offered them).
    """

    EXPECTED_TONES: frozenset[str] = frozenset(
        {
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
    )

    def test_enum_values_match_frontend_wizard_type(self) -> None:
        """Backend enum values must exactly equal the frontend ``StoryTone`` union."""
        actual = {t.value for t in StoryTone}
        extra = actual - self.EXPECTED_TONES
        missing = self.EXPECTED_TONES - actual
        assert not extra, f"RULE-17 drift — backend-only tones: {sorted(extra)}"
        assert not missing, f"RULE-17 drift — backend missing tones: {sorted(missing)}"

    def test_step2_accepts_every_frontend_tone(self) -> None:
        """``Step2NovelRequest`` must accept every tone the wizard can send.

        Uses ``model_validate`` to exercise the JSON-body coercion path that
        FastAPI uses when the frontend posts the wizard state.
        """
        for tone in self.EXPECTED_TONES:
            req = Step2NovelRequest.model_validate({"title": "T", "tone": tone})
            assert req.tone == tone

    def test_step2_rejects_unknown_tone(self) -> None:
        """Unknown tone strings are still rejected (enum validation intact)."""
        with pytest.raises(ValidationError):
            Step2NovelRequest.model_validate({"title": "T", "tone": "not-a-real-tone"})


class TestAIProviderEnum:
    def test_all_expected_providers_exist(self) -> None:
        expected = {"anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai"}
        actual = {p.value for p in AIProvider}
        assert expected == actual


class TestStep4ProviderRequest:
    def test_requires_model(self) -> None:
        with pytest.raises(ValidationError, match="at least 1"):
            Step4ProviderRequest(provider=AIProvider.ANTHROPIC, api_key="key", model="")

    def test_valid_request(self) -> None:
        req = Step4ProviderRequest(
            provider=AIProvider.ANTHROPIC,
            api_key="sk-ant-test",
            model="claude-haiku-3-5-20241022",
        )
        assert req.provider == AIProvider.ANTHROPIC


class TestWizardState:
    def test_constructs_with_all_fields(self) -> None:
        state = WizardState(
            project_name="Test",
            writing_language="en",
            autosave_interval=30,
            title="My Novel",
            author="Test Author",
            genre="fantasy",
            logline="A story about things.",
            story_structure=StoryStructure.THREE_ACT,
            tone=StoryTone.DRAMATIC,
            starter=StarterContent.BLANK,
            provider=AIProvider.ANTHROPIC,
            api_key="test-key",
            model="claude-haiku-3-5-20241022",
            ollama_url="http://localhost:11434",
        )
        assert state.title == "My Novel"
        assert state.starter == StarterContent.BLANK
