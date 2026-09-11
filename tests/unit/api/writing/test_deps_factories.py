"""Import-level and error-path tests for writing DI factory modules.

Category B coverage: DI Factory files (currently 28-46% uncovered).

For each factory we verify:
1. The module imports cleanly (class-level import test).
2. The factory function exists and is an async callable.

For ``deps_story_suggest.py`` we additionally test:
- Novel not found → raises ``NotFoundError``
- ConfigurationError during resolve → graceful degradation
- Success path with mocked dependencies

Uses ``MagicMock(spec=...)`` / ``AsyncMock(spec=...)`` for type-safe mocking
(RULE-TEST-01, per test_deps_ws.py / test_deps_tier_overrides.py patterns).
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare_core.context.contracts import EffectiveContextBudgets
from narrare_core.shared.errors import NotFoundError

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_session() -> MagicMock:
    """A spec'd AsyncSession mock for factory repository construction.

    Repository constructors only store the session, so a spec'd mock is
    sufficient and satisfies RULE-TEST-01 (no bare ``MagicMock()``).
    """
    return MagicMock(spec=AsyncSession, name="session")


# ===========================================================================
# deps_style_variants.py — get_style_variant_service
# ===========================================================================


class TestStyleVariantsFactory:
    """Import, structural, and execution tests for get_style_variant_service."""

    def test_factory_function_exists(self) -> None:
        """The factory function is defined in the module."""
        from narrare.writing.deps_style_variants import get_style_variant_service

        assert get_style_variant_service is not None

    def test_factory_function_is_async(self) -> None:
        """The factory is a coroutine function (async def)."""
        from narrare.writing.deps_style_variants import get_style_variant_service

        assert inspect.iscoroutinefunction(get_style_variant_service)

    def test_factory_signature(self) -> None:
        """The factory accepts session, user_id, and optional project_id."""
        from narrare.writing.deps_style_variants import get_style_variant_service

        sig = inspect.signature(get_style_variant_service)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "user_id" in params
        assert "project_id" in params

    async def test_execution_returns_style_variant_service(self) -> None:
        """Smoke test: factory wires up and returns a StyleVariantService."""
        from narrare.writing.deps_style_variants import get_style_variant_service
        from narrare.writing.style_variant_service import StyleVariantService
        from narrare_core.llm import ResolvedModelConfig

        session = _fake_session()
        user_id = str(uuid4())
        project_id = uuid4()

        from types import SimpleNamespace

        from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl

        # Use real dataclass so dataclasses.replace() in the factory works
        fake_config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            temperature=0.7,
            max_tokens=4096,
        )
        fake_resolved = SimpleNamespace(
            config=fake_config,
            api_key=None,
            base_url=None,
        )
        fake_resolver = MagicMock(spec=ModelRoutingResolverImpl)
        fake_resolver.resolve = AsyncMock(return_value=fake_resolved)

        # Fake token limits — minimal object with the two properties the factory reads
        fake_limits = SimpleNamespace(
            output_limit=4096,
            tier_percentages=None,
        )
        fake_limits_service = MagicMock(spec=["get_resolved_limits"], name="TokenLimitsService")
        fake_limits_service.get_resolved_limits = AsyncMock(return_value=fake_limits)

        # Stub out the rest of the lazy imports
        fake_pipeline = MagicMock(spec=["generate"], name="pipeline")
        fake_settings = MagicMock(spec=True, name="Settings")
        fake_repo = MagicMock(spec=["get_by_id"], name="GenerationRepository")

        # Fix-wave N1: the factory gates the project scope at entry via
        # the (call-time imported) NovelRepository — stub the ownership
        # lookup so the hermetic smoke test stays on the happy path.
        fake_novel_repo = MagicMock(spec=["get_by_id"], name="NovelRepository")
        fake_novel_repo.get_by_id = AsyncMock(return_value=MagicMock(spec=True, name="novel"))

        with (
            patch(
                "narrare.writing.deps_style_variants.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch(
                "narrare.settings.token_limits.service.TokenLimitsService",
                return_value=fake_limits_service,
            ),
            # ADR-082 wiring: the factory resolves context budgets before
            # building the pipeline — patch the adapter so no models.dev
            # window provider is constructed.
            patch(
                "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
                return_value=EffectiveContextBudgets(
                    context_total=32_000,
                    series_history=0,
                    writing_tier_base=32_000,
                    reserve_tokens=8_096,
                    context_window=128_000,
                    source="cascade:uncapped",
                ),
            ),
            # Lazy imports inside function body — patch at definition site
            patch("narrare._app.config.get_settings", return_value=fake_settings),
            patch("narrare.writing.deps_pipeline.create_pipeline", return_value=fake_pipeline),
            patch("narrare.writing.repository.GenerationRepository", return_value=fake_repo),
            patch("narrare.novels.repository.NovelRepository", return_value=fake_novel_repo),
        ):
            service = await get_style_variant_service(
                session=session,
                user_id=user_id,
                project_id=project_id,
            )

        assert isinstance(service, StyleVariantService)


# ===========================================================================
# deps_story_suggest.py — get_story_suggest_service
# ===========================================================================


class TestStorySuggestFactory:
    """Import, structural, and error-path tests for get_story_suggest_service."""

    def test_factory_function_exists(self) -> None:
        """The factory function is defined in the module."""
        from narrare.writing.deps_story_suggest import get_story_suggest_service

        assert get_story_suggest_service is not None

    def test_factory_function_is_async(self) -> None:
        """The factory is a coroutine function (async def)."""
        from narrare.writing.deps_story_suggest import get_story_suggest_service

        assert inspect.iscoroutinefunction(get_story_suggest_service)

    def test_factory_signature(self) -> None:
        """The factory accepts session, user_id, and novel_id."""
        from narrare.writing.deps_story_suggest import get_story_suggest_service

        sig = inspect.signature(get_story_suggest_service)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "user_id" in params
        assert "novel_id" in params

    # ------------------------------------------------------------------
    # Error path: novel not found
    # ------------------------------------------------------------------

    async def test_raises_not_found_when_novel_missing(self) -> None:
        """Raises NotFoundError when the novel repository returns None."""
        from narrare.writing.deps_story_suggest import get_story_suggest_service

        session = _fake_session()
        novel_id = uuid4()
        user_id = str(uuid4())

        # Mock NovelRepository to return None (novel not found)
        fake_repo = MagicMock(spec=["get_by_id"], name="NovelRepository")
        fake_repo.get_by_id = AsyncMock(return_value=None)

        with (
            patch(
                "narrare.writing.deps_story_suggest.NovelRepository",
                return_value=fake_repo,
            ),
            pytest.raises(NotFoundError, match=str(novel_id)),
        ):
            await get_story_suggest_service(
                session=session,
                user_id=user_id,
                novel_id=novel_id,
            )

    # ------------------------------------------------------------------
    # Error path: ConfigurationError → graceful degradation
    # ------------------------------------------------------------------

    async def test_graceful_degradation_when_no_ai_provider(self) -> None:
        """ConfigurationError from resolver results in model_config=None."""
        from narrare.writing.deps_story_suggest import get_story_suggest_service

        session = _fake_session()
        novel_id = uuid4()
        user_id = str(uuid4())

        # Novel exists
        fake_novel = MagicMock(spec=True, name="novel")
        fake_novel_repo = MagicMock(spec=["get_by_id"], name="NovelRepository")
        fake_novel_repo.get_by_id = AsyncMock(return_value=fake_novel)

        # Resolver raises ConfigurationError
        from narrare_core.shared.errors import ConfigurationError

        fake_resolver = MagicMock(spec=["resolve"], name="resolver")
        fake_resolver.resolve = AsyncMock(side_effect=ConfigurationError("No provider"))

        # Stub out the other dependencies so we get a service back
        with (
            patch(
                "narrare.writing.deps_story_suggest.NovelRepository",
                return_value=fake_novel_repo,
            ),
            patch(
                "narrare.writing.deps_story_suggest.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch("narrare.writing.deps_story_suggest.get_model_registry"),
            patch("narrare.writing.deps_story_suggest.get_composer"),
            patch("narrare.writing.deps_story_suggest.get_invocation_pipeline"),
        ):
            service = await get_story_suggest_service(
                session=session,
                user_id=user_id,
                novel_id=novel_id,
            )

        # Graceful degradation means model_config is None
        assert service._config is None

    # ------------------------------------------------------------------
    # Success path (smoke test)
    # ------------------------------------------------------------------

    async def test_success_path_returns_service(self) -> None:
        """Happy path returns a fully wired StorySuggestService."""
        from narrare.writing.deps_story_suggest import get_story_suggest_service
        from narrare.writing.story_suggest_service import StorySuggestService

        session = _fake_session()
        novel_id = uuid4()
        user_id = str(uuid4())

        # Novel exists
        fake_novel = MagicMock(spec=True, name="novel")
        fake_novel_repo = MagicMock(spec=["get_by_id"], name="NovelRepository")
        fake_novel_repo.get_by_id = AsyncMock(return_value=fake_novel)

        # Successful model resolution
        fake_resolved = MagicMock(spec=["config"], name="resolved")
        fake_resolved.config = MagicMock(spec=True, name="config")

        fake_resolver = MagicMock(spec=["resolve"], name="resolver")
        fake_resolver.resolve = AsyncMock(return_value=fake_resolved)

        with (
            patch(
                "narrare.writing.deps_story_suggest.NovelRepository",
                return_value=fake_novel_repo,
            ),
            patch(
                "narrare.writing.deps_story_suggest.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch("narrare.writing.deps_story_suggest.get_model_registry"),
            patch("narrare.writing.deps_story_suggest.get_composer"),
            patch("narrare.writing.deps_story_suggest.get_invocation_pipeline"),
        ):
            service = await get_story_suggest_service(
                session=session,
                user_id=user_id,
                novel_id=novel_id,
            )

        assert isinstance(service, StorySuggestService)
        assert service._config is not None


# ===========================================================================
# deps_suggest.py — get_suggest_service
# ===========================================================================


class TestSuggestFactory:
    """Import, structural, and execution tests for get_suggest_service."""

    def test_factory_function_exists(self) -> None:
        """The factory function is defined in the module."""
        from narrare.writing.deps_suggest import get_suggest_service

        assert get_suggest_service is not None

    def test_factory_function_is_async(self) -> None:
        """The factory is a coroutine function (async def)."""
        from narrare.writing.deps_suggest import get_suggest_service

        assert inspect.iscoroutinefunction(get_suggest_service)

    def test_factory_signature(self) -> None:
        """The factory accepts session, user_id, and optional project_id."""
        from narrare.writing.deps_suggest import get_suggest_service

        sig = inspect.signature(get_suggest_service)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "user_id" in params
        assert "project_id" in params

    async def test_execution_returns_inline_suggest_service(self) -> None:
        """Smoke test: factory wires up and returns an InlineSuggestService."""
        from narrare.writing.deps_suggest import get_suggest_service
        from narrare.writing.suggest_service import InlineSuggestService
        from narrare_core.llm import ResolvedModelConfig

        session = _fake_session()
        user_id = str(uuid4())
        project_id = uuid4()

        from types import SimpleNamespace

        from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl

        # Use real dataclass so dataclasses.replace() in the factory works
        fake_config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            temperature=0.3,
            max_tokens=500,
        )
        fake_resolved = SimpleNamespace(
            config=fake_config,
            api_key=None,
            base_url=None,
        )
        fake_resolver = MagicMock(spec=ModelRoutingResolverImpl)
        fake_resolver.resolve = AsyncMock(return_value=fake_resolved)

        fake_registry = MagicMock(spec=["get_model"], name="ModelRegistry")
        fake_composer = MagicMock(spec=["compose"], name="PromptComposer")
        fake_repo = MagicMock(spec=["get_by_id"], name="ChapterRepository")

        # Fix-wave N1: the factory gates the project scope at entry via
        # the (call-time imported) NovelRepository — stub the ownership
        # lookup so the hermetic smoke test stays on the happy path.
        fake_novel_repo = MagicMock(spec=["get_by_id"], name="NovelRepository")
        fake_novel_repo.get_by_id = AsyncMock(return_value=MagicMock(spec=True, name="novel"))

        with (
            patch(
                "narrare.writing.deps_suggest.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch("narrare.writing.deps_suggest.get_model_registry", return_value=fake_registry),
            patch("narrare.writing.deps_suggest.get_composer", return_value=fake_composer),
            # Lazy import inside function body — patch at definition site
            patch("narrare.chapters.repository.ChapterRepository", return_value=fake_repo),
            patch("narrare.novels.repository.NovelRepository", return_value=fake_novel_repo),
        ):
            service = await get_suggest_service(
                session=session,
                user_id=user_id,
                project_id=project_id,
            )

        assert isinstance(service, InlineSuggestService)
