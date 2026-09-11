"""Unit tests for POVService — access control, language, agent orchestration.

Uses Fake classes for all dependencies (no MagicMock).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare.analysis.services.pov_service import POVService
from narrare_core.agents.pov_types import POVDetectionOutput
from narrare_core.analysis.types import POVResult
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import NotFoundError
from tests.fakes import FakeChapterRepository, FakeModelRegistry, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos
from tests.unit.api.analysis._fakes import (
    FakeComposer,
    FakePOVAgent,
    SpyInvocationPipeline,
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIG = ResolvedModelConfig(provider_name="anthropic", model_id="test-model")


def _pov_output(**overrides: Any) -> POVDetectionOutput:
    data: dict[str, Any] = {
        "scenes": [{"scene_index": 0, "pov_character": "Alice", "confidence": 0.9}],
        "issues": [],
        "pov_distribution": {"Alice": 1.0},
        "switch_count": 0,
        "analysis_type": "third_limited",
    }
    data.update(overrides)
    return POVDetectionOutput(**data)


def _make_service(
    content: str = "Alice saw the light.",
    writing_language: str = "en",
    invocation_pipeline: InvocationPipeline | None = None,
    composer: FakeComposer | None = None,
) -> tuple[Any, Any, POVService]:
    novel = make_novel(writing_language=writing_language)
    ch = make_chapter(novel_id=novel.id, content=content)
    nr, cr = FakeNovelRepository(), FakeChapterRepository()
    seed_repos(novel, ch, novel_repo=nr, chapter_repo=cr)
    svc = POVService(
        chapter_repo=cr,
        novel_repo=nr,
        model_registry=FakeModelRegistry(),
        # ADR-086: unit tests pin the resolved config via StaticModelResolution.
        model_resolution=StaticModelResolution(ResolvedModel(config=_CONFIG)),
        composer=composer or FakeComposer(),
        invocation_pipeline=invocation_pipeline,
    )
    return novel, ch, svc


def _prepared() -> PreparedModelCall:
    """Canned coherent triple for injected-agent tests (Task 6a-2).

    The injected ``_prepare_agent`` replacement skips the real registry,
    so the run-pass-through (``model_settings`` / ``usage_limits``) is
    verified by the dedicated wiring suite
    (``test_analysis_service_prepare_wiring.py``) instead.
    """
    return PreparedModelCall(model=MagicMock(spec=object), model_settings=None, usage_limits=None)


def _inject(svc: POVService, agent: FakePOVAgent) -> None:
    async def _prepare_agent(
        system_prompt: str | None = None,
        resolved_model: ResolvedModel | None = None,
    ) -> tuple[FakePOVAgent, PreparedModelCall]:
        return agent, _prepared()

    svc._prepare_agent = _prepare_agent  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# A. analyze — happy path
# ---------------------------------------------------------------------------


class TestPOVAnalyzeHappyPath:
    @pytest.mark.asyncio
    async def test_returns_pov_result(self) -> None:
        novel, ch, svc = _make_service()
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        result = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert isinstance(result, POVResult)
        assert result.analysis_type == "third_limited"
        assert fake.run_called

    @pytest.mark.asyncio
    async def test_resolves_language_auto_from_novel(self) -> None:
        novel, ch, svc = _make_service(writing_language="de")
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, language="auto"
        )
        assert fake.last_deps.language == "de"

    @pytest.mark.asyncio
    async def test_language_override_not_auto(self) -> None:
        novel, ch, svc = _make_service(writing_language="de")
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        await svc.analyze(
            novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id, language="fr"
        )
        assert fake.last_deps.language == "fr"


# ---------------------------------------------------------------------------
# B. analyze — error cases
# ---------------------------------------------------------------------------


class TestPOVAnalyzeErrors:
    @pytest.mark.asyncio
    async def test_novel_not_found_raises(self) -> None:
        novel, ch, svc = _make_service()
        with pytest.raises(NotFoundError, match="Novel"):
            await svc.analyze(novel_id=uuid4(), chapter_ids=[ch.id], user_id=novel.user_id)

    @pytest.mark.asyncio
    async def test_chapter_not_found_raises(self) -> None:
        novel, _, svc = _make_service()
        with pytest.raises(NotFoundError, match="Chapter"):
            await svc.analyze(novel_id=novel.id, chapter_ids=[uuid4()], user_id=novel.user_id)

    @pytest.mark.asyncio
    async def test_agent_error_propagates(self) -> None:
        novel, ch, svc = _make_service()
        fake = FakePOVAgent(error=RuntimeError("LLM down"))
        _inject(svc, fake)
        with pytest.raises(RuntimeError, match="LLM down"):
            await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)


# ---------------------------------------------------------------------------
# C. analyze — empty text edge case
# ---------------------------------------------------------------------------


class TestPOVAnalyzeEmptyText:
    @pytest.mark.asyncio
    async def test_empty_chapter_returns_empty_result(self) -> None:
        novel, ch, svc = _make_service(content="")
        fake = FakePOVAgent()
        _inject(svc, fake)
        result = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert isinstance(result, POVResult)
        assert result.scenes == []
        assert not fake.run_called

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_empty_result(self) -> None:
        novel, ch, svc = _make_service(content="   \n\t  ")
        fake = FakePOVAgent()
        _inject(svc, fake)
        result = await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)
        assert result.scenes == []
        assert not fake.run_called


# ---------------------------------------------------------------------------
# D. Multiple chapters
# ---------------------------------------------------------------------------


class TestMultipleChapters:
    @pytest.mark.asyncio
    async def test_chapters_concatenated(self) -> None:
        novel = make_novel()
        ch1 = make_chapter(novel_id=novel.id, content="First scene.")
        ch2 = make_chapter(novel_id=novel.id, content="Second scene.")
        nr, cr = FakeNovelRepository(), FakeChapterRepository()
        seed_repos(novel, ch1, ch2, novel_repo=nr, chapter_repo=cr)
        svc = POVService(
            chapter_repo=cr,
            novel_repo=nr,
            model_registry=FakeModelRegistry(),
            model_resolution=StaticModelResolution(ResolvedModel(config=_CONFIG)),
            composer=FakeComposer(),
        )
        fake = FakePOVAgent(output=_pov_output())
        _inject(svc, fake)
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch1.id, ch2.id], user_id=novel.user_id)
        assert "First scene." in fake.last_deps.text
        assert "Second scene." in fake.last_deps.text


# ---------------------------------------------------------------------------
# E. Invocation composition — verifies compose_invocation (ADR-048 Mode 1)
# ---------------------------------------------------------------------------


class TestInvocationComposition:
    """Verify the service routes through compose_invocation (Mode 1, composer-driven)."""

    @pytest.mark.asyncio
    async def test_compose_invocation_called_with_pov_feature_id(self) -> None:
        """The pipeline prepare/finalize are invoked with feature_id analysis_pov."""
        spy = SpyInvocationPipeline()
        novel, ch, svc = _make_service(invocation_pipeline=spy)
        _inject(svc, FakePOVAgent(output=_pov_output()))
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)

        assert len(spy.prepare_calls) == 1
        assert spy.prepare_calls[0].feature_id == "analysis_pov"
        assert len(spy.finalize_calls) == 1
        assert spy.finalize_calls[0].feature_id == "analysis_pov"


# ---------------------------------------------------------------------------
# F. Mode 1 prompt composition — composer-driven system prompt (ADR-048)
# ---------------------------------------------------------------------------


class TestMode1PromptComposition:
    """Mode 1: the composer-built system prompt reaches the agent."""

    @pytest.mark.asyncio
    async def test_composed_system_prompt_passed_to_agent(self) -> None:
        """The composer-built system prompt is handed to the agent constructor."""
        composer = FakeComposer(system="POV-SYSTEM-PROMPT")
        novel, ch, svc = _make_service(composer=composer)
        captured: dict[str, object] = {}

        async def spy_prepare_agent(
            system_prompt: str | None = None,
            resolved_model: ResolvedModel | None = None,
        ) -> tuple[FakePOVAgent, PreparedModelCall]:
            captured["system_prompt"] = system_prompt
            return FakePOVAgent(output=_pov_output()), _prepared()

        svc._prepare_agent = spy_prepare_agent  # type: ignore[method-assign]
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)

        assert captured["system_prompt"] == "POV-SYSTEM-PROMPT"

    @pytest.mark.asyncio
    async def test_fallback_composes_directly_when_pipeline_none(self) -> None:
        """Without a pipeline, compose_invocation falls back to composer.build()."""
        composer = FakeComposer(system="FALLBACK-POV")
        novel, ch, svc = _make_service(composer=composer)
        _inject(svc, FakePOVAgent(output=_pov_output()))
        await svc.analyze(novel_id=novel.id, chapter_ids=[ch.id], user_id=novel.user_id)

        assert len(composer.build_calls) >= 1

    @pytest.mark.asyncio
    async def test_no_manual_injection_used(self) -> None:
        """Mode 1 never uses ManualInjectionDeclaration — composer drives the prompt.

        Regression guard: the service must not re-introduce a ``manual_injection``
        constant. ``POVService.__init__`` requires a ``composer`` (Mode 1), which
        is asserted by construction in ``_make_service``.
        """
        import inspect

        from narrare.analysis.services import pov_service

        source = inspect.getsource(pov_service)
        assert "ManualInjectionDeclaration" not in source
        assert "manual_injection=" not in source
