"""Item E — WS tier-budget threading tests.

Defect (a3da2823 follow-up): every WS writing turn budgeted with Core
defaults (``WsWritingContextAssembler()`` bare) while the HTTP writing
factories thread ``limits.tier_percentages`` (FIND-012) plus the
ADR-082 model-capped ``writing_tier_base`` (``resolve_context_budgets``)
into their pipelines — WS tiering drifted from HTTP tiering.

Fix under test here:

1. Assembler contract — ``WsWritingContextAssembler`` construction with
   threaded values governs the real assembly (percentages applied,
   content truncated to the overridden immediate share); bare
   construction keeps the Core defaults (RULE-11 baseline).
2. Factory wiring — ``build_writing_session_handler`` resolves the
   budgets at handler build from the handshake ``limits`` and threads
   them into the turn service's assembler; ``limits=None`` keeps the
   pre-item-E wiring exactly.

Extraction note (RULE-04): these cases were first appended to
``test_ws_context_assembler.py`` / ``test_ws_turn_prompt_supply.py``
and were modularized when both hit the 400-line test hard limit —
moved verbatim, not compressed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.context.budget import TokenBudgetManager
from narrare_core.llm import ModelRegistry, ResolvedModelConfig
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import PromptComposer
from narrare_core.writing.context_assembler import WritingContextAssembler

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.settings.token_limits.contracts import TokenLimitOverrides
    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_handler import WritingSessionHandler
    from narrare.writing.ws_session_control_service import WritingSessionControlService
    from narrare_core.writing.session_manager import SessionManager
    from narrare_core.writing.session_turn_state import SessionTurnStateStore

_CHAPTER_ID = uuid4()
_PROJECT_ID = uuid4()


# ---------------------------------------------------------------------------
# Minimal doubles — the budget paths need only the chapter fetch; the
# assembler tests use ``project_id=None`` so no project-scoped repos run.
# ---------------------------------------------------------------------------


def _oversized_chapter(chapter_id: object) -> SimpleNamespace:
    """Chapter double whose content exceeds any small test budget."""
    return SimpleNamespace(
        id=chapter_id,
        title="Chapter 5",
        content="word " * 4_000,
        summary="summary",
        position=5,
        timeline_position="",
    )


def _install_chapter_fetch(monkeypatch: pytest.MonkeyPatch, chapter: object) -> None:
    """Patch the assembler's session + chapter-repo seam."""

    class _ChapterRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get(self, chapter_id: object) -> object:
            return chapter

    async def _session_gen() -> AsyncIterator[object]:
        yield object()

    monkeypatch.setattr("narrare._app.database.get_async_session", _session_gen)
    monkeypatch.setattr("narrare.chapters.repository.ChapterRepository", _ChapterRepo)


# ---------------------------------------------------------------------------
# Assembler contract — threaded values govern assembly
# ---------------------------------------------------------------------------


class TestWsAssemblerBudgetThreading:
    """Resolved budgets passed at construction govern WS assembly.

    The factory threads ``limits.tier_percentages`` (FIND-012) and the
    ADR-082 ``writing_tier_base`` (model-capped) into the assembler so a
    WebSocket turn allocates tiers exactly like the HTTP writing paths.
    """

    async def test_threaded_budget_governs_assembly_tier_split(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An oversized chapter is truncated to the overridden immediate
        share — the threaded percentages (not Core defaults) allocated
        the budget during real assembly."""
        from narrare.writing.ws_context_assembler import WsWritingContextAssembler
        from narrare_core.writing._token_utils import default_token_counter

        overrides = {
            "immediate": 0.90,
            "recent": 0.05,
            "kb_referenced": 0.02,
            "kb_suggested": 0.02,
            "pinned": 0.01,
        }
        _install_chapter_fetch(monkeypatch, _oversized_chapter(_CHAPTER_ID))

        assembler = WsWritingContextAssembler(
            tier_overrides=overrides,
            total_budget=1_000,
        )
        context = await assembler.assemble(
            chapter_id=_CHAPTER_ID, project_id=None, mode="interactive_session"
        )

        # Immediate tier = 90% of the threaded 1_000-token budget.
        allocation = assembler.get_tier_allocation(first_chapter=False, mode="interactive_session")
        assert allocation["immediate"].percentage == pytest.approx(0.90)
        assert allocation["immediate"].token_limit == 900
        assert sum(t.percentage for t in allocation.values()) == pytest.approx(1.0)
        # The tier limit actually truncated the chapter content.
        assert context.total_budget_tokens == 1_000
        assert default_token_counter(context.chapter_content) <= 900
        assert context.chapter_content != "word " * 4_000

    async def test_default_construction_keeps_core_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bare construction (the historical WS wiring) keeps the Core
        default total and base tier distribution — the degradation
        baseline the factory falls back to (RULE-11)."""
        from narrare.writing.ws_context_assembler import WsWritingContextAssembler

        _install_chapter_fetch(
            monkeypatch,
            SimpleNamespace(
                id=_CHAPTER_ID,
                title="Chapter 5",
                content="content of pos 5",
                summary="summary",
                position=5,
                timeline_position="",
            ),
        )

        assembler = WsWritingContextAssembler()
        context = await assembler.assemble(
            chapter_id=_CHAPTER_ID, project_id=None, mode="interactive_session"
        )

        assert assembler.total_budget == TokenBudgetManager.DEFAULT_TOTAL_BUDGET
        assert context.total_budget_tokens == TokenBudgetManager.DEFAULT_TOTAL_BUDGET
        allocation = assembler.get_tier_allocation(first_chapter=False, mode="interactive_session")
        assert allocation["immediate"].percentage == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# Factory wiring — handshake limits → assembler budgets
# ---------------------------------------------------------------------------


def _handler_collaborators() -> tuple[
    SessionManager,
    ActiveTurnRegistry,
    SessionTurnStateStore,
    WritingSessionControlService,
]:
    """Real session-manager/control-service collaborators for the factory."""
    from narrare.writing._ws_cache import InMemorySessionCache
    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_session_control_service import (
        WritingSessionControlService,
    )
    from narrare_core.writing.session_manager import SessionManager
    from narrare_core.writing.session_turn_state import SessionTurnStateStore

    session_manager = SessionManager(cache=InMemorySessionCache())
    turn_state = SessionTurnStateStore()
    active_registry = ActiveTurnRegistry()
    control_service = WritingSessionControlService(
        session_manager=session_manager,
        turn_state=turn_state,
        registry=active_registry,
    )
    return session_manager, active_registry, turn_state, control_service


def _turn_service_assembler(handler: WritingSessionHandler) -> WritingContextAssembler:
    """Dig the assembler out of the built handler's turn service.

    ADR-086 L39: the assembler composes at first use — callers must
    ``ensure_resolved()`` on the turn service before digging.
    """
    turn_service = handler._message_router._direction_dispatcher._turn_service
    runtime = turn_service._runtime
    assert runtime is not None
    assembler = runtime.context_assembler
    assert isinstance(assembler, WritingContextAssembler)
    return assembler


def _build(
    monkeypatch: pytest.MonkeyPatch,
    *,
    config: ResolvedModelConfig,
    limits: TokenLimitOverrides | None = None,
) -> WritingSessionHandler:
    """Call ``build_writing_session_handler`` with the shared collaborators.

    ADR-086 L39: the factory wires lazily — the config reaches it as a
    static resolution; nothing resolves or composes at build time.
    """
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare.writing.ws_factory import build_writing_session_handler
    from narrare_core.llm.model_routing import ResolvedModel

    session_manager, active_registry, turn_state, control_service = _handler_collaborators()
    return build_writing_session_handler(
        session_manager=session_manager,
        registry=active_registry,
        turn_state=turn_state,
        control_service=control_service,
        model_registry=MagicMock(spec=ModelRegistry),
        composer=MagicMock(spec=PromptComposer),
        model_resolution=StaticModelResolution(ResolvedModel(config=config)),
        invocation_pipeline=MagicMock(spec=InvocationPipeline),
        run_limit_resolver=DefaultRunLimitResolver(),
        limits=limits,
    )


class TestWsFactoryBudgetWiring:
    """The factory defers budget composition to first use (ADR-086 L39)."""

    async def test_threads_resolved_tier_budgets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Resolved budgets reach the WS assembler at first use — the
        same tier allocations the HTTP factories hand to
        ``create_pipeline`` (FIND-012 overrides + writing_tier_base);
        nothing composes at handler build."""
        from narrare.settings.token_limits.contracts import TokenLimitOverrides
        from narrare.writing.ws_context_assembler import WsWritingContextAssembler
        from narrare_core.context.contracts import EffectiveContextBudgets

        config = ResolvedModelConfig(
            provider_name="test",
            model_id="test-model",
            temperature=0.7,
            max_tokens=2048,
        )
        limits = TokenLimitOverrides(
            output_limit=2048,
            tier_percentages={"immediate": 0.60},
            context_total_budget=48_000,
        )
        budgets = EffectiveContextBudgets(
            context_total=48_000,
            series_history=0,
            writing_tier_base=48_000,
            reserve_tokens=8_192,
            context_window=131_072,
            source="cascade:uncapped",
        )
        captured: dict[str, object] = {}

        def fake_resolve(**kwargs: object) -> EffectiveContextBudgets:
            captured.update(kwargs)
            return budgets

        monkeypatch.setattr(
            "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
            fake_resolve,
        )

        handler = _build(monkeypatch, config=config, limits=limits)
        assert captured == {}  # lazy: no composition at handler build

        turn_service = handler._message_router._direction_dispatcher._turn_service
        runtime = await turn_service.ensure_resolved()
        assembler = runtime.context_assembler
        assert isinstance(assembler, WsWritingContextAssembler)
        # Composition ran at first use with the handshake's exact inputs;
        # WS never injects {{series_history}} → standalone carve-out semantics.
        assert captured["limits"] is limits
        frozen = cast("ResolvedModelConfig", captured["config"])
        assert frozen.temperature == 0.7  # the frozen config
        assert frozen.max_tokens == 2048
        assert captured["series_in_scope"] is False
        # The resolved tier base + FIND-012 overrides govern WS allocation.
        assert assembler.total_budget == 48_000
        allocation = assembler.get_tier_allocation(first_chapter=False)
        assert allocation["immediate"].percentage == pytest.approx(0.60)
        assert allocation["immediate"].token_limit == 28_800

    async def test_unconfigured_tiers_degrade_to_core_allocations(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RULE-11: ``tier_percentages`` unset (the common cascade
        outcome) keeps the Core mode allocations while the resolved
        tier base still caps the budget."""
        from narrare.settings.token_limits.contracts import TokenLimitOverrides
        from narrare.writing.ws_context_assembler import WsWritingContextAssembler
        from narrare_core.context.contracts import EffectiveContextBudgets

        monkeypatch.setattr(
            "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
            lambda **kwargs: EffectiveContextBudgets(
                context_total=20_000,
                series_history=0,
                writing_tier_base=20_000,
                reserve_tokens=None,
                context_window=None,
                source="cascade:window_unknown",
            ),
        )

        handler = _build(
            monkeypatch,
            config=ResolvedModelConfig(
                provider_name="test",
                model_id="test-model",
                temperature=0.7,
                max_tokens=2048,
            ),
            limits=TokenLimitOverrides(output_limit=2048, context_total_budget=20_000),
        )
        turn_service = handler._message_router._direction_dispatcher._turn_service
        runtime = await turn_service.ensure_resolved()
        assembler = runtime.context_assembler

        assert isinstance(assembler, WsWritingContextAssembler)
        assert assembler.total_budget == 20_000
        allocation = assembler.get_tier_allocation(first_chapter=False)
        assert allocation["immediate"].percentage == pytest.approx(0.30)
        assert allocation["immediate"].token_limit == 6_000

    async def test_without_limits_keeps_core_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No handshake limits (legacy/test call sites) → bare assembler,
        exactly the pre-item-E wiring (RULE-11 baseline)."""

        def forbidden(**kwargs: object) -> object:
            raise AssertionError("resolve_context_budgets must not run without limits")

        monkeypatch.setattr(
            "narrare.settings.token_limits.context_budgets.resolve_context_budgets",
            forbidden,
        )

        handler = _build(
            monkeypatch,
            config=ResolvedModelConfig(
                provider_name="test",
                model_id="test-model",
                temperature=0.7,
                max_tokens=2000,
            ),
        )
        turn_service = handler._message_router._direction_dispatcher._turn_service
        runtime = await turn_service.ensure_resolved()
        assembler = runtime.context_assembler

        from narrare.writing.ws_context_assembler import WsWritingContextAssembler

        assert isinstance(assembler, WsWritingContextAssembler)
        assert assembler.total_budget == TokenBudgetManager.DEFAULT_TOTAL_BUDGET
        allocation = assembler.get_tier_allocation(first_chapter=False)
        assert allocation["immediate"].percentage == pytest.approx(0.30)
