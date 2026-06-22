"""PROMPT-003 backend reset service tests (CR-AUFG-07-16).

Verifies that :class:`PromptResetApiService` returns metadata
(:class:`ResetResponse`) after resetting an override, instead of a bare
boolean. The Core management service is faked — no filesystem, no DB.
"""

from __future__ import annotations

from narrare.prompts.preview_service import PromptResetApiService
from narrare_core.prompts._management_types import PromptDetail


def _make_detail(
    *,
    prompt_id: str = "writing/en/new_chapter",
    content: str = "default",
    source: str = "bundled",
    is_overridden: bool = False,
) -> PromptDetail:
    return PromptDetail(
        prompt_id=prompt_id,
        content=content,
        base_content=content,
        source=source,
        is_overridden=is_overridden,
        variables=[],
        metadata={},
    )


class FakeCoreManagement:
    """Fake Core ``_ResetDataSource`` — records calls, returns canned data."""

    def __init__(
        self,
        *,
        reset_result: bool = True,
        detail: PromptDetail | None = None,
    ) -> None:
        self._reset_result = reset_result
        self._detail = detail
        self.reset_calls: list[str] = []
        self.get_calls: list[str] = []

    async def reset_override(self, prompt_id: str) -> bool:
        self.reset_calls.append(prompt_id)
        return self._reset_result

    async def get_prompt(self, prompt_id: str) -> PromptDetail | None:
        self.get_calls.append(prompt_id)
        return self._detail


async def test_reset_returns_metadata() -> None:
    """Happy path: reset returns effective source + content after deletion."""
    mgmt = FakeCoreManagement(
        reset_result=True,
        detail=_make_detail(content="default", source="bundled"),
    )
    service = PromptResetApiService(core=mgmt)

    resp = await service.reset_with_metadata("writing/en/new_chapter")

    assert resp.reset is True
    assert resp.effective_source == "bundled"
    assert resp.effective_content == "default"
    assert mgmt.reset_calls == ["writing/en/new_chapter"]
    assert mgmt.get_calls == ["writing/en/new_chapter"]


async def test_reset_returns_false_when_no_override_existed() -> None:
    """Edge case: reset is False (nothing to delete), effective prompt still reported."""
    mgmt = FakeCoreManagement(
        reset_result=False,
        detail=_make_detail(content="bundled default", source="bundled"),
    )
    service = PromptResetApiService(core=mgmt)

    resp = await service.reset_with_metadata("writing/en/new_chapter")

    assert resp.reset is False
    # Effective content is still reported so the UI can render the active prompt.
    assert resp.effective_source == "bundled"
    assert resp.effective_content == "bundled default"


async def test_reset_handles_missing_detail_gracefully() -> None:
    """Edge case: detail is None (prompt vanished post-reset) → empty strings, not crash."""
    mgmt = FakeCoreManagement(reset_result=True, detail=None)
    service = PromptResetApiService(core=mgmt)

    resp = await service.reset_with_metadata("writing/en/new_chapter")

    assert resp.reset is True
    assert resp.effective_source == ""
    assert resp.effective_content == ""


async def test_reset_reports_actual_post_reset_source() -> None:
    """The reported source reflects the post-reset state returned by Core."""
    mgmt = FakeCoreManagement(
        reset_result=True,
        detail=_make_detail(content="restored content", source="bundled"),
    )
    service = PromptResetApiService(core=mgmt)

    resp = await service.reset_with_metadata("writing/en/new_chapter")

    assert resp.effective_source == "bundled"
    assert resp.effective_content == "restored content"
