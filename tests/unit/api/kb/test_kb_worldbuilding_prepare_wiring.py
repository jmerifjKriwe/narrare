"""Task 6c-2 wiring tests — worldbuilding resolves via ModelRegistry.prepare().

Pins the Task-6a/6b structural contract for the WorldbuildingAnalyzer
phases (intent KB_WORLDBUILD, features ``kb_worldbuilding_phase1`` /
``kb_worldbuilding_phase2``): the model resolves via the SINGLE
assembly point (``ModelRegistry.prepare``, Task 4).

Phase-2 note: the core ``WorldbuildingAgent.run_phase2`` kwargs
pass-through landed in Task 1 of the pydantic-ai follow-ups plan; the
service-side wiring that forwards the full prepared triple into
``run_phase2`` landed in Task 2 (pinned in
``test_phase2_receives_prepared_triple`` below).

Shared fakes live in ``_kb_prepare_wiring_helpers.py`` (RULE-04 split
sibling of ``test_kb_prepare_wiring.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from tests.unit.api.kb._kb_prepare_wiring_helpers import (
    _USER_BASE_URL,
    _USER_KEY,
    _AssertWiring,
    _FakeComposer,
    _RecordingPrepareRegistry,
    _user_config,
)

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts import PromptComposer


class _FakeKBEntry:
    def __init__(self, *, entity_type: str = "character", name: str = "Test") -> None:
        self.id = uuid4()
        self.name = name
        self.entity_type = entity_type
        self.metadata_: dict[str, object] | None = None
        self.body = "Body text"
        self.tags: list[str] | None = None
        self.usage_count = 0


class _FakeKBRepo:
    def __init__(self, entries: list[_FakeKBEntry] | None = None) -> None:
        self._entries = entries or []

    async def list_entries(
        self,
        novel_id: object,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[_FakeKBEntry], int]:
        start = (page - 1) * page_size
        return self._entries[start : start + page_size], len(self._entries)

    async def get_by_id(self, entry_id: object) -> _FakeKBEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None


class _FakeRelRepo:
    async def get_adjacency_map(
        self, novel_id: object, entity_ids: set[object] | None = None
    ) -> dict[str, set[str]]:
        return {}

    async def list_for_entry(self, entry_id: object, direction: str | None = None) -> list[object]:
        return []


class _FakeCache:
    def __init__(self) -> None:
        self.last_set: tuple[str, str] | None = None

    async def get(self, novel_id: str, types_hash: str = "") -> str | None:
        return None

    async def set(self, novel_id: str, value: str, types_hash: str = "") -> None:
        self.last_set = (novel_id, value)


def _phase1_output(**overrides: Any) -> Any:
    from narrare_core.agents.worldbuilding_types import WorldbuildingPhase1Output

    defaults: dict[str, Any] = {
        "gaps": [],
        "connection_suggestions": [],
        "assessment": "OK",
        "worldbuilding_score": 0.5,
        "candidate_pairs_for_consistency": [],
    }
    defaults.update(overrides)
    return WorldbuildingPhase1Output(**defaults)


def _make_wb_analyzer(
    registry: _RecordingPrepareRegistry,
    config: Any,
) -> Any:
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer

    return WorldbuildingAnalyzer(
        kb_repo=cast("KBRepository", _FakeKBRepo([_FakeKBEntry()])),
        rel_repo=cast("RelationshipRepository", _FakeRelRepo()),
        cache=cast("WorldbuildingCache", _FakeCache()),
        registry=cast("ModelRegistry", registry),
        config=config,
        composer=cast("PromptComposer", _FakeComposer()),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )


class TestWorldbuildingPrepareWiring:
    """WorldbuildingAgent phases resolve via prepare(KB_WORLDBUILD)."""

    async def test_phase1_resolves_via_prepare_with_kb_worldbuild_intent(self) -> None:
        from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisRequest

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        wiring = _AssertWiring(registry, config)
        analyzer = _make_wb_analyzer(registry, config)
        agent = MagicMock(spec=["run_phase1", "run_phase2"])
        agent.run_phase1 = AsyncMock(return_value=_phase1_output(worldbuilding_score=0.75))
        agent.run_phase2 = AsyncMock()

        with patch(
            "narrare.kb.worldbuilding_analyzer.WorldbuildingAgent", return_value=agent
        ) as MockAgent:
            result = await analyzer.analyze(
                novel_id=uuid4(),
                request=WorldbuildingAnalysisRequest(refresh=True, include_consistency=False),
            )

        call = wiring.call(0)
        assert call["intent"] is LLMIntent.KB_WORLDBUILD
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL
        registry.get_model.assert_awaited_once()
        prepared = call["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        assert MockAgent.call_args.kwargs["model"] is prepared.model
        # Phase 1 forwards the full triple via the agent's **kwargs
        # pass-through (NarrareAgent.run).
        phase1_kwargs = agent.run_phase1.call_args.kwargs
        assert phase1_kwargs["model_settings"] is prepared.model_settings
        assert phase1_kwargs["usage_limits"] is prepared.usage_limits
        # Task 3 follow-up: the ADR-045 run-limit resolver is wired —
        # the pass-through value is a resolved, non-None UsageLimits.
        assert prepared.usage_limits is not None
        agent.run_phase2.assert_not_called()
        assert result.worldbuilding_score == 0.75

    async def test_phase2_receives_prepared_triple(self) -> None:
        """Phase 2 gets the full prepared triple (Task 2 wiring): the
        core ``run_phase2`` kwargs pass-through (Task 1) carries the
        settings/limits halves into the ephemeral phase-2 agent."""
        from narrare.kb.worldbuilding_contracts import WorldbuildingAnalysisRequest

        config = _user_config()
        registry = _RecordingPrepareRegistry()
        analyzer = _make_wb_analyzer(registry, config)
        agent = MagicMock(spec=["run_phase1", "run_phase2"])
        agent.run_phase1 = AsyncMock(
            return_value=_phase1_output(
                candidate_pairs_for_consistency=[(str(uuid4()), str(uuid4()))]
            )
        )
        phase2_output = MagicMock(spec=["issues"], issues=[])
        agent.run_phase2 = AsyncMock(return_value=phase2_output)

        with patch("narrare.kb.worldbuilding_analyzer.WorldbuildingAgent", return_value=agent):
            await analyzer.analyze(
                novel_id=uuid4(),
                request=WorldbuildingAnalysisRequest(refresh=True, include_consistency=True),
            )

        # Phase 2 performs its own prepare() resolution (one per phase).
        assert len(registry.prepare_calls) == 2
        second = registry.prepare_calls[1]
        assert second["intent"] is LLMIntent.KB_WORLDBUILD
        prepared = second["prepared"]
        assert isinstance(prepared, PreparedModelCall)
        # The full prepared triple (model + settings + limits) reaches
        # phase 2 (Task 2 service-side wiring).
        run_kwargs = agent.run_phase2.call_args.kwargs
        assert run_kwargs["model"] is prepared.model
        assert run_kwargs["model_settings"] is prepared.model_settings
        assert run_kwargs["usage_limits"] is prepared.usage_limits
