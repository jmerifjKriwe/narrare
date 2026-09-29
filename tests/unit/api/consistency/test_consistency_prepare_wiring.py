"""Task 6b wiring tests — consistency domain resolves via ModelRegistry.prepare().

Pins the Task-6a structural contract for the three consistency call
sites — each resolves the model via the SINGLE assembly point
(``ModelRegistry.prepare``, Task 4) and forwards the coherent
``(model, model_settings, usage_limits)`` triple to ``agent.run``:

- ``ConsistencyOrchestrator._run_fact_extraction`` (FACT_EXTRACT)
- ``orchestrator_helpers.run_consistency_stage`` (CONSISTENCY)
- ``legacy_check_runner.run_legacy_check`` (CONSISTENCY)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the sites resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied
to these consistency paths. The capability intent is a static property
of each site — the same values the user-routing factories (Task 3)
resolve for the two consistency resolutions (FACT_EXTRACT + CONSISTENCY).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.agents.consistency_types import ConsistencyCheckType, ConsistencyDeps
from narrare_core.agents.fact_extractor_types import FactExtractorOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


class _RecordingPrepareRegistry:
    """Fake ModelRegistry mirroring the Task-6a recording fakes.

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


class _FakeComposer:
    """Fake PromptComposer returning simple prompts."""

    async def build(self, intent: object, context: object) -> ComposedPrompt:
        return ComposedPrompt(system="System prompt.", user="User prompt.")


def _deps() -> ConsistencyDeps:
    chapter_id = str(uuid4())
    return ConsistencyDeps(
        language="en",
        novel_id=str(uuid4()),
        chapter_texts={chapter_id: "Anna walked through the forest."},
        kb_entity_summaries=[],
        timeline_events=[],
        check_types=[ConsistencyCheckType.CHARACTER],
    )


def _fact_output() -> FactExtractorOutput:
    return FactExtractorOutput(facts=[], assessment_summary="")


def _assert_prepare_wiring(
    registry: _RecordingPrepareRegistry,
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
    # Value equality: the orchestrator composes the override config
    # (dataclasses.replace at first use), so identity does not hold for
    # the staged sites — the legacy/runner sites pass the same object.
    assert call["config"] == config
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
    assert mock_agent_cls.return_value.run.await_count == 1


class TestFactExtractionStagePrepareWiring:
    """Stage 1 (FactExtractorAgent) resolves via prepare(FACT_EXTRACT)."""

    async def test_fact_extraction_resolves_via_prepare_with_fact_extract_intent(self) -> None:
        from dataclasses import replace

        from narrare._app.dependencies_services import StaticModelResolution
        from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator
        from narrare_core.llm.model_routing import ResolvedModel

        fact_resolved = ResolvedModel(
            config=_user_config(),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
            source="unit-test",
        )
        registry = _RecordingPrepareRegistry()
        orchestrator = ConsistencyOrchestrator(
            registry=cast("ModelRegistry", registry),
            # ADR-086 L13: the orchestrator consumes ModelResolution
            # seams and composes the 0.2/0.3 overrides at first use.
            fact_extractor_resolution=StaticModelResolution(fact_resolved),
            consistency_resolution=StaticModelResolution(fact_resolved),
            composer=cast("PromptComposer", _FakeComposer()),
        )
        agent = AsyncMock(run=AsyncMock(return_value=_fact_output()))

        with patch(
            "narrare_core.agents.fact_extractor_agent.FactExtractorAgent", return_value=agent
        ) as MockAgent:
            await orchestrator._run_fact_extraction(
                deps=_deps(),
                kb_summaries=[],
                timeline_envelopes=[],
                language="en",
                configs=await orchestrator.ensure_resolved(),
            )

        _assert_prepare_wiring(
            registry,
            replace(_user_config(), temperature=0.2),
            mock_agent_cls=MockAgent,
            intent=LLMIntent.FACT_EXTRACT,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )


class TestStagedConsistencyStagePrepareWiring:
    """Stage 2 (staged ConsistencyAgent) resolves via prepare(CONSISTENCY)."""

    async def test_consistency_stage_resolves_via_prepare_with_consistency_intent(self) -> None:
        from narrare.consistency.orchestrator_helpers import run_consistency_stage

        consistency_config = _user_config()
        registry = _RecordingPrepareRegistry()
        agent = AsyncMock(
            run=AsyncMock(
                return_value=MagicMock(
                    spec=["issues", "checked_types", "overall_assessment"],
                    issues=[],
                    checked_types=[ConsistencyCheckType.CHARACTER],
                    overall_assessment="No issues.",
                )
            )
        )

        with patch(
            "narrare_core.agents.consistency_agent.ConsistencyAgent", return_value=agent
        ) as MockAgent:
            await run_consistency_stage(
                registry=cast("ModelRegistry", registry),
                consistency_config=consistency_config,
                composer=cast("PromptComposer", _FakeComposer()),
                novel_id=uuid4(),
                deps=_deps(),
                kb_summaries=[],
                timeline_envelopes=[],
                language="en",
                max_chapter_tokens=2000,
                fact_output=_fact_output(),
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        _assert_prepare_wiring(
            registry,
            consistency_config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.CONSISTENCY,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )


class TestLegacyCheckPrepareWiring:
    """Legacy single-pass ConsistencyAgent resolves via prepare(CONSISTENCY)."""

    async def test_legacy_check_resolves_via_prepare_with_consistency_intent(self) -> None:
        from narrare.consistency.checker_context import CheckContext
        from narrare.consistency.legacy_check_runner import run_legacy_check

        consistency_config = _user_config()
        registry = _RecordingPrepareRegistry()
        agent = AsyncMock(
            run=AsyncMock(
                return_value=MagicMock(
                    spec=["issues", "checked_types", "overall_assessment"],
                    issues=[],
                    checked_types=[ConsistencyCheckType.CHARACTER],
                    overall_assessment="No issues.",
                )
            )
        )
        context = CheckContext(
            deps=_deps(),
            kb_summaries=[],
            timeline_envelopes=[],
            resolved_ids=[],
            language="en",
            max_chapter_tokens=2000,
            rule_issues=[],
        )

        with patch(
            "narrare.consistency.legacy_check_runner.ConsistencyAgent", return_value=agent
        ) as MockAgent:
            await run_legacy_check(
                registry=cast("ModelRegistry", registry),
                config=consistency_config,
                composer=cast("PromptComposer", _FakeComposer()),
                novel_id=uuid4(),
                context=context,
                api_key=_USER_KEY,
                base_url=_USER_BASE_URL,
            )

        _assert_prepare_wiring(
            registry,
            consistency_config,
            mock_agent_cls=MockAgent,
            intent=LLMIntent.CONSISTENCY,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
