"""Unit tests for StyleVariantService — style-variant regeneration (CR-AUFG-07-22).

The service orchestrates: validate → create request row → stream via pipeline.
The pipeline is mocked; we assert the service passes ``style_variant`` through
to ``pipeline.generate()`` and uses the correct rewrite mode/count.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing.contracts_style_variants import StyleVariantRegenerationProtocol
from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest
from narrare.writing.style_variant_service import StyleVariantService
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError
from narrare_core.writing import StyleVariant
from narrare_core.writing._enums import GenerationMode

CONFIG = ResolvedModelConfig(provider_name="test", model_id="m", max_tokens=2000)

# The service calls UUID(user_id) internally (mirrors RewriteService), so the
# test user_id must be a valid UUID string.
USER_ID = "00000000-0000-0000-0000-000000000001"


def _make_request(
    variant: StyleVariant = StyleVariant.MORE_SENSORY,
) -> StyleVariantRegenerateRequest:
    return StyleVariantRegenerateRequest(
        source_text=(
            "The forest was dark and full of ancient trees that whispered "
            "secrets to each other across the centuries."
        ),
        style_variant=variant,
    )


def _make_draft_processor() -> Any:
    """Draft processor mock whose ``process()`` returns the text unchanged."""
    dp = MagicMock(spec=["process"])
    dp.process = MagicMock(spec=[], side_effect=lambda text, **_kw: text)
    return dp


def _dummy_pipeline() -> Any:
    """Pipeline mock with the ``generate`` method spec'd (RULE-TEST-01)."""
    return MagicMock(spec=["generate"])


def _gate_open_repos() -> tuple[Any, Any]:
    """S6 gate-open repos (chapter binds to ANY novel, every novel owned)."""
    from tests.factories import make_chapter, make_novel

    chapter_repo = MagicMock(spec=["get"])
    chapter_repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    novel_repo = MagicMock(spec=["get_by_id"])
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return chapter_repo, novel_repo


def _make_service(pipeline: Any, repo: Any) -> StyleVariantService:
    """A service over a pinned static runtime (ADR-086 L35 lazy ctor).

    The runtime factory pins ``pipeline`` verbatim so the guard/working
    mock semantics are unchanged; the lazy composition contract itself
    is pinned in ``test_style_variant_service_lazy_resolution.py``.
    """
    from tests.unit.api.writing._style_variant_factories import make_static_runtime_factory

    chapter_repo, novel_repo = _gate_open_repos()
    return StyleVariantService(
        repo=repo,
        runtime_factory=make_static_runtime_factory(pipeline, CONFIG),
        draft_processor=_make_draft_processor(),
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )


@pytest.fixture()
def mock_repo() -> Any:
    repo = MagicMock(spec=["get_active_for_chapter", "create_if_no_active", "update_status"])
    repo.get_active_for_chapter = AsyncMock(return_value=None)
    repo.create_if_no_active = AsyncMock(return_value=uuid4())
    repo.update_status = AsyncMock()
    return repo


async def _fake_stream(*_chunks: StreamChunk) -> Any:
    for c in _chunks:
        yield c


class TestStyleVariantServiceProtocol:
    def test_implements_protocol(self) -> None:
        """StyleVariantService satisfies the runtime_checkable Protocol."""
        svc = _make_service(_dummy_pipeline(), _dummy_pipeline())
        assert isinstance(svc, StyleVariantRegenerationProtocol)


class TestStyleVariantServiceValidate:
    @pytest.mark.asyncio
    async def test_validate_raises_on_empty_source(self, mock_repo: Any) -> None:
        svc = _make_service(_dummy_pipeline(), mock_repo)
        req = _make_request()
        req.source_text = "      "  # whitespace only
        with pytest.raises(ValidationError):
            await svc.validate_variant(uuid4(), uuid4(), req, user_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_validate_raises_when_chapter_missing(self, mock_repo: Any) -> None:
        from tests.unit.api.writing._style_variant_factories import make_static_runtime_factory

        chapter_repo, novel_repo = _gate_open_repos()
        chapter_repo.get = AsyncMock(return_value=None)  # unknown chapter
        svc = StyleVariantService(
            repo=mock_repo,
            runtime_factory=make_static_runtime_factory(_dummy_pipeline(), CONFIG),
            draft_processor=_make_draft_processor(),
            chapter_repo=chapter_repo,
            novel_repo=novel_repo,
        )
        with pytest.raises(NotFoundError):
            await svc.validate_variant(uuid4(), uuid4(), _make_request(), user_id=str(uuid4()))

    @pytest.mark.asyncio
    async def test_validate_raises_on_active_generation(self, mock_repo: Any) -> None:
        mock_repo.get_active_for_chapter = AsyncMock(return_value=uuid4())
        svc = _make_service(_dummy_pipeline(), mock_repo)
        with pytest.raises(ConflictError):
            await svc.validate_variant(uuid4(), uuid4(), _make_request(), user_id=str(uuid4()))


class TestStyleVariantServiceStream:
    @pytest.mark.asyncio
    async def test_stream_passes_style_variant_to_pipeline(self, mock_repo: Any) -> None:
        pipeline = MagicMock(spec=["generate"])
        usage = TokenUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        pipeline.generate = MagicMock(
            spec=[],
            return_value=_fake_stream(
                StreamChunk(text='<alternative label="Sensory">Immersive text here.</alternative>'),
                StreamChunk(text="", is_final=True, usage=usage),
            ),
        )
        svc = _make_service(pipeline, mock_repo)
        chunks = [
            c
            async for c in svc.stream_variant(
                uuid4(), uuid4(), USER_ID, _make_request(StyleVariant.MORE_SENSORY)
            )
        ]

        # The pipeline.generate call must include the style_variant kwarg.
        call_kwargs = pipeline.generate.call_args.kwargs
        assert call_kwargs["style_variant"] == StyleVariant.MORE_SENSORY
        assert any(c.is_final for c in chunks)

    @pytest.mark.asyncio
    async def test_stream_uses_rewrite_mode_style_count_one(self, mock_repo: Any) -> None:
        """Default source_mode='rewrite' uses rewrite_mode='style' with count=1."""
        pipeline = MagicMock(spec=["generate"])
        pipeline.generate = MagicMock(
            spec=[],
            return_value=_fake_stream(
                StreamChunk(text="x", is_final=True, usage=TokenUsage(1, 1, 2)),
            ),
        )
        svc = _make_service(pipeline, mock_repo)
        req = _make_request()
        async for _ in svc.stream_variant(uuid4(), uuid4(), USER_ID, req):
            pass

        # Default source_mode is "rewrite" -> request row + pipeline REWRITE mode.
        assert mock_repo.create_if_no_active.call_args.args[3] == "rewrite"
        pipeline_request = pipeline.generate.call_args.args[0]
        assert pipeline_request.mode == GenerationMode.REWRITE

        call_kwargs = pipeline.generate.call_args.kwargs
        assert call_kwargs["rewrite_mode"] == "style"
        assert call_kwargs["rewrite_count"] == 1

    @pytest.mark.asyncio
    async def test_stream_co_author_mode_routes_to_co_author_pipeline(self, mock_repo: Any) -> None:
        """source_mode='co_author' -> CO_AUTHOR mode + co_author_focus, no rewrite kwargs.

        Verifies the Increment B branch: the request row uses the 'co_author'
        mode string, the pipeline request carries ``GenerationMode.CO_AUTHOR``,
        and ``rewrite_mode``/``rewrite_count`` are NOT forwarded (the variant
        direction is the sole creative signal).
        """
        pipeline = MagicMock(spec=["generate"])
        pipeline.generate = MagicMock(
            spec=[],
            return_value=_fake_stream(
                StreamChunk(text="x", is_final=True, usage=TokenUsage(1, 1, 2)),
            ),
        )
        svc = _make_service(pipeline, mock_repo)
        req = _make_request()
        req.source_mode = "co_author"
        async for _ in svc.stream_variant(uuid4(), uuid4(), USER_ID, req):
            pass

        # Request row created with the co_author mode string.
        assert mock_repo.create_if_no_active.call_args.args[3] == "co_author"

        # Pipeline request mode is CO_AUTHOR.
        pipeline_request = pipeline.generate.call_args.args[0]
        assert pipeline_request.mode == GenerationMode.CO_AUTHOR

        # Mode-specific kwargs: co_author_focus passed, style_variant preserved,
        # and rewrite-specific kwargs absent.
        call_kwargs = pipeline.generate.call_args.kwargs
        assert call_kwargs["co_author_focus"] == []
        assert call_kwargs["style_variant"] == req.style_variant
        assert "rewrite_mode" not in call_kwargs
        assert "rewrite_count" not in call_kwargs

    @pytest.mark.asyncio
    async def test_stream_passes_source_text_as_selection(self, mock_repo: Any) -> None:
        """The source_text is passed as both chapter_content and selection_text."""
        pipeline = MagicMock(spec=["generate"])
        pipeline.generate = MagicMock(
            spec=[],
            return_value=_fake_stream(
                StreamChunk(text="x", is_final=True, usage=TokenUsage(1, 1, 2)),
            ),
        )
        svc = _make_service(pipeline, mock_repo)
        req = _make_request()
        async for _ in svc.stream_variant(uuid4(), uuid4(), USER_ID, req):
            pass

        call_kwargs = pipeline.generate.call_args.kwargs
        assert call_kwargs["selection_text"] == req.source_text
        assert req.source_text in call_kwargs["chapter_content"]

    @pytest.mark.asyncio
    async def test_stream_transitions_to_completed_on_final(self, mock_repo: Any) -> None:
        pipeline = MagicMock(spec=["generate"])
        pipeline.generate = MagicMock(
            spec=[],
            return_value=_fake_stream(
                StreamChunk(text="done", is_final=True, usage=TokenUsage(2, 3, 5)),
            ),
        )
        svc = _make_service(pipeline, mock_repo)
        async for _ in svc.stream_variant(uuid4(), uuid4(), USER_ID, _make_request()):
            pass

        # update_status called with "streaming" then "completed".
        statuses = [c.args[1] for c in mock_repo.update_status.call_args_list]
        assert "streaming" in statuses
        assert "completed" in statuses

    @pytest.mark.asyncio
    async def test_stream_transitions_to_failed_on_pipeline_error(self, mock_repo: Any) -> None:
        async def _raising_stream(*_a: Any, **_k: Any) -> Any:
            yield StreamChunk(text="partial")
            raise RuntimeError("LLM exploded")

        pipeline = MagicMock(spec=["generate"])
        pipeline.generate = MagicMock(spec=[], return_value=_raising_stream())
        svc = _make_service(pipeline, mock_repo)

        with pytest.raises(RuntimeError, match="LLM exploded"):
            async for _ in svc.stream_variant(uuid4(), uuid4(), USER_ID, _make_request()):
                pass

        statuses = [c.args[1] for c in mock_repo.update_status.call_args_list]
        assert "failed" in statuses
