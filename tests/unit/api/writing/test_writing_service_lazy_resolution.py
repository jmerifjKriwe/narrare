"""Lazy service-level semantics for WritingService (ADR-086 L37).

Service-level half of the L37 lazy contract (the factory-level wiring
pins live in ``test_deps_writing_lazy_wiring.py``). The factory
(``writing/deps_writing.py::get_writing_service``) wires a
``LazyModelResolution`` plus a deferred runtime composition (M-budget):
the intent routing cascade AND the token-limits cascade resolve
together with the sampling/budget/pipeline composition at the service's
FIRST use. This file pins the lazy contract at the service seams:

- ``validate_request_access`` — the router's pre-stream seam — is a
  first-use site, so ``ConfigurationError`` surfaces as a pre-header
  400 (RULE-11 — AI-mandatory SSE endpoint) and never after headers;
- the request-row ownership gate (IDOR S6, ``get_validated_request``)
  runs FIRST — the cascades are NEVER invoked when it fails;
- the eager factory's composition (``replace(resolved.config,
  temperature=0.7, max_tokens=limits.output_limit)`` + the SUGGEST
  override, verbatim credentials, tier-wired pipeline, ADR-082
  series-history ceiling) is reproduced exactly once at first use —
  WHAT unchanged, only WHEN.

Mirrors ``tests/unit/api/writing/test_style_variant_service_lazy_resolution.py``
(ADR-086 L35 precedent).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing._writing_support import WritingRuntime
from narrare.writing.service import WritingService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.shared.errors import ConfigurationError, NotFoundError
from narrare_core.writing.draft_processor import DraftProcessor
from tests.factories import make_novel

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

USAGE = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)

_CASCADE_CONFIG = ResolvedModelConfig(
    provider_name="zai",
    model_id="glm-4.7",
    temperature=0.7,
    max_tokens=1500,
)


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


class _RaisingRuntimeFactory:
    """Fake runtime factory — the first-use composition finds no provider."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self) -> WritingRuntime:
        self.calls += 1
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


def _runtime(
    pipeline: Any = None,
    config: ResolvedModelConfig | None = None,
    *,
    series_history_budget: int | None = None,
) -> WritingRuntime:
    """A canned first-use runtime (composed config + pipeline)."""
    return WritingRuntime(
        config=config or _CASCADE_CONFIG,
        api_key="sk-user-key",
        base_url="https://user.example/v1",
        pipeline=pipeline or MagicMock(spec=["generate"], name="pipeline"),
        series_history_budget=series_history_budget,
    )


def _static_runtime_factory(
    runtime: WritingRuntime,
) -> tuple[Callable[[], Awaitable[WritingRuntime]], list[int]]:
    """An async runtime factory returning a fixed runtime; counts calls."""
    calls: list[int] = []

    async def runtime_factory() -> WritingRuntime:
        calls.append(1)
        return runtime

    return runtime_factory, calls


def _request_model(user_id: uuid.UUID) -> SimpleNamespace:
    """A fake GenerationRequest ORM row with valid attributes."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        novel_id=uuid.uuid4(),
        user_id=user_id,
        mode="full_draft",
        tone="balanced",
        status="pending",
        word_count=0,
    )


def _streaming_pipeline(*, capture: dict[str, Any] | None = None) -> MagicMock:
    """A spec'd pipeline whose generate() yields two chunks."""
    pipeline = MagicMock(spec=["generate"], name="pipeline")

    async def _generate(*_args: Any, **kwargs: Any) -> Any:
        if capture is not None:
            capture.update(kwargs)
        yield StreamChunk(text="Hello ")
        yield StreamChunk(text="world.", is_final=True, usage=USAGE)

    pipeline.generate = _generate
    return pipeline


def _gate_open_novel_repo() -> AsyncMock:
    """Novel repo where every novel belongs to the caller (S6 gate open)."""
    repo = AsyncMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=make_novel())
    return repo


def _make_service(
    runtime_factory: Callable[[], Awaitable[WritingRuntime]],
    repo: AsyncMock,
    novel_repo: AsyncMock | None = None,
) -> WritingService:
    """A WritingService over a counting runtime factory + gate-open repos."""
    return WritingService(
        repo=repo,
        runtime_factory=runtime_factory,
        draft_processor=MagicMock(spec=DraftProcessor),
        chapter_repo=AsyncMock(spec=["get"]),
        novel_repo=novel_repo or _gate_open_novel_repo(),
    )


# ---------------------------------------------------------------------------
# Service-level lazy contract
# ---------------------------------------------------------------------------


class TestLazyServiceContract:
    """The service composes its runtime lazily, once, post-gate."""

    async def test_no_composition_at_construction(self) -> None:
        """Construction must not invoke the runtime factory — both
        cascades and the pipeline composition stay idle until first use."""
        _factory, calls = _static_runtime_factory(_runtime())
        repo = AsyncMock(spec=["get_by_id"])

        _make_service(_factory, repo)

        assert calls == []

    async def test_ensure_resolved_composes_once_and_is_idempotent(self) -> None:
        """First use composes exactly once; repeat calls hit the cache."""
        runtime = _runtime()
        factory, calls = _static_runtime_factory(runtime)
        repo = AsyncMock(spec=["get_by_id"])
        service = _make_service(factory, repo)

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert calls == [1]
        assert first is second
        assert first is runtime

    async def test_validate_request_access_is_a_first_use_site(self) -> None:
        """The pre-stream seam composes the runtime exactly once — after
        the request-row ownership gate, before the router constructs the
        ``StreamingResponse``."""
        runtime = _runtime()
        factory, calls = _static_runtime_factory(runtime)
        user_id = uuid4()
        request_model = _request_model(user_id)
        repo = AsyncMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=request_model)
        service = _make_service(factory, repo)

        await service.validate_request_access(request_model.id, str(user_id))

        assert calls == [1]

    async def test_configuration_error_propagates_and_is_uncached(self) -> None:
        """RULE-11 / ADR-086: the composition's ``ConfigurationError``
        (unconfigured provider) propagates from the pre-stream seam —
        the service never swallows it, and the failure is NOT cached:
        the next attempt re-invokes the composition."""
        raising = _RaisingRuntimeFactory()
        user_id = uuid4()
        repo = AsyncMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=_request_model(user_id))
        service = _make_service(raising, repo)

        with pytest.raises(ConfigurationError):
            await service.validate_request_access(uuid4(), str(user_id))
        with pytest.raises(ConfigurationError):
            await service.validate_request_access(uuid4(), str(user_id))

        assert raising.calls == 2

    async def test_ownership_gate_stays_ahead_of_composition(self) -> None:
        """An unknown/foreign request is rejected with ``NotFoundError``
        and the runtime factory is NEVER invoked — the IDOR S6 gate
        precedes resolution (MUST-NOT-change list)."""
        _factory, calls = _static_runtime_factory(_runtime())
        repo = AsyncMock(spec=["get_by_id"])
        repo.get_by_id = AsyncMock(return_value=None)
        service = _make_service(_factory, repo)

        with pytest.raises(NotFoundError):
            await service.validate_request_access(uuid4(), str(uuid4()))

        assert calls == []


# ---------------------------------------------------------------------------
# First-use streaming
# ---------------------------------------------------------------------------


class TestFirstUseStreaming:
    """The eager factory's runtime, consumed verbatim by the stream."""

    async def test_stream_generation_streams_with_composed_runtime(self) -> None:
        """Timing-only invariant: the lazy service streams with the SAME
        effective runtime the eager factory passed — the pipeline call
        and the streaming-status transition read the composed config and
        credentials verbatim, and the composition is not re-run."""
        composition_calls: list[WritingRuntime] = []
        capture: dict[str, Any] = {}
        pipeline = _streaming_pipeline(capture=capture)
        runtime = _runtime(pipeline=pipeline)

        async def runtime_factory() -> WritingRuntime:
            composition_calls.append(runtime)
            return runtime

        user_id = uuid4()
        request_model = _request_model(user_id)
        repo = AsyncMock(spec=["get_by_id", "update_status"])
        repo.get_by_id = AsyncMock(return_value=request_model)
        repo.update_status = AsyncMock()
        service = WritingService(
            repo=repo,
            runtime_factory=runtime_factory,
            draft_processor=MagicMock(spec=DraftProcessor),
            chapter_repo=AsyncMock(spec=["get"]),
            novel_repo=_gate_open_novel_repo(),
        )

        _chunks = [
            chunk async for chunk in service.stream_generation(request_model.id, str(user_id))
        ]

        assert composition_calls == [runtime]
        # Step 2 pins the composed model on the streaming transition.
        status_kwargs = repo.update_status.call_args_list[0].kwargs
        assert status_kwargs["model_id"] == "glm-4.7"
        assert status_kwargs["provider_name"] == "zai"
        # The pipeline call received the composed runtime verbatim.
        assert capture["config"] is runtime.config
        assert capture["api_key"] == "sk-user-key"
        assert capture["base_url"] == "https://user.example/v1"

    async def test_series_history_budget_flows_from_runtime(self) -> None:
        """ADR-082: the composed series-history ceiling (a token-limits
        cascade output) reaches the provider call via the runtime."""
        composition_calls: list[WritingRuntime] = []
        provider = AsyncMock()
        provider.assemble_series_history.return_value = "Previously…"
        pipeline = _streaming_pipeline()
        runtime = _runtime(pipeline=pipeline, series_history_budget=12_000)

        async def runtime_factory() -> WritingRuntime:
            composition_calls.append(runtime)
            return runtime

        user_id = uuid4()
        request_model = _request_model(user_id)
        repo = AsyncMock(spec=["get_by_id", "update_status"])
        repo.get_by_id = AsyncMock(return_value=request_model)
        repo.update_status = AsyncMock()
        service = WritingService(
            repo=repo,
            runtime_factory=runtime_factory,
            draft_processor=MagicMock(spec=DraftProcessor),
            chapter_repo=AsyncMock(spec=["get"]),
            novel_repo=_gate_open_novel_repo(),
            series_history_provider=provider,
        )

        _chunks = [
            chunk async for chunk in service.stream_generation(request_model.id, str(user_id))
        ]

        assert composition_calls == [runtime]
        provider.assemble_series_history.assert_awaited_once_with(
            request_model.novel_id, token_budget=12_000
        )
