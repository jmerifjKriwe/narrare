"""Unit tests for narrare/analysis/dependencies.py — DI factory functions.

Tests the factory functions that wire analysis services with their
dependencies:

- ``get_beta_reader_service`` (in ``dependencies_beta_reader.py``) —
  BetaReaderService with ModelRegistry, PromptComposer, in-memory cache,
  ContextAssembler, canonical KBContextProvider (ADR-067), InvocationPipeline.
- ``get_sentiment_service`` — ChapterSentimentService with SpacyNLPProvider
  (deterministic analysis, no LLM).
- ``get_readability_service`` — ReadabilityService with ModelRegistry,
  PromptComposer, InvocationPipeline.
- ``get_pov_service`` — POVService with ModelRegistry, KBRepository,
  PromptComposer, InvocationPipeline.

Each factory uses **lazy imports** inside the function body (FastAPI DI
pattern), so tests mock at the module attribute level before calling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.dependencies_services import LazyModelResolution
from narrare.analysis.dependencies import (
    get_pov_service,
    get_readability_service,
    get_sentiment_service,
)
from narrare.analysis.dependencies_beta_reader import get_beta_reader_service
from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

# ---------------------------------------------------------------------------
# Shared user-routing helpers (user-routing regressions: test_deps_user_routing.py)
# ---------------------------------------------------------------------------

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _fake_resolver() -> tuple[MagicMock, ResolvedModel]:
    """A spec'd fake resolver whose resolve() returns the user's model."""
    resolved = ResolvedModel(
        config=ResolvedModelConfig(
            provider_name="zai",
            model_id="glm-4.7",
            temperature=0.7,
            max_tokens=4096,
        ),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(return_value=resolved)
    return resolver, resolved


# ---------------------------------------------------------------------------
# get_beta_reader_service
# ---------------------------------------------------------------------------


class TestGetBetaReaderService:
    """get_beta_reader_service(session, user_id, novel_id) — async factory.

    ADR-086: the factory wires LAZILY — both the routing cascade AND the
    token-limits cascade (RULE-18b; source unchanged, timing deferred)
    run at the service's first use, not at construction (which happens
    pre-body-validation).
    """

    async def test_wires_lazy_resolution_and_defers_both_cascades(self) -> None:
        """No resolution at construction; first use runs both cascades."""
        import uuid as _uuid

        from narrare._app.config import Settings
        from narrare.settings.token_limits.contracts import TokenLimitOverrides
        from narrare.settings.token_limits.service import TokenLimitsService
        from narrare_core.context.contracts import EffectiveContextBudgets

        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_composer = MagicMock(spec=["compose", "build"])
        mock_pipeline = MagicMock(spec=["generate"])
        resolver, resolved = _fake_resolver()
        user_id = str(_uuid.uuid4())
        novel_id = _uuid.uuid4()

        fake_limits = TokenLimitOverrides(context_total_budget=24_000)
        fake_token_service = MagicMock(spec=TokenLimitsService)
        fake_token_service.get_resolved_limits = AsyncMock(return_value=fake_limits)

        canned = EffectiveContextBudgets(
            context_total=24_000,
            series_history=0,
            writing_tier_base=24_000,
            reserve_tokens=4_096,
            context_window=128_000,
            source="cascade:uncapped",
        )

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch("narrare._app.dependencies.get_composer", return_value=mock_composer),
            patch(
                "narrare.analysis.dependencies_beta_reader.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch("narrare._app.dependencies.get_invocation_pipeline", return_value=mock_pipeline),
            patch("narrare.chapters.repository.ChapterRepository"),
            patch("narrare.kb.repository.KBRepository"),
            patch("narrare.kb.relationship_repository.RelationshipRepository"),
            patch("narrare.novels.repository.NovelRepository"),
            patch("narrare.kb._context_provider.KBContextProvider"),
            patch("narrare.analysis.context_assembler.ContextAssembler"),
            patch("narrare_core.cache.InMemorySessionCache"),
            patch("narrare.analysis.beta_reader_cache.BetaReaderCache"),
            patch(
                "narrare.settings.token_limits.service.TokenLimitsService",
                return_value=fake_token_service,
            ),
            patch(
                "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
                return_value=canned,
            ),
            patch(
                "narrare._app.config.get_settings",
                return_value=MagicMock(spec=Settings, name="settings"),
            ),
        ):
            result = await get_beta_reader_service(session, user_id=user_id, novel_id=novel_id)

        # ADR-086 lazy wiring: the factory runs pre-body-validation, so
        # it must NOT resolve — BOTH cascades are deferred to first use.
        assert resolver.resolve.await_args_list == []
        assert fake_token_service.get_resolved_limits.await_args_list == []
        assert isinstance(result._model_resolution, LazyModelResolution)

        # First use, step 1: the routing cascade runs with the real
        # intent (BETA_READ) for this user + novel (project tier).
        resolved_model = await result._model_resolution.resolve()
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.BETA_READ, UUID(user_id), novel_id)
        ]
        assert resolved_model.config is resolved.config
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL

        # First use, step 2: the deferred composition awaits the
        # token-limits cascade + the resolved window and builds the
        # budget assembler at the resolved context_total_budget.
        budget_assembler = await result._budget_assembler_factory()
        fake_token_service.get_resolved_limits.assert_awaited_once_with(
            user_id=user_id, project_id=str(novel_id)
        )
        assert budget_assembler.total_budget == 24_000


# ---------------------------------------------------------------------------
# get_sentiment_service
# ---------------------------------------------------------------------------


class TestGetSentimentService:
    """get_sentiment_service(session) — ChapterSentimentService factory."""

    def test_returns_sentiment_service_with_nlp_provider(self) -> None:
        """Returns ChapterSentimentService with SpacyNLPProvider injected."""
        session = AsyncMock(spec=AsyncSession)

        with (
            patch("narrare.chapters.repository.ChapterRepository") as mock_chapter_repo_cls,
            patch("narrare.novels.repository.NovelRepository") as mock_novel_repo_cls,
            patch(
                "narrare_core.nlp.provider_spacy.SpacyNLPProvider",
            ) as mock_nlp_cls,
            patch(
                "narrare.analysis.services.sentiment_service.ChapterSentimentService",
            ) as mock_svc_cls,
        ):
            mock_svc = mock_svc_cls.return_value
            result = get_sentiment_service(session)

            # -- verify service instance
            assert result is mock_svc
            mock_svc_cls.assert_called_once()

            # -- verify repositories created with session
            mock_chapter_repo_cls.assert_called_once_with(session)
            mock_novel_repo_cls.assert_called_once_with(session)

            # -- verify SpacyNLPProvider created (no args)
            mock_nlp_cls.assert_called_once_with()

            # -- verify ChapterSentimentService receives all deps
            mock_svc_cls.assert_called_once_with(
                chapter_repo=mock_chapter_repo_cls.return_value,
                novel_repo=mock_novel_repo_cls.return_value,
                nlp_provider=mock_nlp_cls.return_value,
            )

    def test_no_model_registry_called(self) -> None:
        """Sentiment factory does NOT call any LLM-related DI functions.

        Sentiment analysis is purely deterministic (ADR-021), so the
        factory must NOT import or call get_model_registry, get_composer,
        or any other LLM dependencies.
        """
        session = AsyncMock(spec=AsyncSession)

        # These DI functions should NOT be called by the sentiment factory.
        # If they were, the import would trigger patched modules anyway,
        # but we verify by checking that only the expected modules are touched.
        with (
            patch("narrare.chapters.repository.ChapterRepository"),
            patch("narrare.novels.repository.NovelRepository"),
            patch("narrare_core.nlp.provider_spacy.SpacyNLPProvider"),
            patch(
                "narrare.analysis.services.sentiment_service.ChapterSentimentService",
            ),
            patch("narrare._app.dependencies.get_model_registry") as mock_registry,
        ):
            get_sentiment_service(session)
            mock_registry.assert_not_called()


# ---------------------------------------------------------------------------
# get_readability_service
# ---------------------------------------------------------------------------


class TestGetReadabilityService:
    """get_readability_service(novel_id, session, user_id) — async factory.

    ADR-086: the factory wires LAZILY — no resolution at construction
    (which happens pre-body-validation); the ANALYSE cascade runs at the
    service's first use.
    """

    async def test_wires_lazy_resolution_and_defers_cascade(self) -> None:
        """No resolution at construction; first use runs the cascade."""
        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_composer = MagicMock(spec=["compose", "build"])
        mock_pipeline = MagicMock(spec=["generate"])
        resolver, resolved = _fake_resolver()
        user_id = str(uuid4())
        novel_id = uuid4()

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch("narrare._app.dependencies.get_composer", return_value=mock_composer),
            patch(
                "narrare.analysis.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch("narrare._app.dependencies.get_invocation_pipeline", return_value=mock_pipeline),
            patch("narrare.chapters.repository.ChapterRepository"),
            patch("narrare.novels.repository.NovelRepository"),
        ):
            result = await get_readability_service(
                novel_id=novel_id, session=session, user_id=user_id
            )

        # ADR-086 lazy wiring: the factory runs pre-body-validation, so
        # it must NOT resolve — the cascade is deferred to first use.
        assert resolver.resolve.await_args_list == []
        assert isinstance(result._model_resolution, LazyModelResolution)

        resolved_model = await result._model_resolution.resolve()
        # The REAL intent (ANALYSE), for THIS user, WITH the novel
        # (project) tier — invoked at first use, not at construction:
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.ANALYSE, UUID(user_id), novel_id)
        ]
        assert result._model_registry is mock_registry
        assert resolved_model.config is resolved.config
        assert result._composer is mock_composer
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL


# ---------------------------------------------------------------------------
# get_pov_service
# ---------------------------------------------------------------------------


class TestGetPOVService:
    """get_pov_service(novel_id, session, user_id) — async factory.

    ADR-086: the factory wires LAZILY — no resolution at construction
    (which happens pre-body-validation); the ANALYSE cascade runs at the
    service's first use.
    """

    async def test_wires_lazy_resolution_and_defers_cascade(self) -> None:
        """No resolution at construction; first use runs the cascade."""
        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_composer = MagicMock(spec=["compose", "build"])
        mock_pipeline = MagicMock(spec=["generate"])
        resolver, resolved = _fake_resolver()
        user_id = str(uuid4())
        novel_id = uuid4()

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch("narrare._app.dependencies.get_composer", return_value=mock_composer),
            patch(
                "narrare.analysis.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch("narrare._app.dependencies.get_invocation_pipeline", return_value=mock_pipeline),
            patch("narrare.chapters.repository.ChapterRepository"),
            patch("narrare.novels.repository.NovelRepository"),
            patch("narrare.kb.repository.KBRepository"),
        ):
            result = await get_pov_service(novel_id=novel_id, session=session, user_id=user_id)

        # ADR-086 lazy wiring: the factory runs pre-body-validation, so
        # it must NOT resolve — the cascade is deferred to first use.
        assert resolver.resolve.await_args_list == []
        assert isinstance(result._model_resolution, LazyModelResolution)

        resolved_model = await result._model_resolution.resolve()
        # The REAL intent (ANALYSE), for THIS user, WITH the novel
        # (project) tier — invoked at first use, not at construction:
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.ANALYSE, UUID(user_id), novel_id)
        ]
        assert result._model_registry is mock_registry
        assert resolved_model.config is resolved.config
        assert result._composer is mock_composer
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL
