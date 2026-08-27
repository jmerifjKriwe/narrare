"""Unit tests for RewriteService — validation and request creation.

Split from test_rewrite_service.py per RULE-04 (file size limit).

Covers:
1. validate_rewrite: empty selection_text → ValidationError
2. validate_rewrite: nonexistent chapter → NotFoundError
3. validate_rewrite: active generation → ConflictError
4. validate_rewrite: valid request passes
5. validate_rewrite: valid request with context markers passes
6. start_rewrite: creates request row, returns GenerateResponse
7. start_rewrite: delegates validation errors
8. start_rewrite: IntegrityError → NotFoundError
9. start_rewrite: passes tone to repository
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import ANY, AsyncMock

import pytest

from narrare.writing.rewrite_service import RewriteService
from narrare.writing.schemas import GenerateResponse
from narrare.writing.schemas_rewrite import RewriteMode, RewriteRequest
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

_SELECTION = (
    "This is a sufficiently long selection text that demonstrates the "
    "rewrite service validation flow. It needs to exceed fifty characters "
    "to satisfy Pydantic's min_length constraint on RewriteRequest."
)


def _request(**kw: Any) -> RewriteRequest:
    """Create a RewriteRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "selection_text": _SELECTION,
        "mode": RewriteMode.TONE,
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return RewriteRequest(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.chapter_exists = AsyncMock(return_value=True)
    repo.get_active_for_chapter = AsyncMock(return_value=None)
    repo.create_if_no_active = AsyncMock(return_value=uuid.uuid4())
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
) -> RewriteService:
    from unittest.mock import MagicMock

    pipeline = MagicMock(spec=["generate"])
    proc = MagicMock(spec=["process"])
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return RewriteService(
        repo=mock_repo,
        pipeline=pipeline,
        draft_processor=proc,
        config=CONFIG,
        chapter_repo=mock_chapter_repo,
        novel_repo=mock_novel_repo,
    )


# ---------------------------------------------------------------------------
# validate_rewrite
# ---------------------------------------------------------------------------


class TestValidateRewrite:
    async def test_empty_selection_text_raises_validation_error(
        self, service: RewriteService
    ) -> None:
        """Whitespace-only selection fails with MISSING_INPUT."""
        req = _request(selection_text=" " * 60)
        with pytest.raises(ValidationError, match="selection_text must not be empty"):
            await service.validate_rewrite(
                uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4())
            )

    async def test_nonexistent_chapter_raises_not_found(
        self,
        service: RewriteService,
        mock_chapter_repo: AsyncMock,
    ) -> None:
        """Chapter that doesn't exist returns 404."""
        mock_chapter_repo.get = AsyncMock(return_value=None)
        req = _request()
        with pytest.raises(NotFoundError, match="Chapter"):
            await service.validate_rewrite(
                uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4())
            )

    async def test_active_generation_raises_conflict(
        self, service: RewriteService, mock_repo: AsyncMock
    ) -> None:
        """Active generation request blocks a new rewrite."""
        mock_repo.get_active_for_chapter = AsyncMock(return_value=AsyncMock(spec=["status"]))
        req = _request()
        with pytest.raises(ConflictError, match="already active"):
            await service.validate_rewrite(
                uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4())
            )

    async def test_valid_request_passes(self, service: RewriteService) -> None:
        """Valid request with default tone passes validation."""
        req = _request()
        await service.validate_rewrite(uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4()))

    async def test_valid_request_with_context_markers_passes(self, service: RewriteService) -> None:
        """Request with context_before and context_after passes."""
        req = _request(
            context_before="The chapter so far has been setting the stage.",
            context_after="The next scene reveals the truth.",
        )
        await service.validate_rewrite(uuid.uuid4(), uuid.uuid4(), req, user_id=str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# start_rewrite
# ---------------------------------------------------------------------------


class TestStartRewrite:
    async def test_returns_generate_response(self, service: RewriteService) -> None:
        """start_rewrite returns pending GenerateResponse with rewrite mode."""
        resp = await service.start_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        )
        assert isinstance(resp, GenerateResponse)
        assert resp.status == "pending"
        assert resp.mode == "rewrite"

    async def test_delegates_validation(
        self, service: RewriteService, mock_chapter_repo: AsyncMock
    ) -> None:
        """Validation failures propagate from start_rewrite."""
        mock_chapter_repo.get = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await service.start_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request())

    async def test_creates_request_row(self, service: RewriteService, mock_repo: AsyncMock) -> None:
        """Request row created with correct parameters."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        req = _request()

        await service.start_rewrite(chapter_id, novel_id, user_id, req)

        mock_repo.create_if_no_active.assert_called_once()
        args = mock_repo.create_if_no_active.call_args.args
        assert args[0] == chapter_id
        assert args[1] == novel_id
        assert args[3] == "rewrite"
        assert args[4] == req.tone

    async def test_passes_tone_to_repo(self, service: RewriteService, mock_repo: AsyncMock) -> None:
        """Custom tone is forwarded to repository."""
        req = _request(tone="dramatic")
        await service.start_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req)

        assert mock_repo.create_if_no_active.call_args.args[4] == "dramatic"

    async def test_integrity_error_converts_to_not_found(
        self, service: RewriteService, mock_repo: AsyncMock
    ) -> None:
        """FK constraint violation becomes NotFoundError (HTTP 404).

        Regression test: when chapter_id or novel_id don't exist in the DB,
        the FK constraint raises IntegrityError.  The service must convert
        this to NotFoundError instead of letting it bubble as an unhandled 500.
        """
        from sqlalchemy.exc import IntegrityError

        mock_repo.create_if_no_active = AsyncMock(side_effect=IntegrityError("", {}, Exception()))

        with pytest.raises(NotFoundError):
            await service.start_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request())
