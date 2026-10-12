"""Audit B07 regression — POV prompt compose receives KB context variables.

``analysis/en/pov/system.md`` references {{kb_characters}} / {{kb_locations}}
/ {{kb_factions}} / {{kb_relationships}}, but POVService composed with a
bare PromptContext — the variable engine raised PromptVariableError and the
endpoint answered 500. The fix follows the coreference SSOT supply: the
canonical KBContextProvider feeds all four slots (ADR-067), degrading to
empty strings when the KB is empty (RULE-11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare.analysis.services.pov_service import POVService
from narrare.kb._context_provider import KBContextProvider
from narrare.kb.models import KBEntry
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from tests.fakes import FakeChapterRepository, FakeModelRegistry, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos
from tests.unit.api.analysis._fakes import FakePOVAgent

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol

_CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model")


def _pov_output() -> Any:
    from narrare_core.agents.pov_types import POVDetectedScene, POVDetectionOutput

    return POVDetectionOutput(
        scenes=[POVDetectedScene(scene_index=0, pov_character="Alice", confidence=0.9)],
        issues=[],
        pov_distribution={"Alice": 1.0},
        switch_count=0,
        analysis_type="third_limited",
    )


def _kb_entry(entity_type: str, name: str, body: str) -> MagicMock:
    entry = MagicMock(spec=KBEntry)
    entry.entity_type = entity_type
    entry.name = name
    entry.body = body
    return entry


def _provider_with(entries: list[MagicMock]) -> KBContextProvider:
    """Real KBContextProvider over a faked KB repo (coreference-test pattern)."""
    repo = AsyncMock()
    repo.list_entries.return_value = (entries, len(entries))
    return KBContextProvider(
        kb_repo=cast("KBRepositoryProtocol", repo),
        relationship_repo=None,
    )


def _prepared() -> PreparedModelCall:
    return PreparedModelCall(model=MagicMock(spec=object), model_settings=None, usage_limits=None)


class TestPOVKBContextSupply:
    @pytest.mark.asyncio
    async def test_analyze_composes_pov_prompt_with_kb_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Real registry + real composer: analyze completes and the composed
        system prompt carries the KB character names (B07 red: AnalysisError)."""
        novel = make_novel(writing_language="en")
        ch = make_chapter(novel_id=novel.id, content="Alice saw the light and smiled.")
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)

        provider = _provider_with(
            [_kb_entry("character", "Alice", "A brave hero who fears rivers.")]
        )
        captured: dict[str, str | None] = {}
        agent = FakePOVAgent(output=_pov_output())

        svc = POVService(
            chapter_repo=cr,
            novel_repo=nr,
            model_registry=FakeModelRegistry(),
            model_resolution=StaticModelResolution(ResolvedModel(config=_CONFIG)),
            composer=PromptComposer(PromptRegistry()),
            kb_context_provider=provider,
        )

        async def _prepare_agent(
            system_prompt: str | None = None,
            resolved_model: ResolvedModel | None = None,
        ) -> tuple[FakePOVAgent, PreparedModelCall]:
            captured["system"] = system_prompt
            return agent, _prepared()

        # MonkeyPatch.setattr (not bare assignment) — pyright-strict safe
        # without a RULE-23 suppression (per-file baseline is 0).
        monkeypatch.setattr(svc, "_prepare_agent", _prepare_agent)

        result = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)

        assert result.analysis_type == "third_limited"
        system = captured["system"] or ""
        assert "Alice" in system, "kb_characters must flow into the pov system prompt"

    @pytest.mark.asyncio
    async def test_analyze_without_provider_degrades_to_empty_slots(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No provider wired → compose still succeeds (empty kb slots, RULE-11)."""
        novel = make_novel(writing_language="en")
        ch = make_chapter(novel_id=novel.id, content="Alice saw the light.")
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)

        agent = FakePOVAgent(output=_pov_output())

        async def _prepare_agent_without_capture(
            system_prompt: str | None = None,
            resolved_model: ResolvedModel | None = None,
        ) -> tuple[FakePOVAgent, PreparedModelCall]:
            return agent, _prepared()

        svc = POVService(
            chapter_repo=cr,
            novel_repo=nr,
            model_registry=FakeModelRegistry(),
            model_resolution=StaticModelResolution(ResolvedModel(config=_CONFIG)),
            composer=PromptComposer(PromptRegistry()),
            kb_context_provider=None,
        )
        monkeypatch.setattr(svc, "_prepare_agent", _prepare_agent_without_capture)

        result = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert result.analysis_type == "third_limited"
