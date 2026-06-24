"""CR-AUFG-07-19 — ``PromptHistoryApiService`` unit tests (compare/restore/clear).

Split from ``test_prompt_history_service.py`` per RULE-04 (file-size limit).
Uses the shared fakes in ``history_service_fakes.py``.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.prompts.history_service import PromptHistoryApiService
from narrare.prompts.schemas import SaveOverrideRequest
from narrare_core.shared.errors import NotFoundError
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


class TestCompareRevisions:
    async def test_compare_two_revisions(
        self, service: PromptHistoryApiService, fake_repo: FakeRepo
    ) -> None:
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="alpha"), actor_id=uuid.uuid4()
        )
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="beta"), actor_id=uuid.uuid4()
        )
        rev_a, rev_b = fake_repo.rows[0], fake_repo.rows[1]

        result = await service.compare_revisions(
            PROMPT_ID, from_id=str(rev_a.id), to_id=str(rev_b.id)
        )

        assert result.from_content.endswith("alpha" + VERSION_MARKER)
        assert result.to_content.endswith("beta" + VERSION_MARKER)
        assert result.from_source == "save"
        assert result.to_source == "save"

    async def test_compare_revision_against_active(
        self, service: PromptHistoryApiService, fake_repo: FakeRepo
    ) -> None:
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="old"), actor_id=uuid.uuid4()
        )
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="new"), actor_id=uuid.uuid4()
        )
        old = fake_repo.rows[0]

        result = await service.compare_revisions(PROMPT_ID, from_id=str(old.id), to_id="active")

        assert result.from_content.endswith("old" + VERSION_MARKER)
        assert result.to_content.endswith("new" + VERSION_MARKER)
        assert result.to_source == "active"

    async def test_compare_unknown_revision_raises(self, service: PromptHistoryApiService) -> None:
        with pytest.raises(NotFoundError):
            await service.compare_revisions(PROMPT_ID, from_id=str(uuid.uuid4()), to_id="active")


class TestRestoreRevision:
    async def test_append_only_restore_writes_file_and_records_new_revision(
        self,
        service: PromptHistoryApiService,
        fake_core: FakeCore,
        fake_repo: FakeRepo,
    ) -> None:
        """Restore writes the active file + records a NEW revision; original untouched."""
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v1"), actor_id=uuid.uuid4()
        )
        v1_row = fake_repo.rows[0]
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="v2"), actor_id=uuid.uuid4()
        )
        assert fake_repo.insert_calls == 2

        result = await service.restore_revision(PROMPT_ID, v1_row.id, actor_id=uuid.uuid4())

        # File now holds v1 content (re-written via core).
        assert fake_core.files[PROMPT_ID].startswith("v1")
        # A NEW revision was recorded (append-only).
        assert fake_repo.insert_calls == 3
        restored = fake_repo.rows[-1]
        assert restored.source == "restore"
        assert restored.restored_from_id == v1_row.id
        assert restored.content == v1_row.content
        # Original row is NOT mutated.
        assert fake_repo.rows[0].source == "save"
        assert fake_repo.rows[0].restored_from_id is None
        # Response reflects active state.
        assert result.restored_revision.is_active is True
        assert result.active_content.startswith("v1")
        assert result.previous_active_hash == hash_text("v2" + VERSION_MARKER)

    async def test_restore_unknown_revision_raises(self, service: PromptHistoryApiService) -> None:
        with pytest.raises(NotFoundError):
            await service.restore_revision(PROMPT_ID, uuid.uuid4(), actor_id=uuid.uuid4())


class TestClearHistory:
    async def test_clear_deletes_rows_and_leaves_file(
        self,
        service: PromptHistoryApiService,
        fake_core: FakeCore,
        fake_repo: FakeRepo,
    ) -> None:
        await service.save_override_recorded(
            PROMPT_ID, SaveOverrideRequest(content="x"), actor_id=uuid.uuid4()
        )
        assert fake_core.files

        result = await service.clear_history(PROMPT_ID)

        assert result.deleted_count == 1
        assert fake_repo.rows == []
        assert PROMPT_ID in fake_core.files

    async def test_clear_when_empty(self, service: PromptHistoryApiService) -> None:
        result = await service.clear_history(PROMPT_ID)
        assert result.deleted_count == 0
