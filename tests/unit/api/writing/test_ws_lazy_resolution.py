"""L39 (ADR-086) — WS writing-session lazy model resolution contract.

Entry 39 of the ADR-086 migration ledger: ``interactive_session`` resolved
the WRITE-intent routing cascade INLINE at session bootstrap
(``resolve_ws_session_config`` step 3) and froze the handshake config
(``temperature=0.7``, ``max_tokens=limits.output_limit``) before any turn
ran. The migration moves the model resolution to FIRST USE (the first
turn / first interview draft) behind the shared ``ModelResolution``
abstraction; the handshake wires a ``LazyModelResolution`` and returns it
instead of a frozen ``ResolvedModelConfig``.

Deliberate residual (documented, plan-accepted): the TOKEN-LIMITS cascade
stays at WS bootstrap — ``limits.ws_timeout`` feeds the handler idle
timeout and ``limits.tier_percentages`` the assembler overrides, both
structurally needed before the message loop starts. Timing-only move
(RULE-18): sources unchanged, gate-before-resolution preserved (the
ownership gate still runs at bootstrap, strictly before any resolve).

First-use error semantics: the WS endpoint has no request body to
validate, so the ADR's 422-preemption defect does not apply here; the
deferral removes the bootstrap resolve for connections that never turn
and lands an unconfigured provider as an in-band error frame (direction
stream generic-error branch / draft dispatch) instead of an abnormal
handshake close.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import ANY, AsyncMock, MagicMock, Mock
from uuid import uuid4

from narrare._app.config import Settings as AppSettings
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import ModelRegistry, ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import PromptComposer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import pytest

    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.writing.ws_turn_service import WritingTurnService

_USER_ID = "00000000-0000-0000-0000-000000000001"
_CHAPTER_ID = uuid4()
_PROJECT_ID = uuid4()


class CountingResolution:
    """ModelResolution double that counts resolve() calls (cache probe)."""

    def __init__(self, resolved: ResolvedModel) -> None:
        self._resolved = resolved
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._resolved


def _resolved_model() -> ResolvedModel:
    return ResolvedModel(
        config=ResolvedModelConfig(
            provider_name="test-provider",
            model_id="test-model",
            temperature=0.5,
            max_tokens=999,
        ),
        api_key="test-key",
        source="user_default",
    )


async def _session_gen_double(session: object) -> AsyncIterator[object]:
    yield session


async def _fake_stream(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    yield StreamChunk(text="ok", is_final=True, usage=TokenUsage(1, 2, 3))


def _patch_handshake(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, AsyncMock]:
    """Patch the handshake DB stack; return (resolver, token_limits_instance).

    The resolver's ``resolve`` is an AsyncMock — its call count is the
    bootstrap-vs-first-use evidence. The gate admits the caller via
    ownership-seeded repositories (IDOR S3 harness reuse).
    """
    from tests.unit.api.writing.ws_test_helpers import owned_project_repos

    resolver = MagicMock(spec=["resolve"])
    resolver.resolve = AsyncMock(return_value=_resolved_model())

    token_instance = AsyncMock()
    token_instance.get_resolved_limits = AsyncMock(return_value=_token_limits())

    novel_cls, chapter_cls = owned_project_repos(_PROJECT_ID)

    monkeypatch.setattr("narrare._app.config.get_settings", lambda: MagicMock(spec=AppSettings))
    monkeypatch.setattr(
        "narrare._app.database.get_async_session", lambda: _session_gen_double(object())
    )
    monkeypatch.setattr("narrare.novels.repository.NovelRepository", novel_cls)
    monkeypatch.setattr("narrare.chapters.repository.ChapterRepository", chapter_cls)
    monkeypatch.setattr(
        "narrare.settings.token_limits.service.TokenLimitsService",
        lambda **_kwargs: token_instance,
    )
    monkeypatch.setattr(
        "narrare._app.dependencies_services.get_model_routing_resolver",
        lambda _session: resolver,
    )
    return resolver, token_instance


def _token_limits() -> TokenLimitOverrides:
    from narrare.settings.token_limits.contracts import TokenLimitOverrides

    return TokenLimitOverrides(output_limit=2048, ws_timeout=900)


class TestHandshakeWiresLazy:
    """Bootstrap wires the resolution; the routing cascade does not run."""

    async def test_handshake_returns_resolution_without_resolving(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """resolve_ws_session_config returns (ModelResolution, limits) and
        the WRITE routing cascade has NOT run when the handshake returns."""
        from narrare._app.dependencies_services import ModelResolution
        from narrare.writing.ws_session_config import resolve_ws_session_config

        resolver, token_instance = _patch_handshake(monkeypatch)

        model_resolution, limits = await resolve_ws_session_config(
            _USER_ID, _CHAPTER_ID, _PROJECT_ID
        )

        assert isinstance(model_resolution, ModelResolution)
        assert limits.ws_timeout == 900
        # Token limits stay at bootstrap (accepted residual: ws_timeout +
        # tier overrides are structurally needed before the message loop).
        token_instance.get_resolved_limits.assert_awaited_once()
        # The routing cascade is DEFERRED — zero resolves at bootstrap.
        resolver.resolve.assert_not_awaited()

    async def test_first_use_resolves_exactly_once_and_freezes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First resolve() runs the WRITE cascade once and returns the
        routed model untouched (the freeze happens at composition —
        ``freeze_handshake_config``); the second resolve() is served from
        the cache."""
        from narrare.writing._ws_turn_support import freeze_handshake_config
        from narrare.writing.ws_session_config import resolve_ws_session_config

        resolver, _ = _patch_handshake(monkeypatch)

        model_resolution, limits = await resolve_ws_session_config(
            _USER_ID, _CHAPTER_ID, _PROJECT_ID
        )
        resolved_first = await model_resolution.resolve()
        resolved_second = await model_resolution.resolve()

        resolver.resolve.assert_awaited_once()
        call_args = resolver.resolve.await_args.args
        assert call_args[0].value == "write"  # LLMIntent.WRITE
        assert call_args[1] == ANY  # user uuid
        assert call_args[2] == ANY  # project uuid
        assert resolved_first is resolved_second
        # The handshake seam returns the ROUTED config unfrozen; the eager
        # freeze (temperature/max_tokens) is reproduced exactly once at
        # composition time by the shared support function.
        assert resolved_first.config.temperature == 0.5
        frozen = freeze_handshake_config(resolved_first.config, limits)
        assert frozen.temperature == 0.7
        assert frozen.max_tokens == limits.output_limit

    async def test_first_use_opens_its_own_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The lazy factory sources its OWN short-lived session at first
        use — the handshake session is already closed by then (no
        request-scoped session on a WebSocket connection)."""
        from narrare.writing import ws_session_config

        resolver, _ = _patch_handshake(monkeypatch)

        sessions_opened = 0

        def counting_session_gen() -> AsyncIterator[object]:
            nonlocal sessions_opened
            sessions_opened += 1
            return _session_gen_double(object())

        monkeypatch.setattr("narrare._app.database.get_async_session", counting_session_gen)

        model_resolution, _ = await ws_session_config.resolve_ws_session_config(
            _USER_ID, _CHAPTER_ID, _PROJECT_ID
        )
        opened_at_bootstrap = sessions_opened
        await model_resolution.resolve()

        # One session at bootstrap (gate + limits), one more at first use.
        assert opened_at_bootstrap == 1
        assert sessions_opened == 2
        resolver.resolve.assert_awaited_once()


class TestTurnServiceLazyRuntime:
    """The turn service composes its runtime at first use (idempotent)."""

    def _make_service(
        self,
        resolution: CountingResolution,
        limits: TokenLimitOverrides,
    ) -> tuple[WritingTurnService, Mock]:
        """WritingTurnService on the production composition closure."""
        from narrare.writing._ws_turn_support import build_turn_runtime_factory
        from narrare.writing.ws_turn_service import WritingTurnService
        from tests.unit.api.writing._ws_turn_fakes import RecordingComposer

        composer = RecordingComposer()
        registry = Mock()
        registry.stream = Mock(side_effect=_fake_stream)
        service = WritingTurnService(
            composer=cast("PromptComposer", composer),
            invocation_pipeline=InvocationPipeline(),
            registry=cast("ModelRegistry", registry),
            runtime_factory=build_turn_runtime_factory(
                model_resolution=cast("CountingResolution", resolution),
                limits=limits,
            ),
            run_limit_resolver=DefaultRunLimitResolver(),
        )
        return service, registry

    async def test_ctor_runs_no_resolution_first_turn_resolves_once(self) -> None:
        """Neither service construction nor closure wiring resolves; the
        cascade runs exactly once, at the first turn."""
        resolution = CountingResolution(_resolved_model())
        service, _ = self._make_service(resolution, _token_limits())
        assert resolution.calls == 0

        chunks = [
            chunk
            async for chunk in service.stream_turn(
                content="Continue the scene.",
                session_mode="interactive_session",
                user_id=uuid4(),
                project_id=_PROJECT_ID,
                chapter_id=_CHAPTER_ID,
                session_id=uuid4(),
            )
        ]
        assert any(chunk.text for chunk in chunks)
        assert resolution.calls == 1

    async def test_stream_turn_streams_with_frozen_config(self) -> None:
        """registry.stream receives the frozen handshake config."""
        resolution = CountingResolution(_resolved_model())
        limits = _token_limits()
        service, registry = self._make_service(resolution, limits)

        async for _ in service.stream_turn(
            content="Continue the scene.",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=_PROJECT_ID,
            chapter_id=_CHAPTER_ID,
            session_id=uuid4(),
        ):
            pass

        stream_kwargs = registry.stream.call_args.kwargs
        config = stream_kwargs["config"]
        assert config.temperature == 0.7
        assert config.max_tokens == limits.output_limit

    async def test_ensure_resolved_is_idempotent(self) -> None:
        """ensure_resolved composes the runtime once; a second call and a
        subsequent turn reuse it (one resolution per connection)."""
        resolution = CountingResolution(_resolved_model())
        service, _ = self._make_service(resolution, _token_limits())

        runtime_first = await service.ensure_resolved()
        runtime_second = await service.ensure_resolved()
        assert runtime_first is runtime_second
        assert resolution.calls == 1

        async for _ in service.stream_turn(
            content="Continue.",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=_PROJECT_ID,
            chapter_id=_CHAPTER_ID,
            session_id=uuid4(),
        ):
            pass
        assert resolution.calls == 1


class TestFactoryDefersBudgets:
    """Handler build resolves nothing; budgets compose at first use."""

    async def test_handler_build_runs_no_resolution_budgets_at_first_turn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build_writing_session_handler wires lazily — no resolve, no
        budget composition at build time; both run at the first turn."""
        from narrare.settings.token_limits import context_budgets
        from tests.unit.api.writing.test_ws_budget_threading import (
            _handler_collaborators,
        )

        resolution = CountingResolution(_resolved_model())
        session_manager, active_registry, turn_state, control_service = _handler_collaborators()

        budget_calls: list[dict[str, object]] = []
        real_resolve_budgets = context_budgets.resolve_context_budgets

        def counting_resolve_budgets(
            *,
            limits: TokenLimitOverrides,
            config: ResolvedModelConfig,
            series_in_scope: bool,
        ) -> object:
            budget_calls.append(
                {"limits": limits, "config": config, "series_in_scope": series_in_scope}
            )
            return real_resolve_budgets(
                limits=limits, config=config, series_in_scope=series_in_scope
            )

        monkeypatch.setattr(
            context_budgets,
            "resolve_context_budgets",
            counting_resolve_budgets,
        )

        from narrare.writing.ws_factory import build_writing_session_handler

        handler = build_writing_session_handler(
            session_manager=session_manager,
            registry=active_registry,
            turn_state=turn_state,
            control_service=control_service,
            model_registry=MagicMock(spec=ModelRegistry),
            composer=MagicMock(spec=PromptComposer),
            model_resolution=cast("CountingResolution", resolution),
            invocation_pipeline=MagicMock(spec=InvocationPipeline),
            run_limit_resolver=DefaultRunLimitResolver(),
            limits=_token_limits(),
        )

        assert resolution.calls == 0
        assert budget_calls == []

        turn_service = handler._message_router._direction_dispatcher._turn_service
        await turn_service.ensure_resolved()

        assert resolution.calls == 1
        assert len(budget_calls) == 1
        frozen = cast("ResolvedModelConfig", budget_calls[0]["config"])
        assert frozen.temperature == 0.7
        assert frozen.max_tokens == 2048
        assert budget_calls[0]["series_in_scope"] is False
