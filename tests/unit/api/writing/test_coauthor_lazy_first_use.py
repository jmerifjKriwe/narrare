"""First-use composition semantics for CoAuthorService (ADR-086 L31).

Composition half of the L31 service-level lazy contract (the
validate-seam lazy pins live in
``test_coauthor_service_lazy_resolution.py``; the factory-level wiring
pins in ``test_deps_coauthor_lazy_wiring.py``). Split from it per the
RULE-04 size limit. This file pins:

- the SET-005 word-limit check reads ``max_selection_words`` from the
  composed runtime (the limit is a token-limits-cascade output, so the
  check necessarily runs at first use — still pre-header, pre-row);
- the eager factory's composition
  (``replace(resolved.config, temperature=0.7,
  max_tokens=limits.output_limit)``, verbatim credentials, tier-wired
  pipeline) is reproduced exactly once at first use — WHAT unchanged,
  only WHEN.

Mirrors ``tests/unit/api/writing/test_rewrite_service_lazy_resolution.py``
(ADR-086 L33 precedent).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.settings.token_limits.contracts import TokenLimitOverrides
from narrare.writing._coauthor_support import CoAuthorRuntime
from narrare.writing.coauthor_service import CoAuthorService
from narrare.writing.schemas_coauthor import CoAuthorFocus, CoAuthorRequest
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.shared.errors import ValidationError
from tests.factories import make_chapter, make_novel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

USAGE = TokenUsage(prompt_tokens=20, completion_tokens=100, total_tokens=120)

_SELECTION = (
    "This is a sufficiently long selection text that demonstrates the "
    "co-author service lazy resolution flow. It needs to exceed fifty "
    "characters to satisfy the min_length constraint on CoAuthorRequest."
)

_CASCADE_CONFIG = ResolvedModelConfig(
    provider_name="zai",
    model_id="glm-4.7",
    temperature=0.2,
    max_tokens=8192,
)

_LIMITS = TokenLimitOverrides(output_limit=1500)


def _runtime(
    pipeline: MagicMock | None = None,
    config: ResolvedModelConfig | None = None,
    *,
    max_selection_words: int = 2000,
) -> CoAuthorRuntime:
    """A canned first-use runtime (composed config + pipeline + SET-005)."""
    return CoAuthorRuntime(
        config=config or ResolvedModelConfig(provider_name="t", model_id="m"),
        api_key=None,
        base_url=None,
        pipeline=pipeline or MagicMock(spec=["generate"], name="pipeline"),
        max_selection_words=max_selection_words,
    )


def _static_runtime_factory(
    runtime: CoAuthorRuntime,
) -> tuple[Any, list[int]]:
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


def _streaming_service(
    runtime_factory: Any,
    repo: AsyncMock,
) -> CoAuthorService:
    """A CoAuthorService over gate-open repos and an identity processor."""
    chapter_repo, novel_repo = _gate_open_repos()
    draft_processor = MagicMock(spec=["process"])
    draft_processor.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return CoAuthorService(
        repo=repo,
        runtime_factory=runtime_factory,
        draft_processor=draft_processor,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )


class TestSet005WordLimitFromRuntime:
    """SET-005 reads ``max_selection_words`` from the composed runtime.

    The limit is a token-limits-cascade output (user → project → env →
    code default), so under the M-budget lazy wiring the check
    necessarily runs AT first use — after the gates, still pre-header
    and before any request-row creation.
    """

    def _make_service(self, runtime: CoAuthorRuntime) -> tuple[CoAuthorService, list[int]]:
        factory, calls = _static_runtime_factory(runtime)
        repo = AsyncMock(spec=["get_active_for_chapter"])
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        chapter_repo, novel_repo = _gate_open_repos()
        service = CoAuthorService(
            repo=repo,
            runtime_factory=factory,
            draft_processor=MagicMock(spec=["process"]),
            chapter_repo=chapter_repo,
            novel_repo=novel_repo,
        )
        return service, calls

    async def test_word_limit_check_uses_composed_runtime_limit(self) -> None:
        """A selection over the runtime's limit raises ``ValidationError``
        with the cascade-resolved limit; the composition ran exactly once."""
        service, calls = self._make_service(_runtime(max_selection_words=500))

        text_600_words = " ".join(["a"] * 600)
        with pytest.raises(ValidationError, match="exceeds 500 words") as exc_info:
            await service.validate_coauthor(
                uuid4(), uuid4(), _request(selection_text=text_600_words), user_id=str(uuid4())
            )

        assert exc_info.value.code == "SELECTION_TOO_LONG"
        assert calls == [1]

    async def test_selection_at_runtime_limit_passes(self) -> None:
        """Exactly at the runtime's limit the selection passes (<= bound),
        with the composition run exactly once."""
        service, calls = self._make_service(_runtime(max_selection_words=500))

        text_500_words = " ".join(["a"] * 500)
        await service.validate_coauthor(
            uuid4(), uuid4(), _request(selection_text=text_500_words), user_id=str(uuid4())
        )

        assert calls == [1]


class TestFirstUseComposition:
    """The eager factory's runtime composition, reproduced at first use."""

    async def test_stream_coauthor_streams_with_composed_runtime(self) -> None:
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
        pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Revised."))
        runtime = CoAuthorRuntime(
            config=composed_config,
            api_key="sk-user-key",
            base_url="https://user.example/v1",
            pipeline=pipeline,
            max_selection_words=_LIMITS.max_selection_words,
        )
        composition_calls: list[ResolvedModelConfig] = []

        async def runtime_factory() -> CoAuthorRuntime:
            composition_calls.append(runtime.config)
            return runtime

        repo = AsyncMock()
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=uuid4())
        repo.get_by_id = AsyncMock(return_value=None)
        repo.update_status = AsyncMock()
        service = _streaming_service(runtime_factory, repo)

        chunks = [
            chunk
            async for chunk in service.stream_coauthor(uuid4(), uuid4(), str(uuid4()), _request())
        ]

        assert [c.text for c in chunks] == ["Revised.", ""]
        # Composition ran exactly once (via validate inside stream_coauthor),
        # and the pipeline received the composed runtime verbatim.
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
