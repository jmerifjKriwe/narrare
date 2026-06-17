"""Prompt-Path-Compliance tests for WorldbuildingAnalyzer Phase 2 (CR-AUFG-02-05).

Regression tests enforcing ADR-046: Phase 2 must resolve its prompt through
``PromptComposer.build()`` (governed cascade + variable substitution), NOT
through ``PromptRegistry.resolve()`` directly, and must fail fast on a missing
route instead of falling back to an inline string.

Reference implementation: Phase 1 already uses ``self._composer.build()``.
Phase 2 is being retrofitted to match (see cr-02-prompt-path-retrofit.md).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic_ai.models import Model

from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
from narrare_core.agents.worldbuilding_types import WorldbuildingDeps
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.shared.errors import PromptError, PromptRouteNotConfiguredError

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeKBEntry:
    def __init__(self, *, entity_type: str = "character", name: str = "Test") -> None:
        self.id = uuid4()
        self.name = name
        self.entity_type = entity_type
        self.metadata_: dict[str, object] | None = {"role": "hero"}
        self.body = "A detailed body describing this entity."
        self.tags: list[str] | None = ["protagonist"]
        self.usage_count = 0


class FakeKBRepo:
    def __init__(self, entries: list[FakeKBEntry] | None = None) -> None:
        self._entries = entries or []

    async def get_by_id(self, entry_id: object) -> FakeKBEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None


class FakeRelRepo:
    async def get_adjacency_map(
        self, novel_id: object, entity_ids: set[object] | None = None
    ) -> dict[str, set[str]]:
        return {}

    async def list_for_entry(self, entry_id: object, direction: str | None = None) -> list[object]:
        return []


class FakeCache:
    async def get(self, novel_id: str, types_hash: str = "") -> str | None:
        return None

    async def set(self, novel_id: str, value: str, types_hash: str = "") -> None:
        pass


class SpyComposer:
    """Composer spy that records every ``build()`` invocation.

    Raises the configured error (if any) so tests can exercise the fail-fast
    path without involving the real cascade.
    """

    def __init__(self, *, raise_error: Exception | None = None) -> None:
        self.build_calls: list[tuple[Any, PromptContext, dict[str, Any]]] = []
        self._raise_error = raise_error

    async def build(
        self,
        intent: Any,
        context: PromptContext,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        self.build_calls.append((intent, context, {"user_prompt": user_prompt}))
        if self._raise_error is not None:
            raise self._raise_error
        return ComposedPrompt(
            system="spy phase2 system prompt",
            user=user_prompt or "spy phase2 user prompt",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analyzer(
    entries: list[FakeKBEntry],
    *,
    composer_raise: Exception | None = None,
) -> tuple[WorldbuildingAnalyzer, SpyComposer]:
    kb_repo = FakeKBRepo(entries)
    spy = SpyComposer(raise_error=composer_raise)
    registry = MagicMock(spec=ModelRegistry)
    registry.get_model = AsyncMock(return_value=MagicMock(spec=Model))
    config = MagicMock(spec=ResolvedModelConfig)
    analyzer = WorldbuildingAnalyzer(
        kb_repo=cast("KBRepository", kb_repo),
        rel_repo=cast("RelationshipRepository", FakeRelRepo()),
        cache=cast("WorldbuildingCache", FakeCache()),
        registry=registry,
        config=config,
        composer=cast("PromptComposer", spy),
    )
    return analyzer, spy


def _phase2_output() -> object:
    from narrare_core.agents.worldbuilding_types import (
        Phase2ConsistencyOutput,
        WorldbuildingPhase2Output,
    )

    return WorldbuildingPhase2Output(
        issues=[
            Phase2ConsistencyOutput(
                category="timeline",
                entity_ids=["a", "b"],
                entity_names=["A", "B"],
                description="Date mismatch.",
                contradiction="Born before parent.",
                severity="moderate",
                confidence=0.7,
            ),
        ],
        assessment="Mostly consistent.",
    )


# ---------------------------------------------------------------------------
# Tests: Phase 2 prompt path compliance (CR-AUFG-02-05)
# ---------------------------------------------------------------------------


class TestPhase2PromptPathCompliance:
    """ADR-046: Phase 2 must use PromptComposer.build(), not PromptRegistry.resolve()."""

    @pytest.mark.asyncio
    async def test_phase2_uses_prompt_composer_not_registry(self) -> None:
        """REGRESSION: Phase2 must call composer.build(), never registry.resolve().

        Before ADR-046: phase2 called ``PromptRegistry.resolve("kb",
        "worldbuilding/phase2")`` directly, bypassing the cascade.
        After ADR-046: phase2 uses ``PromptComposer.build()`` like phase1.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, spy = _make_analyzer([e1, e2])
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        # Composer.build MUST have been called exactly once for phase2.
        assert len(spy.build_calls) == 1, "Phase2 must resolve its prompt via composer.build()"
        intent, _ctx, _kwargs = spy.build_calls[0]
        assert intent == LLMIntent.KB_WORLDBUILD

    @pytest.mark.asyncio
    async def test_phase2_composer_called_with_phase2_mode(self) -> None:
        """Phase2 must request the governed 'worldbuilding/phase2' route.

        The route table allows {'worldbuilding/phase1', 'worldbuilding/phase2'}
        for KB_WORLDBUILD. Phase2 must select the phase2 template explicitly.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, spy = _make_analyzer([e1, e2])
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        assert len(spy.build_calls) == 1
        _intent, ctx, _kwargs = spy.build_calls[0]
        assert ctx.mode == "worldbuilding/phase2"

    @pytest.mark.asyncio
    async def test_phase2_context_carries_entity_data(self) -> None:
        """Template variables must be provisioned via PromptContext.extra.

        The phase2 template requires {{candidate_pairs}}, {{entity_details}},
        and {{existing_relationships}}. These must flow through the governed
        variable engine, not be assembled ad-hoc.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, spy = _make_analyzer([e1, e2])
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en", existing_relationships=[])

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        assert len(spy.build_calls) == 1
        _intent, ctx, _kwargs = spy.build_calls[0]
        # Required template variables present in extra (substituted by engine).
        assert "candidate_pairs" in ctx.extra
        assert "entity_details" in ctx.extra
        assert "existing_relationships" in ctx.extra
        # Provisioned values must be non-empty readable strings.
        assert ctx.extra["candidate_pairs"]
        assert ctx.extra["entity_details"]
        # Entity names must surface in the formatted details.
        assert "Alice" in ctx.extra["entity_details"]
        assert "Bob" in ctx.extra["entity_details"]

    @pytest.mark.asyncio
    async def test_phase2_composed_prompt_passed_to_agent(self) -> None:
        """The agent must receive the composed system prompt, not a fallback string."""
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, _spy = _make_analyzer([e1, e2])
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        run_phase2_kwargs = MockAgent.return_value.run_phase2.call_args.kwargs
        assert run_phase2_kwargs["system_prompt"] == "spy phase2 system prompt"

    @pytest.mark.asyncio
    async def test_phase2_no_inline_fallback(self) -> None:
        """REGRESSION: Missing prompt route must fail fast, not return inline fallback.

        Before ADR-046: ``except Exception: system_prompt = "Check entity pairs
        for worldbuilding contradictions."`` masked configuration failures.
        After ADR-046: a missing route raises a typed ``PromptError``.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        route_error = PromptRouteNotConfiguredError(
            LLMIntent.KB_WORLDBUILD.value,
            "Context mode 'worldbuilding/phase2' is not a governed route.",
        )
        analyzer, _spy = _make_analyzer([e1, e2], composer_raise=route_error)
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with (
            patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent,
            pytest.raises(PromptError),
        ):
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            await analyzer._run_phase2(deps, pairs, uuid4())

        # The agent must never run when prompt resolution fails.
        MockAgent.return_value.run_phase2.assert_not_called()

    @pytest.mark.asyncio
    async def test_phase2_no_prompt_registry_dependency(self) -> None:
        """The analyzer must not require a PromptRegistry to run phase2.

        After the retrofit, PromptRegistry is no longer injected; all prompt
        resolution flows through PromptComposer. Constructing the analyzer
        without a prompt_registry and running phase2 must succeed.
        """
        e1, e2 = FakeKBEntry(name="Alice"), FakeKBEntry(name="Bob")
        analyzer, _spy = _make_analyzer([e1, e2])
        # No prompt_registry attribute should exist on the instance.
        assert not hasattr(analyzer, "_prompt_registry")
        pairs = [(str(e1.id), str(e2.id))]
        deps = WorldbuildingDeps(language="en")

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent") as MockAgent:
            MockAgent.return_value.run_phase2 = AsyncMock(return_value=_phase2_output())
            result = await analyzer._run_phase2(deps, pairs, uuid4())

        assert len(result) == 1
        assert result[0].category.value == "timeline"
