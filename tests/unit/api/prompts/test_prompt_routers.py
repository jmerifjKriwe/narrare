"""Unit tests for the thin prompts routers (RULE-06 delegation + error mapping).

The routers delegate immediately to their services (RULE-06); the only logic
they own is HTTP error mapping (404 for missing prompts, 400/503 for the
live-test provider gate). These tests call the handler functions directly with
fake services — no FastAPI app, no DB, no TestClient — and pin that mapping.

Endpoint wiring (status codes, response models) is covered by the integration
suite (``tests/integration/prompts/``); this module owns the unit-level logic.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.prompts.router import (
    cascade_info,
    detect_updates,
    get_diff,
    get_prompt,
    list_prompts,
    reset_override,
    save_override,
)
from narrare.prompts.router_prompt_history import (
    clear_history,
    compare_revisions,
    list_history,
    restore_revision,
)
from narrare.prompts.router_prompt_ux import (
    preview_prompt,
    reset_prompt,
    start_live_test,
)
from narrare.prompts.schemas import SaveOverrideRequest
from narrare.prompts.schemas_prompt_ux import LiveTestRequest, PreviewRequest
from narrare_core.shared.errors import ConfigurationError, ValidationError

_USER = "11111111-1111-1111-1111-111111111111"


class _FakeStreamLiveTest:
    """Fake for ``PromptLiveTestApiService.stream_live_test`` (RULE-TEST-01).

    The real method is an async *generator*: calling it returns an async
    iterator WITHOUT awaiting (the router never awaits it). A bare
    ``MagicMock`` matches that contract but violates RULE-TEST-01, and an
    ``AsyncMock`` would coerce the return into a coroutine that is never
    awaited (RuntimeWarning, fatal under ``filterwarnings=error``). This tiny
    fake records calls and replays the prepared frame iterator.
    """

    def __init__(self, frames: object) -> None:
        self._frames = frames
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        return self._frames


# ===========================================================================
# router.py — management endpoints
# ===========================================================================


class TestManagementRouter:
    async def test_detect_updates_delegates_to_service(self) -> None:
        service = AsyncMock()
        service.detect_updates.return_value = []
        result = await detect_updates(user_id=_USER, service=service)
        assert result == []
        service.detect_updates.assert_awaited_once()

    async def test_cascade_info_delegates_to_service(self) -> None:
        service = AsyncMock()
        service.cascade_info.return_value = []
        result = await cascade_info("writing/en/new_chapter", user_id=_USER, service=service)
        assert result == []
        service.cascade_info.assert_awaited_once_with("writing/en/new_chapter")

    async def test_list_prompts_passes_category_filter(self) -> None:
        service = AsyncMock()
        service.list_prompts.return_value = []
        await list_prompts(user_id=_USER, category="writing", service=service)
        service.list_prompts.assert_awaited_once_with(category="writing")

    async def test_reset_override_delegates_to_service(self) -> None:
        service = AsyncMock()
        service.reset_override.return_value = True
        result = await reset_override("writing/en/new_chapter", user_id=_USER, service=service)
        assert result is True

    async def test_get_diff_raises_404_when_no_override(self) -> None:
        service = AsyncMock()
        service.get_diff.return_value = None
        with pytest.raises(HTTPException) as exc:
            await get_diff("writing/en/new_chapter", user_id=_USER, service=service)
        assert exc.value.status_code == 404

    async def test_get_diff_returns_result_when_override_exists(self) -> None:
        sentinel = object()
        service = AsyncMock()
        service.get_diff.return_value = sentinel
        result = await get_diff("writing/en/new_chapter", user_id=_USER, service=service)
        assert result is sentinel

    async def test_get_prompt_raises_404_when_missing(self) -> None:
        service = AsyncMock()
        service.get_prompt.return_value = None
        with pytest.raises(HTTPException) as exc:
            await get_prompt("missing/prompt", user_id=_USER, service=service)
        assert exc.value.status_code == 404

    async def test_get_prompt_returns_detail_when_found(self) -> None:
        sentinel = object()
        service = AsyncMock()
        service.get_prompt.return_value = sentinel
        result = await get_prompt("writing/en/new_chapter", user_id=_USER, service=service)
        assert result is sentinel

    async def test_save_override_wires_history_service(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        history = AsyncMock()
        monkeypatch.setattr(
            "narrare.prompts.router.get_prompt_history_service",
            AsyncMock(return_value=history),
        )
        await save_override(
            "writing/en/new_chapter",
            SaveOverrideRequest(content="custom"),
            user_id=_USER,
            session=MagicMock(spec=AsyncSession),
        )
        history.save_override_recorded.assert_awaited_once()
        # actor_id is parsed from the authenticated user id.
        kwargs = history.save_override_recorded.call_args
        assert kwargs.kwargs["actor_id"] == uuid.UUID(_USER)


# ===========================================================================
# router_prompt_ux.py — preview / reset / live-test
# ===========================================================================


class TestUxRouter:
    async def test_preview_delegates_to_service(self) -> None:
        service = AsyncMock()
        sentinel = object()
        service.preview.return_value = sentinel
        result = await preview_prompt(
            "writing/en/new_chapter",
            request=MagicMock(spec=PreviewRequest),
            user_id=_USER,
            service=service,
        )
        assert result is sentinel

    async def test_reset_delegates_to_service(self) -> None:
        service = AsyncMock()
        sentinel = object()
        service.reset_with_metadata.return_value = sentinel
        result = await reset_prompt("writing/en/new_chapter", user_id=_USER, service=service)
        assert result is sentinel

    async def test_live_test_returns_400_on_validation_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = AsyncMock()
        service.validate_live_test.side_effect = ValidationError("not acknowledged")
        monkeypatch.setattr(
            "narrare.prompts.router_prompt_ux.get_live_test_service",
            AsyncMock(return_value=service),
        )
        with pytest.raises(HTTPException) as exc:
            await start_live_test(
                "writing/en/new_chapter",
                request=MagicMock(spec=LiveTestRequest),
                user_id=_USER,
                session=MagicMock(spec=AsyncSession),
            )
        assert exc.value.status_code == 400

    async def test_live_test_returns_503_when_no_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = AsyncMock()
        service.validate_live_test.side_effect = ConfigurationError("no provider")
        monkeypatch.setattr(
            "narrare.prompts.router_prompt_ux.get_live_test_service",
            AsyncMock(return_value=service),
        )
        with pytest.raises(HTTPException) as exc:
            await start_live_test(
                "writing/en/new_chapter",
                request=MagicMock(spec=LiveTestRequest),
                user_id=_USER,
                session=MagicMock(spec=AsyncSession),
            )
        assert exc.value.status_code == 503

    async def test_live_test_streams_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from fastapi.responses import StreamingResponse

        service = AsyncMock()
        metadata = object()
        service.validate_live_test.return_value = metadata

        async def _frames() -> object:
            yield "data: ok\n\n"

        # stream_live_test is an async-GENERATOR method: calling it returns an
        # async iterator WITHOUT awaiting (the router never awaits it). An
        # AsyncMock would return a coroutine that is never awaited →
        # RuntimeWarning → fatal under filterwarnings=error, so a small
        # RULE-TEST-01-compliant fake replays the prepared frame iterator.
        service.stream_live_test = _FakeStreamLiveTest(_frames())
        monkeypatch.setattr(
            "narrare.prompts.router_prompt_ux.get_live_test_service",
            AsyncMock(return_value=service),
        )
        response = await start_live_test(
            "writing/en/new_chapter",
            request=MagicMock(spec=LiveTestRequest),
            user_id=_USER,
            session=MagicMock(spec=AsyncSession),
        )
        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"
        service.validate_live_test.assert_awaited_once()


# ===========================================================================
# router_prompt_history.py — history endpoints
# ===========================================================================


class TestHistoryRouter:
    @pytest.fixture
    def history_service(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def wired_history(
        self, monkeypatch: pytest.MonkeyPatch, history_service: AsyncMock
    ) -> AsyncMock:
        monkeypatch.setattr(
            "narrare.prompts.router_prompt_history.get_prompt_history_service",
            AsyncMock(return_value=history_service),
        )
        return history_service

    async def test_list_history_delegates_with_pagination(self, wired_history: AsyncMock) -> None:
        wired_history.list_history.return_value = object()
        await list_history(
            "writing/en/new_chapter",
            user_id=_USER,
            session=MagicMock(spec=AsyncSession),
            limit=10,
            offset=5,
        )
        wired_history.list_history.assert_awaited_once()
        kwargs = wired_history.list_history.call_args
        assert kwargs.kwargs["limit"] == 10
        assert kwargs.kwargs["offset"] == 5

    async def test_compare_revisions_delegates(self, wired_history: AsyncMock) -> None:
        wired_history.compare_revisions.return_value = object()
        await compare_revisions(
            "writing/en/new_chapter",
            user_id=_USER,
            session=MagicMock(spec=AsyncSession),
            from_revision="active",
            to_revision="22222222-2222-2222-2222-222222222222",
        )
        wired_history.compare_revisions.assert_awaited_once()

    async def test_restore_revision_delegates(self, wired_history: AsyncMock) -> None:
        revision_id = uuid.uuid4()
        wired_history.restore_revision.return_value = object()
        await restore_revision(
            "writing/en/new_chapter",
            revision_id=revision_id,
            user_id=_USER,
            session=MagicMock(spec=AsyncSession),
        )
        wired_history.restore_revision.assert_awaited_once()
        assert wired_history.restore_revision.call_args.kwargs["actor_id"] == uuid.UUID(_USER)

    async def test_clear_history_delegates(self, wired_history: AsyncMock) -> None:
        wired_history.clear_history.return_value = object()
        await clear_history(
            "writing/en/new_chapter",
            user_id=_USER,
            session=MagicMock(spec=AsyncSession),
        )
        wired_history.clear_history.assert_awaited_once()
