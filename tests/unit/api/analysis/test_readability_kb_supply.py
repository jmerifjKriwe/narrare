"""N12 regression: the readability AI phase must actually RUN.

Audit N12: the readability template requires the four ``kb_*`` slots, but
``ReadabilityService`` composed with no ``extra`` — ``composer.build``
raised ``PromptVariableError: Missing required prompt variable
'kb_characters' in analysis/en/readability`` on EVERY call (verified
in-tree 2026-10-18), the service's graceful-degradation ``except``
swallowed it, and the UI claimed "No problematic sentences detected!".
The fix mirrors the landed B07 POV kb-supply (kb_context_provider +
extra=kb_vars); ``kb_context_provider=None`` degrades to EMPTY slots,
which compose successfully.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare.analysis.services.readability_service import ReadabilityService
from narrare.kb._context_provider import KBContextProvider
from narrare.kb.models import KBEntry
from narrare_core.agents.readability_types import ReadabilityAgentOutput
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from tests.fakes import FakeChapterRepository, FakeModelRegistry, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare.kb.contracts import KBRepositoryProtocol

_CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model")

_CHAPTER_TEXT = (
    "Elara waited by the gate. The bells rang twice, and she counted "
    "them the way her mother had taught her, waiting for the third."
)


class _StubAgent:
    """ReadabilityAgent stand-in: records construction + the composed prompt."""

    def __init__(self, *, model: object, system_prompt: str | None = None) -> None:
        self.model = model
        self.system_prompt = system_prompt


def _stub_readability_agent(
    monkeypatch: pytest.MonkeyPatch,
    agent_run: Callable[..., Awaitable[object]],
) -> list[_StubAgent]:
    """Patch ``ReadabilityAgent`` at its call-time import site.

    ``_prepare_agent`` imports the module attribute at call time from
    ``narrare_core.agents.readability_agent``, so patching the attribute
    intercepts construction while the REAL registry ``prepare`` path runs.
    Returns the list of constructed instances (the N12 pin: the AI phase
    was REACHED — compose succeeded before the agent was ever built).
    """
    import narrare_core.agents.readability_agent as ra_module

    instances: list[_StubAgent] = []

    class _Agent(_StubAgent):
        def __init__(self, *, model: object, system_prompt: str | None = None) -> None:
            super().__init__(model=model, system_prompt=system_prompt)
            instances.append(self)

        async def run(self, **kwargs: object) -> object:
            return await agent_run(**kwargs)

    monkeypatch.setattr(ra_module, "ReadabilityAgent", _Agent)
    return instances


def _kb_entry(entity_type: str, name: str, body: str) -> MagicMock:
    entry = MagicMock(spec=KBEntry)
    entry.entity_type = entity_type
    entry.name = name
    entry.body = body
    return entry


def _provider_with(entries: list[MagicMock]) -> KBContextProvider:
    """Real KBContextProvider over a faked KB repo (B07 test pattern)."""
    repo = AsyncMock()
    repo.list_entries.return_value = (entries, len(entries))
    return KBContextProvider(
        kb_repo=cast("KBRepositoryProtocol", repo),
        relationship_repo=None,
    )


def _build_service(
    monkeypatch: pytest.MonkeyPatch,
    agent_run: Callable[..., Awaitable[object]],
    *,
    kb_context_provider: KBContextProvider | None = None,
) -> tuple[ReadabilityService, list[_StubAgent], Any, Any]:
    """ReadabilityService on the REAL composer + registry fakes for the rest.

    Returns ``(service, agent_instances, novel, chapter)`` — the seeded
    novel/chapter the tests must analyze (the repo-backed fakes are
    keyed to these ids).
    """
    instances = _stub_readability_agent(monkeypatch, agent_run)
    novel = make_novel(writing_language="en")
    ch = make_chapter(novel_id=novel.id, content=_CHAPTER_TEXT)
    nr, cr = FakeNovelRepository(), FakeChapterRepository()
    seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
    service = ReadabilityService(
        chapter_repo=cr,
        novel_repo=nr,
        model_registry=FakeModelRegistry(),
        # ADR-086: unit tests pin the resolved config via StaticModelResolution.
        model_resolution=StaticModelResolution(ResolvedModel(config=_CONFIG)),
        composer=PromptComposer(PromptRegistry()),
        kb_context_provider=kb_context_provider,
    )
    return service, instances, novel, ch


class TestReadabilityKBSupply:
    @pytest.mark.asyncio
    async def test_ai_phase_composes_and_runs_the_agent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RED pre-fix: the compose failed before the agent was ever built.

        ``PromptVariableError`` → ``AnalysisError`` → swallowed by the
        graceful-degradation ``except`` → metrics-only result, zero agent
        instances. Post-fix: empty kb slots (no provider) compose fine and
        the agent runs with the governed template as system prompt.
        """

        async def agent_run(**kwargs: object) -> ReadabilityAgentOutput:
            return ReadabilityAgentOutput(problematic_sentences=[], overall_assessment="ok")

        service, instances, novel, ch = _build_service(monkeypatch, agent_run)

        results = await service.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, language="en"
        )

        assert len(results) == 1
        assert results[0].metrics.flesch_reading_ease is not None
        # The N12 pin: the AI phase was REACHED (compose succeeded).
        assert len(instances) == 1
        assert instances[0].system_prompt  # the governed template rendered

    @pytest.mark.asyncio
    async def test_provider_supplies_kb_names_into_the_system_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The fix's core: kb vars flow through ``extra=`` into the prompt."""

        async def agent_run(**kwargs: object) -> ReadabilityAgentOutput:
            return ReadabilityAgentOutput(problematic_sentences=[], overall_assessment="ok")

        provider = _provider_with(
            [_kb_entry("character", "Kaelith", "Storm-born warden of the gate.")]
        )
        service, instances, novel, ch = _build_service(
            monkeypatch, agent_run, kb_context_provider=provider
        )

        await service.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, language="en"
        )

        assert len(instances) == 1
        system = instances[0].system_prompt or ""
        assert "Kaelith" in system, "kb_characters must flow into the readability system prompt"

    @pytest.mark.asyncio
    async def test_agent_failure_degrades_to_deterministic_metrics(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The RULE-11 seam stays: agent failure → 200-shape, metrics only."""

        async def agent_run(**kwargs: object) -> ReadabilityAgentOutput:
            raise RuntimeError("agent down (E04-class failure)")

        service, instances, novel, ch = _build_service(monkeypatch, agent_run)

        results = await service.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, language="en"
        )

        assert len(instances) == 1  # the agent was reached, then failed
        assert len(results) == 1
        assert results[0].metrics.sentence_count >= 1
        assert results[0].sentence_analyses == []
