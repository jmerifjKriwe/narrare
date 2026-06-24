"""CR-AUFG-07-19 — ``PromptHistoryApiService`` unit tests (save + list).

The service composes the core file-based ``PromptManagementService`` with the
DB-backed ``PromptHistoryRepository``.  These tests use in-memory fakes (see
``history_service_fakes.py``) — no filesystem, no DB — and assert the
save/list orchestration contract.  Compare/restore/clear live in the split
module ``test_prompt_history_service_restore.py`` (RULE-04 file-size limit).
"""

from __future__ import annotations

import uuid

import pytest

from narrare.prompts.history_service import PromptHistoryApiService
from narrare.prompts.schemas import SaveOverrideRequest
from narrare.prompts.schemas_prompt_history import PromptHistoryScope
from tests.unit.api.prompts.history_service_fakes import (
    VERSION_MARKER,
    FakeCore,
    FakeRepo,
    hash_text,
)

PROMPT_ID = "writing/en/new_chapter"


@pytest.fixture
def fake_core() -> FakeCore:
    return FakeCore()


@pytest.fixture
def fake_repo() -> FakeRepo:
    return FakeRepo()


@pytest.fixture
def service(fake_core: FakeCore, fake_repo: FakeRepo) -> PromptHistoryApiService:
    return PromptHistoryApiService(
        core=fake_core,
        repo=fake_repo,
        retention_limit=100,
    )


class TestSaveOverrideRecorded:
    async def test_writes_file_first_then_records_revision(
        self, service: PromptHistoryApiService, fake_core: FakeCore, fake_repo: FakeRepo
    ) -> None:
        """File write happens; a revision with the canonical content is recorded."""
        request = SaveOverrideRequest(content="my override text")

        await service.save_override_recorded(PROMPT_ID, request, actor_id=uuid.uuid4())

        assert fake_core.save_calls == [(PROMPT_ID, "my override text")]
        assert fake_repo.insert_calls == 1
        recorded = fake_repo.rows[0]
        expected_content = "my override text" + VERSION_MARKER
        assert recorded.content == expected_content
        assert recorded.content_hash == hash_text(expected_content)
        assert recorded.source == "save"

    async def test_dedup_skips_recording_when_hash_matches_latest(
        self, service: PromptHistoryApiService, fake_core: FakeCore, fake_repo: FakeRepo
    ) -> None:
        """Saving identical content twice records only one revision."""
        request = SaveOverrideRequest(content="same content")

        await service.save_override_recorded(PROMPT_ID, request, actor_id=uuid.uuid4())
        await service.save_override_recorded(PROMPT_ID, request, actor_id=uuid.uuid4())

        assert fake_core.save_calls == [(PROMPT_ID, "same content")] * 2
        assert fake_repo.insert_calls == 1, "second identical save must not record"

    async def test_records_when_content_changes(
        self, service: PromptHistoryApiService, fake_repo: FakeRepo
    ) -> None:
        """Distinct content produces distinct revisions."""
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v1"), actor_id=uuid.uuid4()
        )
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v2"), actor_id=uuid.uuid4()
        )
        assert fake_repo.insert_calls == 2

    async def test_db_failure_does_not_block_file_write(
        self,
        service: PromptHistoryApiService,
        fake_core: FakeCore,
        fake_repo: FakeRepo,
    ) -> None:
        """Best-effort: a DB failure is swallowed; the file write stands."""
        fake_repo.fail_next_insert = RuntimeError("db down")
        request = SaveOverrideRequest(content="will record-fail")

        await service.save_override_recorded(PROMPT_ID, request, actor_id=uuid.uuid4())

        assert fake_core.save_calls == [(PROMPT_ID, "will record-fail")]
        assert fake_repo.insert_calls == 1

    async def test_change_reason_is_forwarded(
        self, service: PromptHistoryApiService, fake_repo: FakeRepo
    ) -> None:
        await service.save_override_recorded(
            PROMPT_ID,
            SaveOverrideRequest(content="x", change_reason="tweak tone"),
            actor_id=uuid.uuid4(),
        )
        assert fake_repo.rows[0].change_reason == "tweak tone"

    async def test_enforces_retention_after_insert(
        self,
        service: PromptHistoryApiService,
        fake_repo: FakeRepo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Retention is enforced after each successful insert."""
        calls: list[int] = []
        real = fake_repo.enforce_retention

        async def spy(prompt_id: str, scope: str, *, keep: int = 100) -> int:
            calls.append(keep)
            return await real(prompt_id, scope, keep=keep)

        monkeypatch.setattr(fake_repo, "enforce_retention", spy)

        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="x"), actor_id=uuid.uuid4()
        )
        assert calls == [100]


class TestListHistory:
    async def test_returns_revisions_with_total_and_pagination(
        self, service: PromptHistoryApiService, fake_repo: FakeRepo
    ) -> None:
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v1"), actor_id=uuid.uuid4()
        )
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v2"), actor_id=uuid.uuid4()
        )

        result = await service.list_history(PROMPT_ID, limit=50, offset=0)

        assert result.total == 2
        assert result.prompt_id == PROMPT_ID
        assert result.scope == PromptHistoryScope.PROJECT
        assert len(result.revisions) == 2
        assert result.revisions[0].content.endswith("v2" + VERSION_MARKER)

    async def test_is_active_derived_from_current_file(
        self, service: PromptHistoryApiService, fake_core: FakeCore, fake_repo: FakeRepo
    ) -> None:
        """Only the revision matching the current active file is ``is_active``."""
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v1"), actor_id=uuid.uuid4()
        )
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v2"), actor_id=uuid.uuid4()
        )

        result = await service.list_history(PROMPT_ID, limit=50, offset=0)

        active = [r for r in result.revisions if r.is_active]
        assert len(active) == 1
        assert active[0].content.endswith("v2" + VERSION_MARKER)

    async def test_no_active_when_override_reset(
        self, service: PromptHistoryApiService, fake_core: FakeCore, fake_repo: FakeRepo
    ) -> None:
        """When the active file is gone, no revision is active."""
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v1"), actor_id=uuid.uuid4()
        )
        fake_core.files.clear()  # simulate reset_override

        result = await service.list_history(PROMPT_ID, limit=50, offset=0)
        assert not any(r.is_active for r in result.revisions)

    async def test_empty_history(self, service: PromptHistoryApiService) -> None:
        result = await service.list_history(PROMPT_ID, limit=50, offset=0)
        assert result.total == 0
        assert result.revisions == []


def test_service_satisfies_protocol(service: PromptHistoryApiService) -> None:
    """PromptHistoryApiService structurally satisfies its Protocol (RULE-17)."""
    from narrare.prompts.contracts import PromptHistoryServiceProtocol

    assert isinstance(service, PromptHistoryServiceProtocol)
