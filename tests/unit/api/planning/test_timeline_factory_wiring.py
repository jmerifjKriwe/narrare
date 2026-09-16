"""Wiring pins for the timeline service factories — LAZY model routing
(ADR-086 L22/L23).

Pins that ``get_timeline_analysis_service`` and
``get_timeline_consistency_service`` wire the per-user PLAN cascade as a
``LazyModelResolution`` — resolving NOTHING and querying NOVELS at
construction time (the eager factories resolved and ran their uid-scoped
novel guard at wiring time; both moved to the services' first use —
ADR-086 regression contract #1 and the planning guard ruling).

Construction-time neutrality is pinned against BOTH eager-world failure
modes: an erroring resolver and a missing novel must not prevent
construction — the graceful swallow and the 404 guard are first-use
policy now (see ``test_timeline_analysis_lazy_resolution.py`` /
``test_timeline_consistency_lazy_resolution.py``).

Mirrors ``test_service_factory_wiring.py`` (ADR-086 L21 convention).
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

from narrare.planning._timeline_analysis_factory import get_timeline_analysis_service
from narrare.planning._timeline_consistency_factory import get_timeline_consistency_service
from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare.planning.timeline_consistency_service import TimelineConsistencyService
from narrare_core.shared.errors import ConfigurationError
from tests.unit.planning._timeline_test_helpers import make_resolved_model

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator

    from sqlalchemy.ext.asyncio import AsyncSession


class _FakeSession:
    """Inert session stand-in — the real repositories are patched out."""


class _FakeNovelRepository:
    """Fake NovelRepository returning a seeded novel (or None); counts."""

    def __init__(self, novel: object | None = None) -> None:
        self._novel = novel
        self.get_by_id_calls = 0

    async def get_by_id(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        self.get_by_id_calls += 1
        return self._novel


class _FakeResolver:
    """Fake model routing resolver — records args; canned result/error."""

    def __init__(self, resolved: object | None = None, error: Exception | None = None) -> None:
        self._resolved = resolved
        self._error = error
        self.calls: list[tuple[object, object, object]] = []

    async def resolve(self, intent: object, user_id: object, novel_id: object) -> object:
        self.calls.append((intent, user_id, novel_id))
        if self._error is not None:
            raise self._error
        return self._resolved


def _patch_analysis_env(
    stack: ExitStack,
    novel: object,
    *,
    resolver: _FakeResolver,
) -> _FakeNovelRepository:
    """Enter all analysis-factory dependency patches onto the stack."""

    def novel_repo_factory(_session: object) -> _FakeNovelRepository:
        return _FakeNovelRepository(novel=novel)

    fakery = {
        "NovelRepository": novel_repo_factory,
        "ChapterRepository": lambda _s: object(),
        "TimelineEventRepository": lambda _s: object(),
        "get_model_routing_resolver": lambda _s: resolver,
        "get_model_registry": lambda: object(),
        "get_composer": lambda: object(),
        "get_invocation_pipeline": lambda: object(),
    }
    for attr, replacement in fakery.items():
        stack.enter_context(
            patch(f"narrare.planning._timeline_analysis_factory.{attr}", replacement)
        )
    # The KB-context provider is imported inside the factory function —
    # patch at the source modules (ADR-067 wiring, provider-independent).
    stack.enter_context(
        patch("narrare.kb._context_provider.KBContextProvider", lambda **_kw: object())
    )
    stack.enter_context(patch("narrare.kb.repository.KBRepository", lambda _s: object()))
    stack.enter_context(
        patch("narrare.kb.relationship_repository.RelationshipRepository", lambda _s: object())
    )
    return novel_repo_factory(None)


def _patch_consistency_env(
    stack: ExitStack,
    novel: object,
    *,
    resolver: _FakeResolver,
) -> _FakeNovelRepository:
    """Enter all consistency-factory dependency patches onto the stack."""

    def novel_repo_factory(_session: object) -> _FakeNovelRepository:
        return _FakeNovelRepository(novel=novel)

    fakery = {
        "NovelRepository": novel_repo_factory,
        "TimelineEventRepository": lambda _s: object(),
        "CharacterAgeService": lambda **_kw: object(),
        "get_model_routing_resolver": lambda _s: resolver,
        "get_model_registry": lambda: object(),
        "get_composer": lambda: object(),
        "get_invocation_pipeline": lambda: object(),
    }
    for attr, replacement in fakery.items():
        stack.enter_context(
            patch(f"narrare.planning._timeline_consistency_factory.{attr}", replacement)
        )
    stack.enter_context(patch("narrare.kb.repository.KBRepository", lambda _s: object()))
    return novel_repo_factory(None)


def _wiring_cases() -> Iterator[
    tuple[
        str,
        Callable[
            [AsyncSession, str, uuid.UUID],
            Awaitable[TimelineAnalysisService | TimelineConsistencyService],
        ],
        Callable[..., _FakeNovelRepository],
    ]
]:
    """Yield (label, factory, env-patcher) for both timeline factories."""
    yield "analysis", get_timeline_analysis_service, _patch_analysis_env
    yield "consistency", get_timeline_consistency_service, _patch_consistency_env


class TestTimelineFactoriesLazyWiring:
    """Both timeline factories: lazy wiring — nothing runs at construction."""

    async def test_no_resolution_at_construction(self) -> None:
        """Factory entry runs ZERO cascades and issues ZERO novel queries.

        The eager factories ran the uid-scoped novel guard + the PLAN
        cascade at wiring time; both move to the services' first use
        (guard preserved per the planning guard ruling — asserted at
        service level in the per-service lazy-resolution tests).
        """
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        for _label, factory, patch_env in _wiring_cases():
            resolver = _FakeResolver(resolved=make_resolved_model())
            with ExitStack() as stack:
                novel_repo = patch_env(
                    stack,
                    MagicMock(spec=["id"]),
                    resolver=resolver,
                )
                service = await factory(
                    cast("AsyncSession", _FakeSession()), str(user_id), novel_id
                )

            assert len(resolver.calls) == 0, "routing cascade must not run at construction"
            assert novel_repo.get_by_id_calls == 0, (
                "uid-scoped novel guard must not run at construction (moved to "
                "the service's first use — planning guard ruling)"
            )
            assert isinstance(service, TimelineAnalysisService | TimelineConsistencyService)

    async def test_factory_wires_lazy_resolution_with_eager_args(self) -> None:
        """The wired lazy resolution resolves the SAME PLAN cascade with
        the SAME args the eager factories used verbatim (intent, uid,
        novel_id — timing-only, RULE-18)."""
        from narrare_core.llm.intents import LLMIntent

        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        uid = uuid.UUID(str(user_id))
        for _label, factory, patch_env in _wiring_cases():
            resolver = _FakeResolver(resolved=make_resolved_model())
            with ExitStack() as stack:
                patch_env(stack, MagicMock(spec=["id"]), resolver=resolver)
                service = await factory(
                    cast("AsyncSession", _FakeSession()), str(user_id), novel_id
                )

            assert service._model_resolution is not None
            await service._model_resolution.resolve()

            assert len(resolver.calls) == 1
            intent, called_uid, called_novel_id = resolver.calls[0]
            assert intent is LLMIntent.PLAN
            assert called_uid == uid
            assert called_novel_id == novel_id

    async def test_factory_constructs_when_resolver_would_fail(self) -> None:
        """An erroring resolver does not prevent construction — the eager
        factories' wiring-time graceful swallow is first-use policy now,
        so construction is neutral (0 cascade attempts)."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        for _label, factory, patch_env in _wiring_cases():
            resolver = _FakeResolver(error=ConfigurationError("no provider"))
            with ExitStack() as stack:
                patch_env(stack, MagicMock(spec=["id"]), resolver=resolver)
                service = await factory(
                    cast("AsyncSession", _FakeSession()), str(user_id), novel_id
                )

            assert len(resolver.calls) == 0
            assert isinstance(service, TimelineAnalysisService | TimelineConsistencyService)

    async def test_factory_constructs_without_novel_query_for_missing_novel(self) -> None:
        """A missing novel does not prevent construction — the eager
        factories' wiring-time 404 guard is first-use policy now, so
        construction issues no novel query at all."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        for _label, factory, patch_env in _wiring_cases():
            with ExitStack() as stack:
                novel_repo = patch_env(stack, None, resolver=_FakeResolver(make_resolved_model()))
                service = await factory(
                    cast("AsyncSession", _FakeSession()), str(user_id), novel_id
                )

            assert novel_repo.get_by_id_calls == 0
            assert isinstance(service, TimelineAnalysisService | TimelineConsistencyService)
