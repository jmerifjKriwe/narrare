"""Task 6c-2 wiring tests — remaining KB sites resolve via ModelRegistry.prepare().

Pins the Task-6a/6b structural contract for two of the three remaining
bare ``get_model`` + ``agent.run()`` KB call sites — each resolves the
model via the SINGLE assembly point (``ModelRegistry.prepare``, Task 4)
and forwards the coherent ``(model, model_settings, usage_limits)``
triple:

- ``KBImproveAnalyzer.analyze`` (KB_IMPROVE)
- ``KBMergeService.analyze_merge_candidates`` (KB_CONSISTENCY) — also
  pins the credential fix: the service accepted api_key/base_url but
  the bare ``get_model`` call dropped them (latent setup bug).

Worldbuilding (KB_WORLDBUILD) lives in the sibling
``test_kb_worldbuilding_prepare_wiring.py`` (RULE-04 split, shared
fakes in ``_kb_prepare_wiring_helpers.py``).

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the sites resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied
to these KB paths.

Out of scope (verified, already compliant): ``KBConsistencyAnalyzer``
routes through ``ModelRegistry.run(intent=...)`` which applies
``build_runtime_model_settings`` internally (gateway.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.llm.intents import LLMIntent
from tests.unit.api.kb._kb_prepare_wiring_helpers import (
    _USER_BASE_URL,
    _USER_KEY,
    _AssertWiring,
    _ComposedInvocation,
    _FakeComposer,
    _RecordingPrepareRegistry,
    _user_config,
)

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer


class TestImprovePrepareWiring:
    """KBImproveAgent resolves via prepare(KB_IMPROVE) with user credentials."""

    async def test_analyze_resolves_via_prepare_with_kb_improve_intent(self) -> None:
        from narrare.kb.improve_analyzer import KBImproveAnalyzer

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        wiring = _AssertWiring(registry, config)
        provider = MagicMock(spec=["fetch_world_context", "fetch_context", "fetch_entities"])
        provider.fetch_world_context = AsyncMock(return_value="")
        provider.fetch_entities = AsyncMock(return_value=[])
        analyzer = KBImproveAnalyzer(
            registry=cast("ModelRegistry", registry),
            config=config,
            kb_context_provider=cast("Any", provider),
            prompt_composer=cast("PromptComposer", _FakeComposer()),
            kb_repo=cast("KBRepository", MagicMock(spec=True, name="KBRepository")),
            rel_repo=cast("RelationshipRepository", MagicMock(spec=True, name="RelRepo")),
        )
        deps = MagicMock(spec=["entity_type", "entry_content"])
        deps.entity_type = "character"
        deps.entry_content = {"name": "Lyra"}
        output = MagicMock(spec=["suggestions", "overall_assessment", "completeness_score"])
        output.suggestions = []
        output.overall_assessment = "Solid entry."
        output.completeness_score = 0.9
        agent = AsyncMock(run=AsyncMock(return_value=output))

        with (
            patch.object(analyzer, "_build_deps", AsyncMock(return_value=deps)),
            patch("narrare.kb.improve_analyzer.KBImproveAgent", return_value=agent) as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_ComposedInvocation()),
            ),
        ):
            result = await analyzer.analyze(novel_id=uuid4(), entry_id=uuid4())

        call = wiring.call(0)
        assert call["intent"] is LLMIntent.KB_IMPROVE
        assert call["api_key"] is None
        assert call["base_url"] is None
        registry.get_model.assert_awaited_once()
        wiring.agent_assembly(MockAgent, call)
        assert result.overall_assessment == "Solid entry."


class TestMergePrepareWiring:
    """KBMergeAgent resolves via prepare(KB_CONSISTENCY) — and the user
    credentials that the old bare get_model call dropped now flow."""

    async def test_analyze_resolves_via_prepare_with_kb_consistency_intent(self) -> None:
        from narrare.kb.merge_service import KBMergeService
        from narrare.kb.schemas_merge import MergeRequest

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        wiring = _AssertWiring(registry, config)
        novel = MagicMock(
            spec=["title", "genre", "writing_language"],
            title="Test Novel",
            genre="fantasy",
            writing_language="en",
        )
        novel_repo = AsyncMock(get_by_id=AsyncMock(return_value=novel))
        service = KBMergeService(
            novel_repo=cast("Any", novel_repo),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            composer=cast("PromptComposer", _FakeComposer()),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        output = MagicMock(spec=["merge_decisions", "overall_notes"])
        output.merge_decisions = []
        output.overall_notes = "No merge candidates found."
        agent = AsyncMock(run=AsyncMock(return_value=output))
        request = MergeRequest(
            entity_type="character",
            candidate_pairs=[{"name_a": "Alice", "name_b": "Alis"}],
        )

        with (
            patch("narrare_core.agents.merge_agent.KBMergeAgent", return_value=agent) as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_ComposedInvocation()),
            ),
        ):
            result = await service.analyze_merge_candidates(
                novel_id=uuid4(),
                user_id=uuid4(),
                request=request,
            )

        call = wiring.call(0)
        assert call["intent"] is LLMIntent.KB_CONSISTENCY
        # Credential regression pin: the bare get_model previously DROPPED
        # the injected api_key/base_url; prepare() forwards them.
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        registry.get_model.assert_awaited_once()
        wiring.agent_assembly(MockAgent, call)
        assert result.overall_notes == "No merge candidates found."
