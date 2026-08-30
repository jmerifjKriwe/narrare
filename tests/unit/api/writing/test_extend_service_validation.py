"""Unit tests for ExtendService — validation and request creation.

Split from test_extend_service.py per RULE-04 (file size limit).

Covers:
1. validate_extend: empty text_before → ValidationError
2. validate_extend: nonexistent chapter → NotFoundError
3. validate_extend: active generation → ConflictError
4. validate_extend: valid request passes
5. start_extend: creates request row, returns GenerateResponse
6. _EXTEND_WORD_TARGETS mapping completeness
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import ANY, AsyncMock

import pytest

from narrare.writing.extend_service import _EXTEND_WORD_TARGETS, ExtendService
from narrare.writing.schemas import ExtendLength, ExtendRequest, GenerateResponse
from narrare_core.llm import ResolvedModelConfig
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIG = ResolvedModelConfig(
    provider_name="test",
    model_id="test-model",
    temperature=0.7,
    max_tokens=4000,
)


def _request(**kw: Any) -> ExtendRequest:
    defaults: dict[str, Any] = {
        "text_before": "Alice walked through the dark forest. The trees loomed.",
        "length": ExtendLength.MEDIUM,
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return ExtendRequest(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_active_for_chapter = AsyncMock(return_value=None)
    repo.create_if_no_active = AsyncMock(return_value=uuid.uuid4())
    repo.create = AsyncMock(return_value=uuid.uuid4())
    repo.update_status = AsyncMock()
    return repo


@pytest.fixture()
def mock_chapter_repo() -> AsyncMock:
    """Gate-open chapter repo (binds to ANY novel) — S6 access matrix lives
    in ``test_generation_access_matrix.py``."""
    from tests.factories import make_chapter

    repo = AsyncMock(spec=["get"])
    repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    return repo


@pytest.fixture()
def mock_novel_repo() -> AsyncMock:
    """Gate-open novel repo (every novel owned by the caller)."""
    from tests.factories import make_novel

    repo = AsyncMock(spec=["get_by_id"])
    repo.get_by_id = AsyncMock(return_value=make_novel())
    return repo


@pytest.fixture()
def service(
    mock_repo: AsyncMock, mock_chapter_repo: AsyncMock, mock_novel_repo: AsyncMock
) -> ExtendService:
    from unittest.mock import MagicMock

    pipeline = AsyncMock()
    proc = MagicMock(spec=["process"])
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return ExtendService(
        repo=mock_repo,
        pipeline=pipeline,
        draft_processor=proc,
        config=CONFIG,
        chapter_repo=mock_chapter_repo,
        novel_repo=mock_novel_repo,
    )


# ---------------------------------------------------------------------------
# validate_extend
# ---------------------------------------------------------------------------


class TestValidateExtend:
    async def test_empty_text_before_raises_validation_error(self, service: ExtendService) -> None:
        req = _request(text_before="   ")
        with pytest.raises(ValidationError, match="text_before must not be empty"):
            await service.validate_extend(
                uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4())
            )

    async def test_nonexistent_chapter_raises_not_found(
        self,
        service: ExtendService,
        mock_chapter_repo: AsyncMock,
    ) -> None:
        mock_chapter_repo.get = AsyncMock(return_value=None)
        req = _request()
        with pytest.raises(NotFoundError, match="Chapter"):
            await service.validate_extend(
                uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4())
            )

    async def test_active_generation_raises_conflict(
        self, service: ExtendService, mock_repo: AsyncMock
    ) -> None:
        mock_repo.get_active_for_chapter = AsyncMock(return_value=AsyncMock(spec=["status"]))
        req = _request()
        with pytest.raises(ConflictError, match="already active"):
            await service.validate_extend(
                uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4())
            )

    async def test_valid_request_passes(self, service: ExtendService) -> None:
        req = _request()
        await service.validate_extend(uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4()))

    async def test_valid_with_text_after_passes(self, service: ExtendService) -> None:
        req = _request(text_after="The sun was setting.")
        await service.validate_extend(uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# start_extend
# ---------------------------------------------------------------------------


class TestStartExtend:
    async def test_returns_generate_response(self, service: ExtendService) -> None:
        resp = await service.start_extend(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request())
        assert isinstance(resp, GenerateResponse)
        assert resp.status == "pending"
        assert resp.mode == "extend"

    async def test_delegates_validation(
        self, service: ExtendService, mock_chapter_repo: AsyncMock
    ) -> None:
        mock_chapter_repo.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.start_extend(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request())

    async def test_creates_request_row(self, service: ExtendService, mock_repo: AsyncMock) -> None:
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        req = _request()

        await service.start_extend(chapter_id, novel_id, user_id, req)

        mock_repo.create_if_no_active.assert_called_once()
        args = mock_repo.create_if_no_active.call_args.args
        assert args[0] == chapter_id
        assert args[1] == novel_id
        assert args[3] == "extend"


# ---------------------------------------------------------------------------
# _EXTEND_WORD_TARGETS constant
# ---------------------------------------------------------------------------


class TestWordTargetMapping:
    def test_short_maps_to_150(self) -> None:
        assert _EXTEND_WORD_TARGETS[ExtendLength.SHORT] == 150

    def test_medium_maps_to_400(self) -> None:
        assert _EXTEND_WORD_TARGETS[ExtendLength.MEDIUM] == 400

    def test_long_maps_to_750(self) -> None:
        assert _EXTEND_WORD_TARGETS[ExtendLength.LONG] == 750

    def test_all_lengths_covered(self) -> None:
        assert set(_EXTEND_WORD_TARGETS.keys()) == set(ExtendLength)
