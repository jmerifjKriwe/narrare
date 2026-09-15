"""Lazy model-resolution semantics for InlineSuggestService (ADR-086 L36).

The factory (``writing/deps_suggest.py::get_suggest_service``) wires a
``LazyModelResolution``; this file pins the SERVICE-side lazy contract:

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``validate_suggest`` — the router's pre-stream seam — is a first-use
  site, so ``ConfigurationError`` surfaces as a pre-header 400
  (RULE-11 — AI-mandatory SSE endpoint) and never after headers,
- text validation and the chapter-ownership gate (IDOR S6) run FIRST —
  the routing cascade is NEVER invoked when they fail,
- the eager factory's sampling composition
  (``replace(resolved.config, temperature=0.3, max_tokens=SUGGEST_MAX_TOKENS)``)
  is reproduced exactly once at first use — WHAT unchanged, only WHEN.

Mirrors ``tests/unit/api/series/test_series_voice_service_lazy_resolution.py``
(ADR-086 L28 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest

from narrare.writing.schemas import InlineSuggestRequest
from narrare.writing.suggest_service import InlineSuggestService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import SUGGEST_MAX_TOKENS
from narrare_core.shared.errors import ConfigurationError, NotFoundError, ValidationError
from tests.unit.api.writing._suggest_factories import (
    make_mock_chapter_repo,
    make_mock_composer,
    make_mock_novel_repo,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare._app.dependencies_services import ModelResolution


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches.

    Exposes the service-level lazy seam (ADR-086): the service must call
    ``resolve()`` exactly once (first use), never at construction.
    """

    def __init__(self, model: ResolvedModel) -> None:
        self._model = model
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._model


class _RaisingResolution:
    """Fake ModelResolution — the cascade finds no configured provider."""

    async def resolve(self) -> ResolvedModel:
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


class _RecordingStreamRegistry:
    """Fake ModelRegistry — records ``stream`` kwargs for pinning.

    Yields one final chunk so ``suggest_inline`` flows to completion.
    """

    def __init__(self) -> None:
        self.stream_calls: list[dict[str, Any]] = []

    async def stream(self, **kwargs: Any) -> AsyncIterator[StreamChunk]:
        self.stream_calls.append(kwargs)
        yield StreamChunk(text=" The cat slept.", is_final=True, usage=TokenUsage(1, 5, 6))


def _resolved_model(
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config or ResolvedModelConfig(provider_name="test", model_id="test-model"),
        api_key=api_key,
        base_url=base_url,
        source="unit-test",
    )


def _make_service(
    model_resolution: ModelResolution,
    registry: _RecordingStreamRegistry | None = None,
) -> tuple[InlineSuggestService, _RecordingStreamRegistry, UUID, str]:
    """Build an InlineSuggestService with the lazy seam injected.

    Seeds owned-chapter mocks so both gates (text validation, IDOR S6)
    pass and requests reach the first-use resolve. Returns
    ``(service, registry, chapter_id, user_id)``.
    """
    reg = registry or _RecordingStreamRegistry()
    service = InlineSuggestService(
        registry=cast("Any", reg),
        composer=cast("Any", make_mock_composer()),
        chapter_repo=cast("Any", make_mock_chapter_repo()),
        novel_repo=cast("Any", make_mock_novel_repo()),
        model_resolution=model_resolution,
    )
    return service, reg, uuid4(), str(uuid4())


def _request(text_before: str = "The old house") -> InlineSuggestRequest:
    return InlineSuggestRequest(text_before=text_before)


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the InlineSuggestService boundary."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch the routing cascade."""
        counting = _CountingResolution(_resolved_model())

        _make_service(counting)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use resolves exactly once; repeat calls hit the cache."""
        counting = _CountingResolution(_resolved_model())
        service, _reg, _cid, _uid = _make_service(counting)

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_validate_suggest_resolves_exactly_once(self) -> None:
        """The pre-stream seam is a first-use site — one resolve."""
        counting = _CountingResolution(_resolved_model())
        service, _reg, chapter_id, user_id = _make_service(counting)

        await service.validate_suggest(chapter_id, user_id, _request())

        assert counting.calls == 1

    async def test_suggest_inline_resolves_exactly_once(self) -> None:
        """The streaming entry point is a first-use site — one resolve."""
        counting = _CountingResolution(_resolved_model())
        service, _reg, chapter_id, user_id = _make_service(counting)

        async for _ in service.suggest_inline(chapter_id, user_id, _request()):
            pass

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the pre-stream seam —
        the service never swallows it, so the SSE router's existing
        ``validate_suggest`` call keeps the 400 BEFORE any headers."""
        service, _reg, chapter_id, user_id = _make_service(_RaisingResolution())

        with pytest.raises(ConfigurationError):
            await service.validate_suggest(chapter_id, user_id, _request())

    async def test_configuration_error_propagates_from_suggest_inline(self) -> None:
        """Direct entry-point call: unconfigured provider raises loudly."""
        service, _reg, chapter_id, user_id = _make_service(_RaisingResolution())

        with pytest.raises(ConfigurationError):
            async for _ in service.suggest_inline(chapter_id, user_id, _request()):
                pass  # pragma: no cover

    async def test_text_validation_precedes_resolution(self) -> None:
        """Empty ``text_before`` fails validation BEFORE the cascade —
        the routing resolve is never invoked (validation-first, and the
        eager world's gate ordering is preserved)."""
        counting = _CountingResolution(_resolved_model())
        service, _reg, chapter_id, user_id = _make_service(counting)

        with pytest.raises(ValidationError, match="text_before must not be empty"):
            await service.validate_suggest(chapter_id, user_id, _request("   "))

        assert counting.calls == 0

    async def test_ownership_gate_stays_ahead_of_resolution(self) -> None:
        """An unknown chapter is rejected with ``NotFoundError`` and the
        routing cascade is NEVER invoked — the IDOR S6 gate precedes
        resolution (MUST-NOT-change list)."""
        counting = _CountingResolution(_resolved_model())
        reg = _RecordingStreamRegistry()
        broken_repo = make_mock_chapter_repo()
        broken_repo.get = _async_none
        service = InlineSuggestService(
            registry=cast("Any", reg),
            composer=cast("Any", make_mock_composer()),
            chapter_repo=cast("Any", broken_repo),
            novel_repo=cast("Any", make_mock_novel_repo()),
            model_resolution=counting,
        )

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.validate_suggest(uuid4(), str(uuid4()), _request())

        assert counting.calls == 0


async def _async_none(_chapter_id: UUID) -> None:
    return None


class TestFirstUseComposition:
    """The eager factory's sampling composition, reproduced at first use."""

    async def test_sampling_overrides_applied_exactly_once_at_first_use(self) -> None:
        """Timing-only invariant: the eager factory passed
        ``replace(resolved.config, temperature=0.3,
        max_tokens=SUGGEST_MAX_TOKENS)`` + verbatim credentials into the
        service — the lazy service composes the SAME effective config at
        first use, and the cascade is not re-run afterwards."""
        cascade_config = ResolvedModelConfig(
            provider_name="zai",
            model_id="glm-4.7",
            temperature=0.7,
            max_tokens=4096,
        )
        registry = _RecordingStreamRegistry()
        counting = _CountingResolution(
            _resolved_model(
                cascade_config, api_key="sk-user-key", base_url="https://user.example/v1"
            )
        )
        service, reg, chapter_id, user_id = _make_service(counting, registry=registry)

        await service.validate_suggest(chapter_id, user_id, _request())
        async for _ in service.suggest_inline(chapter_id, user_id, _request()):
            pass

        assert counting.calls == 1
        assert len(reg.stream_calls) == 1
        call = reg.stream_calls[0]
        config = call["config"]
        assert config.temperature == 0.3
        assert config.max_tokens == SUGGEST_MAX_TOKENS
        assert config.provider_name == "zai"
        assert config.model_id == "glm-4.7"
        assert call["api_key"] == "sk-user-key"
        assert call["base_url"] == "https://user.example/v1"
