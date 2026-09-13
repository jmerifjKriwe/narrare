"""Shared test helpers for CoreferenceService tests (RULE-04 split).

Provides fakes and fixtures used by
``test_coreference_service.py`` (Mode 1 behavioural + RULE-11).

Mirrors the ``_character_arc_test_helpers.py`` pattern (ADR-054 precedent).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.agents.coreference_types import CoreferenceOutput
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from pydantic_ai.usage import UsageLimits

    from narrare._app.dependencies_services import ModelResolution
    from narrare.analysis.coreference_service import CoreferenceService
    from narrare.analysis.schemas_coreference import CoreferenceStreamEvent
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare_core.llm.intents import LLMIntent

# ---------------------------------------------------------------------------
# Fakes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model.

    ``prepare`` mirrors the real single assembly point (Task 4): exactly
    one ``get_model`` resolution, a canned sentinel ``model_settings``
    (so pass-through to ``agent.run`` is assertable), and the
    ``usage_limits`` pass-through. Calls are recorded in
    ``prepare_calls`` for wiring assertions.
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
        self.prepare_calls.append(
            {
                "config": config,
                "intent": intent,
                "usage_limits": usage_limits,
                "api_key": api_key,
                "base_url": base_url,
                "prepared": prepared,
            }
        )
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
            return_value=ComposedPrompt(system="COMPOSED-COREFERENCE-SYSTEM", user="")
        )


class FakeComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The service only reads ``invocation.composed_prompt`` (Mode 1
    invariant), so a lightweight class with that attribute is sufficient
    and avoids constructing the full ``prepared``/``finalized`` pipeline
    objects.
    """

    def __init__(self, system: str = "COMPOSED-COREFERENCE-SYSTEM", user: str = "") -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(system=system, user=user)


def make_chapter(**overrides: object) -> MagicMock:
    """Create a mock chapter with the attributes the service reads."""
    from narrare.chapters.models import Chapter

    novel_id = overrides.get("novel_id", uuid.uuid4())
    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "novel_id": novel_id,
        "title": overrides.get("title", "Chapter 1"),
        "content": overrides.get("content", "Alice looked at Bob. She smiled."),
    }
    defaults.update(overrides)
    chapter = MagicMock(spec=Chapter)
    for k, v in defaults.items():
        setattr(chapter, k, v)
    return chapter


def make_novel(**overrides: object) -> MagicMock:
    """Create a mock novel with the attributes the service reads."""
    from narrare.novels.models import Novel

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "title": overrides.get("title", "Test Novel"),
        "genre": overrides.get("genre", "Fantasy"),
        "writing_language": overrides.get("writing_language", "en"),
    }
    defaults.update(overrides)
    novel = MagicMock(spec=Novel)
    for k, v in defaults.items():
        setattr(novel, k, v)
    return novel


def make_kb_entry(**overrides: object) -> MagicMock:
    """Create a mock KB entry with the attributes the provider reads.

    Used to seed the canonical ``KBContextProvider`` (ADR-067): the
    provider's ``kb_entry_to_kb_entity`` mapper reads ``id`` /
    ``entity_type`` / ``name`` / ``body`` plus the provenance fields
    (``metadata_`` / ``status`` / ``source`` / ``review_status`` /
    ``updated_at``) that ``format_entities`` may annotate. Defaults to a
    ``character`` entity.
    """
    from datetime import UTC, datetime

    from narrare.kb.models import KBEntry

    defaults: dict[str, object] = {
        "id": overrides.get("id", uuid.uuid4()),
        "novel_id": overrides.get("novel_id", uuid.uuid4()),
        "entity_type": overrides.get("entity_type", "character"),
        "name": overrides.get("name", "Unknown"),
        "body": overrides.get("body", ""),
        "metadata_": overrides.get("metadata_", {}),
        "status": overrides.get("status", "accepted"),
        "source": overrides.get("source", "manual"),
        "review_status": overrides.get("review_status", "approved"),
        "updated_at": overrides.get("updated_at", datetime.now(UTC)),
    }
    defaults.update(overrides)
    entry = MagicMock(spec=KBEntry)
    for k, v in defaults.items():
        setattr(entry, k, v)
    return entry


def make_agent_output() -> CoreferenceOutput:
    """Build a fake CoreferenceAgent.run result."""
    return CoreferenceOutput(
        resolutions=[],
        character_mentions=[],
        clarity_score=82.0,
        summary="Most pronouns resolve clearly to Alice.",
    )


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches.

    Exposes the service-level lazy seam (ADR-086): the service must call
    ``resolve()`` exactly once (first use), never at construction.
    """

    def __init__(self, model: ResolvedModel | None = None) -> None:
        self._model = model if model is not None else _resolved_model()
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._model


def _resolved_model(config: ResolvedModelConfig | None = None) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config or ResolvedModelConfig(provider_name="test", model_id="test-model"),
        source="unit-test",
    )


def make_service(
    composer: FakeComposer,
    config: ResolvedModelConfig,
    kb_context_provider: KBContextProviderProtocol | None = None,
    *,
    model_resolution: ModelResolution | None = None,
) -> CoreferenceService:
    """Build a CoreferenceService wired for Mode 1 prompt resolution.

    Args:
        composer: Fake PromptComposer for DI wiring.
        config: Fake model config (wrapped in a ``StaticModelResolution``
            — ADR-086 unit-test harness).
        kb_context_provider: Optional canonical KB-context provider
            (ADR-067) for the ``kb_characters`` / ``kb_locations`` /
            ``kb_factions`` / ``kb_relationships`` prompt variables. When
            ``None`` (default), the service exercises the graceful
            degradation path (``KBContextBundle.empty()`` → every kb_*
            slot is ``""``) — this preserves backward compatibility with
            pre-KB-wiring tests.
        model_resolution: Optional resolution override (e.g.
            ``_CountingResolution`` for lazy-semantics tests); defaults
            to the static resolution around ``config``.
    """
    from narrare.analysis.coreference_service import CoreferenceService

    novel_repo = AsyncMock()
    chapter_repo = AsyncMock()
    return CoreferenceService(
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
        model_resolution=model_resolution or StaticModelResolution(_resolved_model(config)),
        composer=composer,  # type: ignore[arg-type]
        kb_context_provider=kb_context_provider,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Shared async-generator + patch utilities (used across the RULE-04 split)
# ---------------------------------------------------------------------------


async def consume(
    stream: AsyncIterator[CoreferenceStreamEvent],
) -> list[CoreferenceStreamEvent]:
    """Collect all events from the service async generator."""
    return [event async for event in stream]


@contextmanager
def patch_mode1(
    system: str = "COMPOSED-COREFERENCE-SYSTEM", user: str = ""
) -> Iterator[tuple[MagicMock, MagicMock, AsyncMock]]:
    """Patch CoreferenceAgent, CoreferenceDeps, and compose_invocation (Mode 1).

    Yields ``(MockAgent, MockDeps, mock_compose)``. The ``MockAgent``
    constructor must be wired to a fake ``run`` by each caller.
    """
    with (
        patch("narrare_core.agents.coreference_agent.CoreferenceAgent") as MockAgent,
        patch("narrare_core.agents.coreference_agent.CoreferenceDeps") as MockDeps,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=FakeComposedInvocation(system=system, user=user)),
        ) as mock_compose,
    ):
        yield MockAgent, MockDeps, mock_compose
