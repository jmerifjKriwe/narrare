"""Shared helpers for the ``ModelRegistry.prepare()`` wiring tests (Task 6b-2).

RULE-04 split: ``test_planning_prepare_wiring.py`` sat exactly at the
400-line test hard limit, and the ADR-086 L20 slice's mechanical ctor
migration (``model_config``/``api_key``/``base_url`` → ``StaticModelResolution``)
crossed it — the size gate prescribed modularization. The recording
registry and the shared fixtures/assertion helper move here; the test
files keep only their site-specific fakes:

- ``test_planning_prepare_wiring.py`` — the three timeline sites,
- ``test_character_arc_prepare_wiring.py`` — the character-arc site.

Mirrors the ``_character_arc_test_helpers.py`` / ``_timeline_extraction_test_helpers.py``
convention.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts import PromptComposer

USER_KEY = "sk-user-key"
USER_BASE_URL = "https://user.example/v1"


def user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def static_resolution(config: ResolvedModelConfig | None = None) -> StaticModelResolution:
    """A ``StaticModelResolution`` over the canned user triple — fixture shim.

    The ADR-086 lazy-migration ctor shape: the resolved triple the eager
    factories used to accept as ``model_config``/``api_key``/``base_url``
    params now arrives pre-resolved (ADR-086 regression contract #4 —
    outcomes unchanged). Pass ``config`` explicitly when the test asserts
    identity (``is``) against the config reaching ``prepare``.
    """
    return StaticModelResolution(
        ResolvedModel(
            config=config or user_config(),
            api_key=USER_KEY,
            base_url=USER_BASE_URL,
            source="unit-test",
        )
    )


class RecordingPrepareRegistry:
    """Fake ModelRegistry mirroring the Task-6b recording fake.

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
    """Fake PromptComposer returning simple prompts."""

    async def build(self, intent: object, context: object) -> ComposedPrompt:
        return ComposedPrompt(system="System prompt.", user="User prompt.")


class ComposedInvocation:
    """Stand-in for ``ComposedInvocation`` (Mode 1).

    The services only read ``invocation.composed_prompt`` (Mode 1
    invariant), so a lightweight attribute carrier is sufficient.
    """

    def __init__(self) -> None:
        self.composed_prompt: ComposedPrompt = ComposedPrompt(
            system="System prompt.", user="User prompt."
        )


def novel() -> MagicMock:
    """Mock novel carrying the real string values the services read."""
    return MagicMock(
        spec=["title", "genre", "writing_language"],
        title="Test Novel",
        genre="Fantasy",
        writing_language="en",
    )


def assert_prepare_wiring(
    registry: RecordingPrepareRegistry,
    config: ResolvedModelConfig,
    *,
    mock_agent_cls: MagicMock,
    intent: LLMIntent,
    api_key: str | None,
    base_url: str | None,
) -> None:
    """Assert the full Task-6a wiring contract for one agent invocation."""
    assert len(registry.prepare_calls) == 1
    call = registry.prepare_calls[0]
    assert call["config"] is config
    assert call["intent"] is intent
    assert call["api_key"] == api_key
    assert call["base_url"] == base_url
    # One prepare() → exactly one model resolution (no duplicate).
    registry.get_model.assert_awaited_once()
    # The coherent triple reaches the agent boundary, and the agent ran.
    prepared = call["prepared"]
    assert isinstance(prepared, PreparedModelCall)
    assert mock_agent_cls.call_args.kwargs["model"] is prepared.model
    run_kwargs = mock_agent_cls.return_value.run.call_args.kwargs
    assert run_kwargs["model_settings"] is prepared.model_settings
    assert run_kwargs["usage_limits"] is prepared.usage_limits
    # Task 3 follow-up: the ADR-045 resolver is wired — non-None UsageLimits.
    assert prepared.usage_limits is not None
    assert mock_agent_cls.return_value.run.await_count == 1


def as_model_registry(registry_obj: RecordingPrepareRegistry) -> ModelRegistry:
    """Cast helper for the shared RecordingPrepareRegistry (DI-wiring only)."""
    return cast("ModelRegistry", registry_obj)


def novel_repo_with(novel_obj: MagicMock) -> NovelRepository:
    """An AsyncMock NovelRepository returning the given novel (cast helper)."""
    return cast("NovelRepository", AsyncMock(get_by_id=AsyncMock(return_value=novel_obj)))


def composer() -> PromptComposer:
    """Cast helper for the shared FakeComposer (DI-wiring only)."""
    return cast("PromptComposer", FakeComposer())
