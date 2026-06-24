"""Unit tests for narrare/analysis/dependencies.py — DI factory functions.

Tests the four factory functions that wire analysis services with their
dependencies:

- ``get_beta_reader_service`` — BetaReaderService with ModelRegistry,
  PromptComposer, Redis cache, ContextAssembler, InvocationPipeline.
- ``get_sentiment_service`` — ChapterSentimentService with SpacyNLPProvider
  (deterministic analysis, no LLM).
- ``get_readability_service`` — ReadabilityService with ModelRegistry,
  InvocationPipeline.
- ``get_pov_service`` — POVService with ModelRegistry, KBRepository,
  InvocationPipeline.

Each factory uses **lazy imports** inside the function body (FastAPI DI
pattern), so tests mock at the module attribute level before calling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from narrare._app.config import Settings
from narrare._app.dependencies_services import SystemModelCategory
from narrare.analysis.dependencies import (
    get_beta_reader_service,
    get_pov_service,
    get_readability_service,
    get_sentiment_service,
)

# ---------------------------------------------------------------------------
# get_beta_reader_service
# ---------------------------------------------------------------------------


class TestGetBetaReaderService:
    """get_beta_reader_service(session) — BetaReaderService factory."""

    def test_returns_beta_reader_service_with_all_deps(self) -> None:
        """Returns BetaReaderService with all dependencies wired correctly."""
        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_composer = MagicMock(spec=["compose", "build"])
        mock_config = MagicMock(spec=["model_id", "provider_name", "temperature", "max_tokens"])
        mock_pipeline = MagicMock(spec=["generate"])
        mock_settings = MagicMock(spec=Settings, redis_url="redis://localhost:6379/0")

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch("narrare._app.dependencies.get_composer", return_value=mock_composer),
            patch(
                "narrare._app.dependencies_services.build_system_default_config",
                return_value=mock_config,
            ) as mock_build_config,
            patch("narrare._app.dependencies.get_invocation_pipeline", return_value=mock_pipeline),
            patch("narrare._app.config.get_settings", return_value=mock_settings),
            patch("narrare.chapters.repository.ChapterRepository") as mock_chapter_repo_cls,
            patch("narrare.kb.repository.KBRepository") as mock_kb_repo_cls,
            patch("narrare.novels.repository.NovelRepository") as mock_novel_repo_cls,
            patch("narrare.analysis.context_assembler.ContextAssembler") as mock_assembler_cls,
            patch("narrare_core.cache.redis_client.RedisSessionCache") as mock_redis_cls,
            patch("narrare.analysis.beta_reader_cache.BetaReaderCache") as mock_cache_cls,
            patch("narrare.analysis.beta_reader_service.BetaReaderService") as mock_svc_cls,
        ):
            mock_svc = mock_svc_cls.return_value
            result = get_beta_reader_service(session)

            # -- verify service instance
            assert result is mock_svc
            mock_svc_cls.assert_called_once()

            # -- verify build_system_default_config called with ANALYSIS category
            mock_build_config.assert_called_once_with(SystemModelCategory.ANALYSIS)

            # -- verify repositories created with session
            mock_chapter_repo_cls.assert_called_once_with(session)
            mock_kb_repo_cls.assert_called_once_with(session)
            mock_novel_repo_cls.assert_called_once_with(session)

            # -- verify ContextAssembler built with repos
            mock_assembler_cls.assert_called_once_with(
                chapter_repo=mock_chapter_repo_cls.return_value,
                kb_repo=mock_kb_repo_cls.return_value,
                novel_repo=mock_novel_repo_cls.return_value,
            )

            # -- verify Redis cache built with settings.redis_url
            mock_redis_cls.assert_called_once_with("redis://localhost:6379/0")

            # -- verify BetaReaderCache wraps Redis cache
            mock_cache_cls.assert_called_once_with(mock_redis_cls.return_value)

            # -- verify BetaReaderService receives all deps
            mock_svc_cls.assert_called_once_with(
                context_assembler=mock_assembler_cls.return_value,
                cache=mock_cache_cls.return_value,
                registry=mock_registry,
                config=mock_config,
                composer=mock_composer,
                invocation_pipeline=mock_pipeline,
            )


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
        """Returns ReadabilityService with ModelRegistry, config, and pipeline."""
        session = AsyncMock(spec=AsyncSession)
        mock_registry = MagicMock(spec=["get_model", "register_model"])
        mock_config = MagicMock(spec=["model_id", "provider_name", "temperature", "max_tokens"])
        mock_pipeline = MagicMock(spec=["generate"])

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
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

            # -- verify ReadabilityService receives all deps
            mock_svc_cls.assert_called_once_with(
                chapter_repo=mock_chapter_repo_cls.return_value,
                novel_repo=mock_novel_repo_cls.return_value,
                model_registry=mock_registry,
                model_config=mock_config,
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
        mock_config = MagicMock(spec=["model_id", "provider_name", "temperature", "max_tokens"])
        mock_pipeline = MagicMock(spec=["generate"])

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
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

            # -- verify POVService receives all deps including kb_repo
            mock_svc_cls.assert_called_once_with(
                chapter_repo=mock_chapter_repo_cls.return_value,
                novel_repo=mock_novel_repo_cls.return_value,
                kb_repo=mock_kb_repo_cls.return_value,
                model_registry=mock_registry,
                model_config=mock_config,
                invocation_pipeline=mock_pipeline,
            )
