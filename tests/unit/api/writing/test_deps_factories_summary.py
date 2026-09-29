"""Tests for summary_deps.py — get_summary_service factory."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_session() -> MagicMock:
    """A spec'd AsyncSession mock for factory repository construction."""
    return MagicMock(spec=AsyncSession, name="session")


# ===========================================================================
# summary_deps.py — get_summary_service
# ===========================================================================


class TestSummaryDepsFactory:
    """Import, structural, and execution tests for get_summary_service."""

    def test_factory_function_exists(self) -> None:
        """The factory function is defined in the module."""
        from narrare.writing.summary_deps import get_summary_service

        assert get_summary_service is not None

    def test_factory_function_is_async(self) -> None:
        """The factory is a coroutine function (async def)."""
        from narrare.writing.summary_deps import get_summary_service

        assert inspect.iscoroutinefunction(get_summary_service)

    def test_factory_signature(self) -> None:
        """The factory accepts user_id, novel_id, and session with Depends defaults."""
        from narrare.writing.summary_deps import get_summary_service

        sig = inspect.signature(get_summary_service)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    async def test_execution_returns_chapter_summary_service(self) -> None:
        """Smoke test: factory wires up lazily and returns a ChapterSummaryService.

        ADR-086 L38 contract: construction touches NEITHER cascade — the
        SUMMARIZE routing resolve and the token-limits resolve are deferred
        behind the service's ``ensure_resolved`` (first use; pinned in
        ``test_summary_lazy_resolution.py``).
        """
        from narrare.writing.summary_deps import get_summary_service
        from narrare.writing.summary_service import ChapterSummaryService
        from narrare_core.llm import ResolvedModelConfig

        session = _fake_session()
        user_id = str(uuid4())
        novel_id = uuid4()

        from types import SimpleNamespace

        from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl

        # Use real dataclass so dataclasses.replace() in the factory works
        fake_config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            temperature=0.3,
            max_tokens=4096,
        )
        fake_resolved = SimpleNamespace(
            config=fake_config,
            api_key=None,
            base_url=None,
        )
        fake_resolver = MagicMock(spec=ModelRoutingResolverImpl)
        fake_resolver.resolve = AsyncMock(return_value=fake_resolved)

        fake_limits = SimpleNamespace(
            output_limit=4096,
            tier_percentages=None,
        )
        fake_limits_service = MagicMock(spec=["get_resolved_limits"], name="TokenLimitsService")
        fake_limits_service.get_resolved_limits = AsyncMock(return_value=fake_limits)

        fake_settings = MagicMock(spec=True, name="Settings")
        fake_registry = MagicMock(spec=["get_model"], name="ModelRegistry")
        fake_repo = MagicMock(spec=["get_by_id"], name="ChapterRepository")
        fake_composer = MagicMock(spec=["compose"], name="PromptComposer")
        fake_invocation_pipeline = MagicMock(spec=["generate"], name="InvocationPipeline")

        with (
            patch(
                "narrare.writing.summary_deps.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch(
                "narrare.settings.token_limits.service.TokenLimitsService",
                return_value=fake_limits_service,
            ),
            # Lazy imports inside function body — patch at definition sites
            patch("narrare._app.config.get_settings", return_value=fake_settings),
            patch("narrare.writing.summary_deps.get_model_registry", return_value=fake_registry),
            patch("narrare.chapters.repository.ChapterRepository", return_value=fake_repo),
            patch("narrare.writing.summary_deps.get_composer", return_value=fake_composer),
            patch(
                "narrare.writing.summary_deps.get_invocation_pipeline",
                return_value=fake_invocation_pipeline,
            ),
        ):
            service = await get_summary_service(
                user_id=user_id,
                novel_id=novel_id,
                session=session,
            )

        assert isinstance(service, ChapterSummaryService)
        # ADR-086 L38 lazy contract: construction defers BOTH cascades —
        # zero routing resolves, zero token-limits resolves at wiring time.
        fake_resolver.resolve.assert_not_awaited()
        fake_limits_service.get_resolved_limits.assert_not_awaited()
        # Slice 3 wiring pin: the canonical KB-context provider (ADR-067) is
        # wired for the kb_characters / kb_locations / kb_factions /
        # kb_relationships prompt slots (render-live since the Slice 4
        # header activation; previously inert below the parse cutoff). Introspected via
        # the instance dict — direct private-attribute access would add a
        # reportPrivateUsage finding, and the type-ignore baseline is a
        # no-growth gate this slice must not extend.
        from narrare.kb._context_provider import KBContextProvider

        provider = vars(service)["_kb_context_provider"]
        assert isinstance(provider, KBContextProvider)
