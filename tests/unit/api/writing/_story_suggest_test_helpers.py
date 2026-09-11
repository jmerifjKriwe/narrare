"""Shared test helpers for StorySuggestService tests (RULE-04 split).

Provides fakes and fixtures used by ``test_story_suggest_service.py``
(Mode 1 behavioural + SSE + error handling).

Mirrors the ``_character_arc_test_helpers.py`` pattern (ADR-054 precedent).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare.writing.schemas_story_suggest import StorySuggestRequest
from narrare_core.agents.story_suggest_types import (
    StorySuggestion,
    StorySuggestionType,
    StorySuggestOutput,
)
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare.writing.story_suggest_service import StorySuggestService
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.intents import LLMIntent

# ---------------------------------------------------------------------------
# Fakes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model.

    ``prepare`` mirrors the real single assembly point (Task 4/6c):
    exactly one ``get_model`` resolution plus a canned sentinel settings
    dict, so pass-through wiring stays assertable.
    """

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))
        self.prepare_calls: list[dict[str, object]] = []

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        model = await self.get_model(config, api_key=api_key, base_url=base_url)
        prepared = PreparedModelCall(
            model=model,
            model_settings={"max_tokens": 12_345},
            usage_limits=usage_limits,
        )
        self.prepare_calls.append({"config": config, "intent": intent, "prepared": prepared})
        return prepared


class FakeComposer:
    """Fake PromptComposer for DI wiring.

    The service routes through ``compose_invocation`` (which calls
    ``composer.build`` internally), so this fake only needs to exist for DI
    wiring — its ``build`` is never reached when ``compose_invocation`` is
    patched. Kept as a real object (not a bare MagicMock) so the service's
    ``composer is None`` guard is satisfied.
    """

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="COMPOSED-STORY-SUGGEST-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The service only reads ``invocation.composed_prompt`` (Mode 1 invariant),
    so a lightweight class with that attribute is sufficient and avoids
    constructing the full ``prepared``/``finalized`` pipeline objects.
    """

    def __init__(self, system: str = "COMPOSED-STORY-SUGGEST-SYSTEM", user: str = "") -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(system=system, user=user)


def make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel with the attributes the service reads."""
    from narrare.novels.models import Novel

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "Fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
        "story_structure": overrides.get("story_structure", "three_act"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=Novel)
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def make_agent_output() -> StorySuggestOutput:
    """Build a fake StorySuggestAgent.run result."""
    return StorySuggestOutput(
        suggestions=[
            StorySuggestion(
                type=StorySuggestionType.PLOT_DEVELOPMENT,
                title="The Hidden Heir",
                description="A long-lost heir emerges from the shadows.",
                connection="Ties to the prophecy thread from chapter 3.",
            ),
            StorySuggestion(
                type=StorySuggestionType.CHARACTER_MOMENT,
                title="Lyra's Doubt",
                description="Lyra questions her loyalty to the rebellion.",
                connection="Builds on her conversation with Kael in chapter 5.",
            ),
        ]
    )


def make_request(**overrides: object) -> StorySuggestRequest:
    """Build a StorySuggestRequest with sensible defaults."""
    defaults: dict[str, object] = {
        "novel_id": overrides.get("novel_id", uuid.uuid4()),
        "chapter_id": overrides.get("chapter_id"),
        "author_instructions": overrides.get("author_instructions"),
    }
    return StorySuggestRequest(**defaults)  # type: ignore[arg-type]


def make_service(
    composer: FakeComposer,
    config: ResolvedModelConfig,
) -> StorySuggestService:
    """Build a StorySuggestService wired for Mode 1 prompt resolution."""
    from narrare.writing.story_suggest_service import StorySuggestService

    novel_repo = AsyncMock()
    return StorySuggestService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_config=config,
        composer=composer,  # type: ignore[arg-type]
    )
