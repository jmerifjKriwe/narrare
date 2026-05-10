"""Unit tests for setup/schemas.py"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare.setup.schemas import (
    AIProvider,
    StarterContent,
    Step1LocationRequest,
    Step4ProviderRequest,
    StoryStructure,
    StoryTone,
    WizardState,
)


class TestStep1LocationRequest:
    def test_valid_project_name(self) -> None:
        req = Step1LocationRequest(project_name="My Novel Project", language="en")
        assert req.project_name == "My Novel Project"

    def test_invalid_characters_in_name(self) -> None:
        with pytest.raises(ValidationError, match="invalid characters"):
            Step1LocationRequest(project_name="Novel/Project", language="en")

    def test_slash_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Step1LocationRequest(project_name="a/b", language="en")

    def test_backslash_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Step1LocationRequest(project_name="a\\b", language="en")

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Step1LocationRequest(project_name="", language="en")

    def test_autosave_defaults_to_30(self) -> None:
        req = Step1LocationRequest(project_name="Novel", language="en")
        assert req.autosave_interval == 30

    def test_autosave_zero_allowed(self) -> None:
        req = Step1LocationRequest(project_name="Novel", language="en", autosave_interval=0)
        assert req.autosave_interval == 0

    def test_autosave_above_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Step1LocationRequest(project_name="Novel", language="en", autosave_interval=3601)


class TestStoryStructureEnum:
    def test_all_values_valid(self) -> None:
        for value in StoryStructure:
            assert StoryStructure(value) == value

    def test_default_is_three_act(self) -> None:
        from narrare.setup.schemas import Step2NovelRequest

        req = Step2NovelRequest(title="My Novel")
        assert req.story_structure == StoryStructure.THREE_ACT


class TestAIProviderEnum:
    def test_all_expected_providers_exist(self) -> None:
        expected = {"anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai"}
        actual = {p.value for p in AIProvider}
        assert expected == actual


class TestStep4ProviderRequest:
    def test_requires_model(self) -> None:
        with pytest.raises(ValidationError):
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
            language="en",
            autosave_interval=30,
            title="My Novel",
            author="Test Author",
            genre="fantasy",
            logline="A story about things.",
            story_structure=StoryStructure.THREE_ACT,
            tone=StoryTone.DRAMATIC,
            starter=StarterContent.BLANK,
            import_path=None,
            provider=AIProvider.ANTHROPIC,
            api_key="test-key",
            model="claude-haiku-3-5-20241022",
            ollama_url="http://localhost:11434",
        )
        assert state.title == "My Novel"
        assert state.starter == StarterContent.BLANK
