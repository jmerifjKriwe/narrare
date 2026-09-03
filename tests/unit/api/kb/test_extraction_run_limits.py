"""Regression tests — ExtractionService enforces ADR-045 output caps.

Root cause (production defect): ``extract_from_chapter`` called
``agent.run(prompt, deps)`` without ``usage_limits``/``model_settings``, so
``max_tokens`` — applied via ``usage_limits.output_tokens_limit`` per
ADR-045 — never reached the provider. On thinking models with
``tool_choice: required``, generation ran unbounded (~7 min/chapter).

The fix mirrors the established patterns: the gateway
(``ModelRegistry.run``) and the writing path (``InterviewDraftGenerator``)
resolve limits via ``DefaultRunLimitResolver`` and pass ``usage_limits`` +
``model_settings=build_runtime_model_settings(...)`` to the agent run.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.kb.extraction_service import ExtractionService
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.run_limits import DefaultRunLimitResolver

from ._extraction_helpers import (
    FakeChapterRepo,
    FakeComposer,
    FakeKBRepo,
    FakeModelRegistry,
    make_chapter,
    make_extraction_output,
)

if TYPE_CHECKING:
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test", model_id="test-model", temperature=0.7, max_tokens=4096
    )


def _make_service(
    config: ResolvedModelConfig,
    chapter_repo: FakeChapterRepo,
    kb_repo: FakeKBRepo,
    composer: FakeComposer,
    resolver: DefaultRunLimitResolver | None,
) -> ExtractionService:
    """Build ExtractionService with fakes via cast (RULE-23: no type-ignore)."""
    registry = FakeModelRegistry()
    return ExtractionService(
        registry=cast("ModelRegistry", registry),
        config=config,
        chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
        kb_repo=cast("KBRepositoryProtocol", kb_repo),
        composer=cast("PromptComposer", composer),
        run_limit_resolver=resolver,
    )


def _patched_agent(output: object) -> tuple[MagicMock, MagicMock]:
    """Build a spec'd fake ExtractionAgent instance (run → output)."""
    mock_agent = MagicMock(spec=["run"])
    mock_agent.run = AsyncMock(return_value=output)
    return mock_agent, mock_agent


# ---------------------------------------------------------------------------
# Regression — resolver wired → caps reach agent.run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_chapter_with_resolver_passes_usage_limits_and_model_settings() -> None:
    """ADR-045: agent.run receives usage_limits + model_settings[max_tokens].

    Regression guard for the unbounded-generation defect: without this,
    ``max_tokens`` never reached the provider on the KB extraction path.
    """
    config = _make_config()
    resolver = DefaultRunLimitResolver(model_limits_provider=lambda _p, _m: None)
    expected = resolver.resolve(config=config, budget=None, invocation_id=uuid4())
    # Sanity: the fixture config resolves to its raw max_tokens (no profile).
    assert expected.effective_output_tokens == 4096

    chapter_repo = FakeChapterRepo()
    chapter = make_chapter()
    chapter_repo.get_by_id.return_value = chapter
    kb_repo = FakeKBRepo()
    composer = FakeComposer()

    mock_agent, _ = _patched_agent(make_extraction_output())
    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        MockAgent.return_value = mock_agent
        service = _make_service(config, chapter_repo, kb_repo, composer, resolver)
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

    kwargs = mock_agent.run.call_args.kwargs
    assert kwargs["usage_limits"] is not None
    assert kwargs["usage_limits"].output_tokens_limit == expected.effective_output_tokens
    assert kwargs["model_settings"] is not None
    assert kwargs["model_settings"]["max_tokens"] == expected.effective_output_tokens


# ---------------------------------------------------------------------------
# Backward-compat — resolver omitted (legacy/test wiring) → no caps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_from_chapter_without_resolver_applies_no_output_caps() -> None:
    """Documented fallback: ``run_limit_resolver=None`` enforces no caps.

    Backward-compat for existing wiring/tests that construct the service
    without a resolver: ``usage_limits`` stays ``None`` and
    ``model_settings`` carries no ``max_tokens`` (provider ``test`` has no
    cache settings).
    """
    config = _make_config()
    chapter_repo = FakeChapterRepo()
    chapter = make_chapter()
    chapter_repo.get_by_id.return_value = chapter
    kb_repo = FakeKBRepo()
    composer = FakeComposer()

    mock_agent, _ = _patched_agent(make_extraction_output())
    with patch("narrare.kb.extraction_service.ExtractionAgent") as MockAgent:
        MockAgent.return_value = mock_agent
        service = _make_service(config, chapter_repo, kb_repo, composer, None)
        await service.extract_from_chapter(
            novel_id=uuid4(),
            chapter_id=chapter.id,
            user_id=uuid4(),
        )

    kwargs = mock_agent.run.call_args.kwargs
    assert kwargs["usage_limits"] is None
    assert kwargs["model_settings"] is None


# ---------------------------------------------------------------------------
# Production wiring — DI factory injects the resolver
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_extraction_service_injects_run_limit_resolver() -> None:
    """``get_extraction_service`` wires a ``DefaultRunLimitResolver``.

    Pins the production DI factory: the caps fix is only effective when the
    factory actually injects the resolver (mirrors ``chat/dependencies.py``
    and ``writing/deps_ws.py``).
    """
    from narrare.kb.dependencies_extraction import get_extraction_service
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare_core.llm.run_limits import DefaultRunLimitResolver as Resolver

    config = _make_config()
    routing_resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    routing_resolver.resolve = AsyncMock(
        return_value=SimpleNamespace(config=config, api_key="sk-user", base_url=None)
    )

    with (
        patch(
            "narrare.kb.dependencies_extraction.get_model_routing_resolver",
            return_value=routing_resolver,
        ),
        patch(
            "narrare._app.dependencies.get_model_registry",
            return_value=MagicMock(spec=["get_model"], name="ModelRegistry"),
        ),
        patch(
            "narrare._app.dependencies.get_composer",
            return_value=MagicMock(spec=["build"], name="PromptComposer"),
        ),
        patch("narrare._app.dependencies.get_invocation_pipeline", return_value=None),
        patch("narrare.kb.extraction_service.ExtractionService") as MockService,
    ):
        MockService.return_value = MagicMock(
            spec=ExtractionService, name="ExtractionServiceInstance"
        )
        await get_extraction_service(
            novel_id=uuid4(),
            session=MagicMock(spec=["execute"], name="AsyncSession"),
            user_id=str(uuid4()),
        )

    kwargs = MockService.call_args.kwargs
    injected = kwargs["run_limit_resolver"]
    assert isinstance(injected, Resolver)
