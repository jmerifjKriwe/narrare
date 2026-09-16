"""Lazy service-level semantics for StyleVariantService (ADR-086 L35).

Service-level half of the L35 lazy contract (the factory-level wiring
pins live in ``test_deps_style_variants_lazy_wiring.py``). The factory
(``writing/deps_style_variants.py::get_style_variant_service``) wires a
``LazyModelResolution`` plus a deferred runtime composition (M-budget):
the REWRITE routing cascade AND the token-limits cascade resolve
together with the sampling/budget/pipeline composition at the service's
FIRST use. This file pins the lazy contract at the service seams:

- ``validate_variant`` — the router's pre-stream seam — is a first-use
  site, so ``ConfigurationError`` surfaces as a pre-header 400
  (RULE-11 — AI-mandatory SSE endpoint) and never after headers;
- the chapter-ownership gate (IDOR S6), text validation, and the
  active-generation conflict check run FIRST — the cascades are NEVER
  invoked when they fail;
- the eager factory's composition
  (``replace(resolved.config, temperature=0.7,
  max_tokens=limits.output_limit)``, verbatim credentials, tier-wired
  pipeline) is reproduced exactly once at first use — WHAT unchanged,
  only WHEN;
- the variant's ``source_mode`` branching (rewrite vs co_author
  pipeline kwargs) is untouched — timing-only migration.

Mirrors ``tests/unit/api/writing/test_extend_service_lazy_resolution.py``
(ADR-086 L32 precedent).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare.writing._style_variants_support import StyleVariantRuntime
from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
from narrare.writing.style_variant_service import StyleVariantService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.shared.errors import (
    ConfigurationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from narrare_core.writing import StyleVariant
from narrare_core.writing._enums import GenerationMode
from tests.factories import make_chapter, make_novel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable


USAGE = TokenUsage(prompt_tokens=20, completion_tokens=100, total_tokens=120)

_SOURCE_TEXT = (
    "The forest was dark and full of ancient trees that whispered "
    "secrets to each other across the centuries of unbroken silence."
)

# A custom, valid 5-tier distribution (sums to 1.0) — proves the resolved
# tier percentages reach the pipeline verbatim at first use.
CUSTOM_TIERS: dict[str, float] = {
    "immediate": 0.50,
    "recent": 0.15,
    "kb_referenced": 0.20,
    "kb_suggested": 0.10,
    "pinned": 0.05,
}

_CASCADE_CONFIG = ResolvedModelConfig(
    provider_name="zai",
    model_id="glm-4.7",
    temperature=0.2,
    max_tokens=8192,
)

_LIMITS = TokenLimitOverrides(output_limit=1500, tier_percentages=CUSTOM_TIERS)


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


class _RaisingRuntimeFactory:
    """Fake runtime factory — the first-use composition finds no provider."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self) -> StyleVariantRuntime:
        self.calls += 1
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


def _runtime(
    pipeline: MagicMock | None = None,
    config: ResolvedModelConfig | None = None,
) -> StyleVariantRuntime:
    """A canned first-use runtime (composed config + pipeline)."""
    return StyleVariantRuntime(
        config=config or ResolvedModelConfig(provider_name="t", model_id="m"),
        api_key=None,
        base_url=None,
        pipeline=pipeline or MagicMock(spec=["generate"], name="pipeline"),
    )


def _static_runtime_factory(
    runtime: StyleVariantRuntime,
) -> tuple[Callable[[], Awaitable[StyleVariantRuntime]], list[int]]:
    """An async runtime factory returning a fixed runtime; counts calls."""
    calls: list[int] = []

    async def runtime_factory() -> StyleVariantRuntime:
        calls.append(1)
        return runtime

    return runtime_factory, calls


def _request(**kw: Any) -> StyleVariantRegenerateRequest:
    """Create a StyleVariantRegenerateRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "source_text": _SOURCE_TEXT,
        "style_variant": StyleVariant.MORE_SENSORY,
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return StyleVariantRegenerateRequest(**defaults)


async def _fake_stream(*texts: str) -> AsyncIterator[StreamChunk]:
    """Async generator yielding StreamChunks — pipeline.generate stand-in."""
    for t in texts:
        yield StreamChunk(text=t)
    yield StreamChunk(text="", is_final=True, usage=USAGE)


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
        runtime_factory: Callable[[], Awaitable[StyleVariantRuntime]],
        repo: AsyncMock | None = None,
        chapter_repo: AsyncMock | None = None,
        novel_repo: AsyncMock | None = None,
    ) -> StyleVariantService:
        gate_chapter_repo, gate_novel_repo = _gate_open_repos()
        default_repo = AsyncMock(spec=["get_active_for_chapter"])
        default_repo.get_active_for_chapter = AsyncMock(return_value=None)
        return StyleVariantService(
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

    async def test_validate_variant_is_a_first_use_site(self) -> None:
        """The pre-stream seam composes the runtime exactly once."""
        factory, calls = _static_runtime_factory(_runtime())
        chapter_repo, novel_repo = _gate_open_repos()
        repo = AsyncMock(spec=["get_active_for_chapter"])
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        service = self._make_service(
            factory, repo=repo, chapter_repo=chapter_repo, novel_repo=novel_repo
        )

        await service.validate_variant(uuid4(), uuid4(), _request(), user_id=str(uuid4()))

        assert calls == [1]

    async def test_configuration_error_propagates_from_validate_variant(self) -> None:
        """RULE-11 / ADR-086: the composition's ``ConfigurationError``
        (unconfigured provider) propagates from the pre-stream seam —
        the service never swallows it, so the SSE router's existing
        ``validate_variant`` call keeps the 400 BEFORE any headers."""
        raising = _RaisingRuntimeFactory()
        service = self._make_service(raising)

        with pytest.raises(ConfigurationError):
            await service.validate_variant(uuid4(), uuid4(), _request(), user_id=str(uuid4()))

        assert raising.calls == 1

    async def test_text_validation_prevents_composition(self) -> None:
        """Whitespace-only ``source_text`` fails validation BEFORE the
        runtime factory runs — the cascades are never invoked
        (validation-first, the eager world's gate ordering preserved)."""
        _factory, calls = _static_runtime_factory(_runtime())
        service = self._make_service(_factory)

        with pytest.raises(ValidationError, match="source_text must not be empty"):
            await service.validate_variant(
                # 60 spaces: passes the schema's min_length=50, fails the
                # service's whitespace-only domain check.
                uuid4(),
                uuid4(),
                _request(source_text=" " * 60),
                user_id=str(uuid4()),
            )

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
            await service.validate_variant(uuid4(), uuid4(), _request(), user_id=str(uuid4()))

        assert calls == []

    async def test_active_generation_conflict_prevents_composition(self) -> None:
        """A concurrently active generation raises ``ConflictError``
        before the cascades run (conflict check precedes resolution)."""
        _factory, calls = _static_runtime_factory(_runtime())
        repo = AsyncMock(spec=["get_active_for_chapter"])
        repo.get_active_for_chapter = AsyncMock(return_value=uuid4())
        service = self._make_service(_factory, repo=repo)

        with pytest.raises(ConflictError, match="already active"):
            await service.validate_variant(uuid4(), uuid4(), _request(), user_id=str(uuid4()))

        assert calls == []


class TestFirstUseComposition:
    """The eager factory's runtime composition, reproduced at first use."""

    async def _streamed_service(
        self,
        runtime: StyleVariantRuntime,
        request: StyleVariantRegenerateRequest,
    ) -> tuple[StyleVariantService, AsyncMock, MagicMock, list[ResolvedModelConfig]]:
        """A service over a counting runtime factory + recorded repo."""
        composition_calls: list[ResolvedModelConfig] = []

        async def runtime_factory() -> StyleVariantRuntime:
            composition_calls.append(runtime.config)
            return runtime

        repo = AsyncMock()
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create_if_no_active = AsyncMock(return_value=uuid4())
        repo.update_status = AsyncMock()
        chapter_repo, novel_repo = _gate_open_repos()
        draft_processor = MagicMock(spec=["process"])
        draft_processor.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
        service = StyleVariantService(
            repo=repo,
            runtime_factory=runtime_factory,
            draft_processor=draft_processor,
            chapter_repo=chapter_repo,
            novel_repo=novel_repo,
        )
        return service, repo, draft_processor, composition_calls

    async def test_stream_variant_streams_with_composed_runtime(self) -> None:
        """Timing-only invariant: the eager factory passed
        ``replace(resolved.config, temperature=0.7,
        max_tokens=limits.output_limit)`` + verbatim credentials + the
        tier-wired pipeline into the service — the lazy service streams
        with the SAME effective runtime, and the composition is not
        re-run afterwards."""
        composed_config = replace(
            _CASCADE_CONFIG,
            temperature=0.7,
            max_tokens=_LIMITS.output_limit,
        )
        pipeline = MagicMock(spec=["generate"], name="pipeline")
        pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Rewritten."))
        runtime = StyleVariantRuntime(
            config=composed_config,
            api_key="sk-user-key",
            base_url="https://user.example/v1",
            pipeline=pipeline,
        )
        service, repo, _dp, composition_calls = await self._streamed_service(runtime, _request())

        chunks = [
            chunk
            async for chunk in service.stream_variant(uuid4(), uuid4(), str(uuid4()), _request())
        ]

        assert [c.text for c in chunks] == ["Rewritten.", ""]
        # Composition ran exactly once (via validate_variant inside
        # stream_variant), and the pipeline received the composed
        # runtime verbatim.
        assert composition_calls == [composed_config]
        generate_kwargs = pipeline.generate.call_args.kwargs
        assert generate_kwargs["config"].temperature == 0.7
        assert generate_kwargs["config"].max_tokens == _LIMITS.output_limit
        assert generate_kwargs["config"].provider_name == "zai"
        assert generate_kwargs["config"].model_id == "glm-4.7"
        assert generate_kwargs["api_key"] == "sk-user-key"
        assert generate_kwargs["base_url"] == "https://user.example/v1"
        # Step 2 pins the resolved model on the streaming transition.
        status_kwargs = repo.update_status.call_args_list[0].kwargs
        assert status_kwargs["model_id"] == "glm-4.7"
        assert status_kwargs["provider_name"] == "zai"

    async def test_source_mode_branching_untouched_by_lazy_runtime(self) -> None:
        """The variant's mode branching is timing-independent: the
        co_author branch still forwards ``co_author_focus`` and withholds
        rewrite kwargs — over the lazily composed runtime."""
        pipeline = MagicMock(spec=["generate"], name="pipeline")
        pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Variant."))
        composed = replace(_CASCADE_CONFIG, temperature=0.7)
        runtime = _runtime(pipeline=pipeline, config=composed)
        service, repo, _dp, composition_calls = await self._streamed_service(runtime, _request())
        req = _request()
        req.source_mode = "co_author"

        _chunks = [c async for c in service.stream_variant(uuid4(), uuid4(), str(uuid4()), req)]

        assert composition_calls == [composed]
        assert repo.create_if_no_active.call_args.args[3] == "co_author"
        pipeline_request = pipeline.generate.call_args.args[0]
        assert pipeline_request.mode == GenerationMode.CO_AUTHOR
        call_kwargs = pipeline.generate.call_args.kwargs
        assert call_kwargs["co_author_focus"] == []
        assert call_kwargs["style_variant"] == req.style_variant
        assert "rewrite_mode" not in call_kwargs
        assert "rewrite_count" not in call_kwargs

    async def test_selection_markers_wrap_source_text(self) -> None:
        """Context markers still bracket the selection inside the
        chapter content handed to the pipeline (content builder moved
        to ``_style_variants_support`` — behavior unchanged)."""
        pipeline = MagicMock(spec=["generate"], name="pipeline")
        pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("V."))
        runtime = _runtime(pipeline=pipeline)
        service, _repo, _dp, _calls = await self._streamed_service(runtime, _request())
        req = _request(context_before="Before the span.", context_after="After the span.")

        async for _ in service.stream_variant(uuid4(), uuid4(), str(uuid4()), req):
            pass

        content = pipeline.generate.call_args.kwargs["chapter_content"]
        assert content.startswith("Before the span.\n[SELECTION START]\n")
        assert "[SELECTION END]\nAfter the span." in content
