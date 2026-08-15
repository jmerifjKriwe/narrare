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

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.dependencies_services import SystemModelCategory
from narrare.analysis.dependencies import (
    get_pov_service,
    get_readability_service,
    get_sentiment_service,
)
from narrare.analysis.dependencies_beta_reader import get_beta_reader_service

# ---------------------------------------------------------------------------
# get_beta_reader_service
# ---------------------------------------------------------------------------


class TestGetBetaReaderService:
    """get_beta_reader_service(session, user_id, novel_id) — async factory.

    C5/ADR-082: resolves context_total_budget through the cascade and the
    model boundary, and injects it as the budget assembler's total
    (RULE-18b runtime-consumer evidence for the analysis side).
    """

    async def test_returns_beta_reader_service_with_resolved_budget(self) -> None:
        """All deps wired; budget_assembler.total_budget = resolved total."""
        import uuid as _uuid

        from narrare._app.config import Settings
        from narrare.settings.token_limits.contracts import TokenLimitOverrides
        from narrare.settings.token_limits.service import TokenLimitsService
        from narrare_core.context.contracts import EffectiveContextBudgets

        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_composer = MagicMock(spec=["compose", "build"])
        mock_config = MagicMock(spec=["model_id", "provider_name", "temperature", "max_tokens"])
        mock_pipeline = MagicMock(spec=["generate"])

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
                "narrare._app.dependencies_services.build_system_default_config",
                return_value=mock_config,
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
            result = await get_beta_reader_service(
                session, user_id=str(_uuid.uuid4()), novel_id=_uuid.uuid4()
            )

        assert result._budget_assembler.total_budget == 24_000


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
    """get_readability_service(session) — ReadabilityService factory."""

    def test_returns_readability_service_with_model_registry(self) -> None:
        """Returns ReadabilityService with ModelRegistry, config, composer, and pipeline."""
        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_composer = MagicMock(spec=["compose", "build"])
        mock_config = MagicMock(spec=["model_id", "provider_name", "temperature", "max_tokens"])
        mock_pipeline = MagicMock(spec=["generate"])

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch("narrare._app.dependencies.get_composer", return_value=mock_composer),
            patch(
                "narrare._app.dependencies_services.build_system_default_config",
                return_value=mock_config,
            ) as mock_build_config,
            patch("narrare._app.dependencies.get_invocation_pipeline", return_value=mock_pipeline),
            patch("narrare.chapters.repository.ChapterRepository") as mock_chapter_repo_cls,
            patch("narrare.novels.repository.NovelRepository") as mock_novel_repo_cls,
            patch(
                "narrare.analysis.services.readability_service.ReadabilityService",
            ) as mock_svc_cls,
        ):
            mock_svc = mock_svc_cls.return_value
            result = get_readability_service(session)

            # -- verify service instance
            assert result is mock_svc
            mock_svc_cls.assert_called_once()

            # -- verify build_system_default_config called with ANALYSIS
            mock_build_config.assert_called_once_with(SystemModelCategory.ANALYSIS)

            # -- verify repositories created with session
            mock_chapter_repo_cls.assert_called_once_with(session)
            mock_novel_repo_cls.assert_called_once_with(session)

            # -- verify ReadabilityService receives all deps (Mode 1: composer)
            mock_svc_cls.assert_called_once_with(
                chapter_repo=mock_chapter_repo_cls.return_value,
                novel_repo=mock_novel_repo_cls.return_value,
                model_registry=mock_registry,
                model_config=mock_config,
                composer=mock_composer,
                invocation_pipeline=mock_pipeline,
            )


# ---------------------------------------------------------------------------
# get_pov_service
# ---------------------------------------------------------------------------


class TestGetPOVService:
    """get_pov_service(session) — POVService factory."""

    def test_returns_pov_service_with_kb_repo(self) -> None:
        """Returns POVService with KB repository for character name resolution."""
        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_composer = MagicMock(spec=["compose", "build"])
        mock_config = MagicMock(spec=["model_id", "provider_name", "temperature", "max_tokens"])
        mock_pipeline = MagicMock(spec=["generate"])

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch("narrare._app.dependencies.get_composer", return_value=mock_composer),
            patch(
                "narrare._app.dependencies_services.build_system_default_config",
                return_value=mock_config,
            ) as mock_build_config,
            patch("narrare._app.dependencies.get_invocation_pipeline", return_value=mock_pipeline),
            patch("narrare.chapters.repository.ChapterRepository") as mock_chapter_repo_cls,
            patch("narrare.novels.repository.NovelRepository") as mock_novel_repo_cls,
            patch("narrare.kb.repository.KBRepository") as mock_kb_repo_cls,
            patch(
                "narrare.analysis.services.pov_service.POVService",
            ) as mock_svc_cls,
        ):
            mock_svc = mock_svc_cls.return_value
            result = get_pov_service(session)

            # -- verify service instance
            assert result is mock_svc
            mock_svc_cls.assert_called_once()

            # -- verify build_system_default_config called with ANALYSIS
            mock_build_config.assert_called_once_with(SystemModelCategory.ANALYSIS)

            # -- verify repositories created with session
            mock_chapter_repo_cls.assert_called_once_with(session)
            mock_novel_repo_cls.assert_called_once_with(session)
            mock_kb_repo_cls.assert_called_once_with(session)

            # -- verify POVService receives all deps incl. kb_repo + composer (Mode 1)
            mock_svc_cls.assert_called_once_with(
                chapter_repo=mock_chapter_repo_cls.return_value,
                novel_repo=mock_novel_repo_cls.return_value,
                kb_repo=mock_kb_repo_cls.return_value,
                model_registry=mock_registry,
                model_config=mock_config,
                composer=mock_composer,
                invocation_pipeline=mock_pipeline,
            )
