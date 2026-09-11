"""Shared fixtures and helpers for generation name_service unit tests."""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from narrare.generation.name_service import NameGeneratorService
from narrare.generation.schemas import (
    GenderEnum,
    NameGenerateRequest,
    NameType,
)
from narrare_core.llm import ResolvedModelConfig
from tests.fakes.fake_llm_gateway import FakeModelRegistry

from ._ownership_fakes import permissive_novel_repo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_request(**overrides: Any) -> NameGenerateRequest:  # pyright: ignore[reportUnusedFunction]
    """Create a NameGenerateRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "project_id": uuid.uuid4(),
        "name_type": NameType.CHARACTER,
        "name_style": "fantasy",
        "count": 5,
        "gender": GenderEnum.ANY,
        "explanation_language": "en",
    }
    defaults.update(overrides)
    return NameGenerateRequest(**defaults)


def _make_config() -> ResolvedModelConfig:
    """Create a default ResolvedModelConfig for tests."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.8,
        max_tokens=2000,
    )


def _json_names_response(
    names: list[dict[str, str]],
) -> str:
    """Build a JSON string mimicking an LLM response for names."""
    return json.dumps(names)


# Sample LLM responses for reuse

SAMPLE_ARRAY_RESPONSE = _json_names_response(
    [
        {"name": "Aelindra", "pronunciation": "ay-LIN-dra", "meaning": "starlight"},
        {"name": "Theron", "pronunciation": "THEH-ron", "meaning": "hunter"},
        {"name": "Lyris", "pronunciation": "LYE-ris", "meaning": "song of the dawn"},
    ]
)

SAMPLE_OBJECT_RESPONSE = json.dumps(
    {
        "names": [
            {"name": "Kaelen", "meaning": "fire spirit"},
            {"name": "Morwen", "meaning": "dark maiden"},
        ],
    }
)

SAMPLE_FENCED_RESPONSE = (
    "```json\n"
    + _json_names_response(
        [
            {"name": "Zara", "meaning": "radiance"},
            {"name": "Dorian", "meaning": "gift"},
        ]
    )
    + "\n```"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_registry() -> FakeModelRegistry:
    """Fake ModelRegistry with programmable responses."""
    return FakeModelRegistry()


@pytest.fixture
def fake_gateway() -> Any:
    """Backward-compatible fake gateway — delegates to FakeModelRegistry."""
    from tests.fakes.fake_llm_gateway import FakeLLMGateway

    return FakeLLMGateway()


@pytest.fixture
def mock_composer() -> AsyncMock:
    """Mock PromptComposer that returns a simple composed prompt."""
    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock()
    composer.build.return_value = ComposedPrompt(
        system="You are a name generator.",
        user="Generate 5 character names for a fantasy setting.",
    )
    return composer


@pytest.fixture
def config() -> ResolvedModelConfig:
    return _make_config()


@pytest.fixture
def service(
    fake_registry: FakeModelRegistry,
    mock_composer: AsyncMock,
    config: ResolvedModelConfig,
) -> NameGeneratorService:
    """NameGeneratorService wired with fake registry and mock composer.

    No KB repo is injected — dedup tests should create their own service
    instance with a FakeKBRepository.
    """
    return NameGeneratorService(
        registry=fake_registry,
        composer=mock_composer,
        config=config,
        novel_repo=permissive_novel_repo(),
        api_key=None,
        base_url=None,
        kb_repo=None,
    )
