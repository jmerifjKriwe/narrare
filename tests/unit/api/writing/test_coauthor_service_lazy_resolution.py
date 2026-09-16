"""Lazy service-level semantics for CoAuthorService (ADR-086 L31).

Validate-seam half of the L31 service-level lazy contract (the
first-use composition + SET-005 pins live in
``test_coauthor_lazy_first_use.py``; the factory-level wiring pins in
``test_deps_coauthor_lazy_wiring.py``). The factory
(``writing/deps_coauthor.py::get_coauthor_service``) wires a
``LazyModelResolution`` plus a deferred runtime composition (M-budget):
the routing cascade AND the token-limits cascade resolve together with
the sampling/budget/pipeline composition at the service's FIRST use.
This file pins the lazy contract at the service seams:

- ``validate_coauthor`` — the router's pre-stream seam — is a first-use
  site, so ``ConfigurationError`` surfaces as a pre-header 400
  (RULE-11 — AI-mandatory SSE endpoint) and never after headers;
- the chapter-ownership gate (IDOR S6), selection/focus validation, and
  the active-generation conflict check run FIRST — the cascades are
  NEVER invoked when they fail.

Mirrors ``tests/unit/api/writing/test_rewrite_service_lazy_resolution.py``
(ADR-086 L33 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing._coauthor_support import CoAuthorRuntime
from narrare.writing.coauthor_service import CoAuthorService
from narrare.writing.schemas_coauthor import CoAuthorFocus, CoAuthorRequest
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import ConfigurationError, NotFoundError, ValidationError
from tests.factories import make_chapter, make_novel

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_SELECTION = (
    "This is a sufficiently long selection text that demonstrates the "
    "co-author service lazy resolution flow. It needs to exceed fifty "
    "characters to satisfy the min_length constraint on CoAuthorRequest."
)


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


class _RaisingRuntimeFactory:
    """Fake runtime factory — the first-use composition finds no provider."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self) -> CoAuthorRuntime:
        self.calls += 1
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


def _runtime(
    pipeline: MagicMock | None = None,
    config: ResolvedModelConfig | None = None,
) -> CoAuthorRuntime:
    """A canned first-use runtime (composed config + pipeline)."""
    return CoAuthorRuntime(
        config=config or ResolvedModelConfig(provider_name="t", model_id="m"),
        api_key=None,
        base_url=None,
        pipeline=pipeline or MagicMock(spec=["generate"], name="pipeline"),
        max_selection_words=2000,
    )


def _static_runtime_factory(
    runtime: CoAuthorRuntime,
) -> tuple[Callable[[], Awaitable[CoAuthorRuntime]], list[int]]:
    """An async runtime factory returning a fixed runtime; counts calls."""
    calls: list[int] = []

    async def runtime_factory() -> CoAuthorRuntime:
        calls.append(1)
        return runtime

    return runtime_factory, calls


def _request(**kw: Any) -> CoAuthorRequest:
    """Create a CoAuthorRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "selection_text": _SELECTION,
        "focus": [CoAuthorFocus.WORD_CHOICE],
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return CoAuthorRequest(**defaults)


def _gate_open_repos() -> tuple[AsyncMock, AsyncMock]:
    """Chapter/novel repo mocks with the S6 ownership gate open."""
    chapter_repo = AsyncMock(spec=["get"])
    chapter_repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    novel_repo = AsyncMock(spec=["get_by_id"])
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return chapter_repo, novel_repo


# ---------------------------------------------------------------------------
# Service-level lazy contract
# ---------------------------------------------------------------------------


class TestLazyServiceContract:
    """The service composes its runtime lazily, once, post-validation."""

    def _make_service(
        self,
        runtime_factory: Callable[[], Awaitable[CoAuthorRuntime]],
        repo: AsyncMock | None = None,
        chapter_repo: AsyncMock | None = None,
        novel_repo: AsyncMock | None = None,
    ) -> CoAuthorService:
        gate_chapter_repo, gate_novel_repo = _gate_open_repos()
        default_repo = AsyncMock(spec=["get_active_for_chapter"])
        default_repo.get_active_for_chapter = AsyncMock(return_value=None)
        return CoAuthorService(
            repo=repo or default_repo,
            runtime_factory=runtime_factory,
            draft_processor=MagicMock(spec=["process"]),
            chapter_repo=chapter_repo or gate_chapter_repo,
            novel_repo=novel_repo or gate_novel_repo,
        )

    async def test_no_composition_at_construction(self) -> None:
        """Construction must not invoke the runtime factory — both
        cascades and the pipeline composition stay idle until first use."""
        _factory, calls = _static_runtime_factory(_runtime())

        self._make_service(_factory)

        assert calls == []

    async def test_ensure_resolved_composes_once_and_is_idempotent(self) -> None:
        """First use composes exactly once; repeat calls hit the cache."""
        runtime = _runtime()
        factory, calls = _static_runtime_factory(runtime)
        service = self._make_service(factory)

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert calls == [1]
        assert first is second
        assert first is runtime

    async def test_validate_coauthor_is_a_first_use_site(self) -> None:
        """The pre-stream seam composes the runtime exactly once."""
        factory, calls = _static_runtime_factory(_runtime())
        chapter_repo, novel_repo = _gate_open_repos()
        repo = AsyncMock(spec=["get_active_for_chapter"])
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        service = self._make_service(
            factory, repo=repo, chapter_repo=chapter_repo, novel_repo=novel_repo
        )

        await service.validate_coauthor(uuid4(), uuid4(), _request(), user_id=str(uuid4()))

        assert calls == [1]

    async def test_configuration_error_propagates_from_validate_coauthor(self) -> None:
        """RULE-11 / ADR-086: the composition's ``ConfigurationError``
        (unconfigured provider) propagates from the pre-stream seam —
        the service never swallows it, so the SSE router's existing
        ``validate_coauthor`` call keeps the 400 BEFORE any headers."""
        raising = _RaisingRuntimeFactory()
        service = self._make_service(raising)

        with pytest.raises(ConfigurationError):
            await service.validate_coauthor(uuid4(), uuid4(), _request(), user_id=str(uuid4()))

        assert raising.calls == 1

    async def test_selection_validation_prevents_composition(self) -> None:
        """Empty ``selection_text`` fails validation BEFORE the runtime
        factory runs — the cascades are never invoked (validation-first,
        the eager world's gate ordering is preserved)."""
        _factory, calls = _static_runtime_factory(_runtime())
        service = self._make_service(_factory)

        with pytest.raises(ValidationError, match="selection_text must not be empty"):
            await service.validate_coauthor(
                uuid4(), uuid4(), _request(selection_text=" " * 60), user_id=str(uuid4())
            )

        assert calls == []

    async def test_focus_validation_prevents_composition(self) -> None:
        """An empty ``focus`` list fails validation BEFORE the runtime
        factory runs (defensive MISSING_INPUT check precedes resolution)."""
        _factory, calls = _static_runtime_factory(_runtime())
        service = self._make_service(_factory)
        req = CoAuthorRequest.model_construct(
            selection_text=_SELECTION,
            focus=[],
            tone="balanced",
            language="en",
        )

        with pytest.raises(ValidationError, match="focus must contain at least one area"):
            await service.validate_coauthor(uuid4(), uuid4(), req, user_id=str(uuid4()))

        assert calls == []

    async def test_ownership_gate_stays_ahead_of_composition(self) -> None:
        """An unknown chapter is rejected with ``NotFoundError`` and the
        runtime factory is NEVER invoked — the IDOR S6 gate precedes
        resolution (MUST-NOT-change list)."""
        _factory, calls = _static_runtime_factory(_runtime())
        broken_chapter_repo = AsyncMock(spec=["get"])
        broken_chapter_repo.get = AsyncMock(return_value=None)
        service = self._make_service(
            _factory, chapter_repo=broken_chapter_repo, novel_repo=AsyncMock(spec=["get_by_id"])
        )

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.validate_coauthor(uuid4(), uuid4(), _request(), user_id=str(uuid4()))

        assert calls == []

    async def test_active_generation_conflict_prevents_composition(self) -> None:
        """A concurrently active generation raises ``ConflictError``
        before the cascades run (conflict check precedes resolution)."""
        from narrare_core.shared.errors import ConflictError

        _factory, calls = _static_runtime_factory(_runtime())
        repo = AsyncMock(spec=["get_active_for_chapter"])
        repo.get_active_for_chapter = AsyncMock(return_value=uuid4())
        service = self._make_service(_factory, repo=repo)

        with pytest.raises(ConflictError, match="already active"):
            await service.validate_coauthor(uuid4(), uuid4(), _request(), user_id=str(uuid4()))

        assert calls == []
