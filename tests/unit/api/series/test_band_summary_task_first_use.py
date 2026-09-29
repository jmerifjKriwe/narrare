"""L25 background-task invariant + service first-use contract (ADR-086).

Plan §3 entry 25 / §9 risk 2, pinned explicitly: the band-summary factory's
lazy closure must capture the in-process task's OWN session-bound resolver,
and first use must happen at task runtime while that session is still open.
Also pins the SERVICE-side contract:

- ``generate`` is the first-use seam — exactly one composition, cached
  across entry points,
- ``ConfigurationError`` propagates un-swallowed from ``generate``
  (RULE-11: the first-use resolve deliberately runs OUTSIDE the service's
  ``WritingError`` wrapper, preserving the eager world's loud 400),
- non-AI entry points (``get`` / ``update_override`` / cache-hit
  ``get_or_generate``) never resolve at all.

Factory-side wiring pins live in ``test_band_summary_lazy_resolution.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.series._band_summary_support import BandSummaryModelRuntime
from narrare.series.band_summary_service import BandSummaryService
from narrare_core.shared.errors import ConfigurationError
from tests.factories import make_chapter, make_novel
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository

from ._band_summary_test_helpers import (
    BandSummaryLazyWiringHarness,
    FakeBandSummaryAgent,
    FakeBandSummaryComposer,
    FakeBandSummaryRegistry,
    make_band_summary_config,
    make_resolved_model,
)

pytestmark = pytest.mark.asyncio

if TYPE_CHECKING:
    from narrare_core.llm.model_routing import ResolvedModel


class _StopResolution(BaseException):
    """Sentinel short-circuiting the task at the resolution point.

    ``BaseException`` (not ``Exception``) so the task runner's broad
    ``except Exception`` rollback wrapper cannot swallow it.
    """


class _FakeOpenState:
    """Boolean cell recording a fake session's open state."""

    def __init__(self) -> None:
        self.open = True


# ---------------------------------------------------------------------------
# L25 background-task invariant: closure captures the task session; first
# use happens before session close.
# ---------------------------------------------------------------------------


class TestBackgroundTaskSessionInvariant:
    """Plan §3 entry 25 / §9 risk 2 — pinned explicitly."""

    async def test_lazy_closure_captures_task_session_and_resolves_while_open(self) -> None:
        """The closure must resolve through THE session-bound resolver of this
        build call, only while that session is open — and never after close
        (cached)."""
        session = MagicMock(spec=AsyncSession, name="task-session")
        open_state = _FakeOpenState()
        resolve_log: list[bool] = []

        async def _resolve(intent: Any, uid: Any, nid: Any) -> ResolvedModel:
            resolve_log.append(open_state.open)
            return make_resolved_model()

        async with BandSummaryLazyWiringHarness(resolver=SimpleNamespace(resolve=_resolve)):
            service = await _build_with_session(session)
            assert resolve_log == []  # nothing resolved at build (task wiring)

            await service.ensure_resolved()
            assert resolve_log == [True]  # first use — session still open

            open_state.open = False  # simulate task-session close
            await service.ensure_resolved()

        assert resolve_log == [True]  # cached: no resolution after close

    async def test_inprocess_task_first_use_happens_before_session_close(self) -> None:
        """Full-task pin: ``generate_band_summary_inprocess`` builds the
        service inside its own session and the FIRST cascade run happens at
        task runtime while that session is still open — the sentinel escapes
        through the rollback wrapper (BaseException) and the session closes
        afterwards."""
        from narrare.series import tasks as series_tasks

        session_state = _FakeOpenState()
        resolve_log: list[bool] = []

        class _FakeCtxSession:
            async def __aenter__(self) -> _FakeCtxSession:
                session_state.open = True
                return self

            async def __aexit__(self, *exc: object) -> bool:
                session_state.open = False
                return False

        async def _resolve(intent: Any, uid: Any, nid: Any) -> ResolvedModel:
            resolve_log.append(session_state.open)
            raise _StopResolution()

        fake_novel = SimpleNamespace(user_id=uuid4())
        fake_novel_repo = MagicMock(spec=["get"], name="NovelRepository")
        fake_novel_repo.get = AsyncMock(return_value=fake_novel)

        with (
            patch(
                "narrare._app.database.get_session_factory",
                return_value=lambda: _FakeCtxSession(),
            ),
            patch("narrare.novels.repository.NovelRepository", return_value=fake_novel_repo),
            pytest.raises(_StopResolution),
        ):
            async with BandSummaryLazyWiringHarness(resolver=SimpleNamespace(resolve=_resolve)):
                await series_tasks.generate_band_summary_inprocess(uuid4())

        assert resolve_log == [True]  # resolved exactly once, session open
        assert session_state.open is False  # session closed after the task


def _build_with_session(session: Any) -> Any:
    """Build via the shared builder, pinned to the given (task) session."""
    from narrare.series.dependencies_band_summary import build_band_summary_service

    return build_band_summary_service(session, uuid4(), uuid4())


# ---------------------------------------------------------------------------
# Service-level first-use contract (BandSummaryService)
# ---------------------------------------------------------------------------


class _CountingRuntimeFactory:
    """Fake deferred composition — counts invocations, returns one runtime."""

    def __init__(self, runtime: BandSummaryModelRuntime) -> None:
        self._runtime = runtime
        self.calls = 0

    async def __call__(self) -> BandSummaryModelRuntime:
        self.calls += 1
        return self._runtime


class _RaisingRuntimeFactory:
    """Fake deferred composition — the routing cascade finds no provider."""

    async def __call__(self) -> BandSummaryModelRuntime:
        raise ConfigurationError("No AI provider configured.", code="NO_AI_PROVIDER")


def _make_lazy_service(
    runtime_factory: Any,
) -> tuple[BandSummaryService, FakeBandSummaryAgent, FakeBandSummaryRepository, Any]:
    """A BandSummaryService wired with fakes + the injected lazy seam.

    Returns ``(service, agent, repo, novel_id)`` — ``novel_id`` is the
    seeded novel the ``generate`` nodes must target.
    """
    novel_id = uuid4()
    novel_repo = FakeNovelRepository()
    novel_repo.seed(make_novel(id=novel_id, title="The Forbidden Vale", genre="Fantasy"))
    chapter_repo = FakeChapterRepository()
    chapter_repo.seed(
        make_chapter(novel_id=novel_id, position=1, summary="Hero arrives."),
        make_chapter(novel_id=novel_id, position=2, summary="Secret revealed."),
    )
    repo = FakeBandSummaryRepository()
    agent = FakeBandSummaryAgent()

    def _agent_factory(model: Any, system_prompt: Any = None) -> FakeBandSummaryAgent:
        del system_prompt
        agent.last_model = model
        return agent

    service = BandSummaryService(
        repo=cast("Any", repo),
        novel_repo=cast("Any", novel_repo),
        chapter_repo=cast("Any", chapter_repo),
        registry=cast("Any", FakeBandSummaryRegistry()),
        model_runtime_factory=cast("Any", runtime_factory),
        composer=cast("Any", FakeBandSummaryComposer()),
        agent_factory=cast("Any", _agent_factory),
    )
    return service, agent, repo, novel_id


class TestServiceLazyContract:
    """First-use semantics at the BandSummaryService boundary."""

    async def test_generate_resolves_exactly_once_and_is_idempotent(self) -> None:
        """``generate`` is the first-use seam; the composition is cached for
        repeat generations."""
        counting = _CountingRuntimeFactory(
            BandSummaryModelRuntime(config=make_band_summary_config(), api_key=None, base_url=None)
        )
        service, agent, _repo, novel_id = _make_lazy_service(counting)

        await service.generate(novel_id)
        assert counting.calls == 1
        assert agent.run_count == 1

        await service.generate(novel_id)
        assert counting.calls == 1  # cached across entry points
        assert agent.run_count == 2

    async def test_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: an unconfigured provider surfaces as the loud
        ``ConfigurationError`` from ``generate`` — NOT wrapped into the
        service's ``WritingError`` (the first-use resolve deliberately runs
        OUTSIDE the generation try-wrapper, preserving the eager world's 400)."""
        service, _agent, _repo, novel_id = _make_lazy_service(_RaisingRuntimeFactory())

        with pytest.raises(ConfigurationError) as excinfo:
            await service.generate(novel_id)

        assert excinfo.value.code == "NO_AI_PROVIDER"

    async def test_non_ai_entry_points_never_resolve(self) -> None:
        """``get`` / ``update_override`` / cache-hit ``get_or_generate`` consume
        no resolution at all (post-migration improvement: the eager factory
        resolved for them too)."""
        counting = _CountingRuntimeFactory(
            BandSummaryModelRuntime(config=make_band_summary_config(), api_key=None, base_url=None)
        )
        service, _agent, repo, novel_id = _make_lazy_service(counting)
        await repo.set_override(novel_id, "An override row.")

        await service.get(novel_id)
        await service.update_override(novel_id, "New override")
        await service.get_or_generate(novel_id)  # override present → no generate
        await service.update_override(novel_id, None)  # clear — still no resolution

        assert counting.calls == 0
