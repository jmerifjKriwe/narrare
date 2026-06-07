"""Unit tests for ExtractionService — CR-01 prompt governance.

Split from test_extraction_service.py per RULE-04 (file size limit).

Tests:
- PromptComposer resolution (no inline fallback)
- Correct KB_EXTRACT intent
- Real composer integration with runtime context
- PromptNotFoundError propagation (no silent fallback)
- KB repo error graceful degradation (empty dedup list, extraction continues)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts import PromptComposer, PromptRegistry
from narrare_core.shared.errors import PromptNotFoundError

from ._extraction_helpers import (
    FakeChapterRepo,
    FakeComposer,
    FakeKBRepo,
    FakeModelRegistry,
    make_chapter,
    make_extraction_output,
    make_service,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test", model_id="test-model", temperature=0.7, max_tokens=4096
    )


@pytest.fixture
def mock_registry() -> FakeModelRegistry:
    return FakeModelRegistry()


@pytest.fixture
def mock_composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def mock_chapter_repo() -> FakeChapterRepo:
    return FakeChapterRepo()


@pytest.fixture
def mock_kb_repo() -> FakeKBRepo:
    return FakeKBRepo()


# ---------------------------------------------------------------------------
# PromptComposer resolution — no inline fallbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_system_prompt_uses_composer(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """_build_system_prompt returns PromptComposer output, not fallback."""
    mock_composer.build = AsyncMock(
        return_value=MagicMock(spec=object, system="Bundled extraction prompt"),
    )
    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)

    result = await service._build_system_prompt(
        chapter_title="Chapter 1",
        existing_entity_names=["Anna"],
    )

    assert result == "Bundled extraction prompt"
    mock_composer.build.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_system_prompt_correct_intent(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """_build_system_prompt calls composer.build with KB_EXTRACT intent."""
    mock_composer.build = AsyncMock(
        return_value=MagicMock(spec=object, system="prompt"),
    )
    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)

    await service._build_system_prompt(
        chapter_title="Chapter 1",
        existing_entity_names=["Anna"],
    )

    intent_arg = mock_composer.build.call_args[0][0]
    assert intent_arg.name == "KB_EXTRACT"


@pytest.mark.asyncio
async def test_build_system_prompt_with_real_composer_routes_runtime_context(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
) -> None:
    """Production path routes extraction data through bundled templates."""
    service = make_service(
        mock_registry,
        config,
        mock_chapter_repo,
        mock_kb_repo,
        PromptComposer(PromptRegistry()),
    )

    result = await service._build_system_prompt(
        chapter_title="Into the Forest",
        existing_entity_names=["Anna", "Dark Forest"],
    )

    assert "Knowledge Base extraction agent" in result
    assert "Into the Forest" in result
    assert "Anna" in result
    assert "Dark Forest" in result


# ---------------------------------------------------------------------------
# Typed error propagation — no silent failures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_when_prompt_missing_propagates_typed_error(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """Missing Composer templates are not replaced with inline fallback bodies."""
    chapter = make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter
    mock_composer.build = AsyncMock(side_effect=PromptNotFoundError("kb", "en", "extract"))
    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)

    with (
        patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent,
        pytest.raises(PromptNotFoundError),
    ):
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

    MockAgent.assert_not_called()


@pytest.mark.asyncio
async def test_extract_when_existing_entities_lookup_fails_degrades_gracefully(
    mock_registry: FakeModelRegistry,
    config: ResolvedModelConfig,
    mock_chapter_repo: FakeChapterRepo,
    mock_kb_repo: FakeKBRepo,
    mock_composer: FakeComposer,
) -> None:
    """KB repo failure degrades gracefully: empty dedup list, extraction continues."""
    chapter = make_chapter()
    mock_chapter_repo.get_by_id.return_value = chapter
    mock_kb_repo.list_entries = AsyncMock(side_effect=RuntimeError("repository offline"))
    service = make_service(mock_registry, config, mock_chapter_repo, mock_kb_repo, mock_composer)

    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=make_extraction_output())
        MockAgent.return_value = mock_agent

        result = await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

        # Extraction succeeds despite KB repo failure
        assert result is not None
        assert len(result.results) == 1

        # Agent was called with empty dedup list
        deps = mock_agent.run.call_args.kwargs["deps"]
        assert deps.existing_entity_names == []
