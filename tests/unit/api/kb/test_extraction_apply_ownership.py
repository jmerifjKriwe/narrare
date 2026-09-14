"""S13 — IDOR regression tests: ownership gate on POST /kb/extract/apply.

Carried finding from S10 (plan
``docs/superpowers/plans/2026-08-26-idor-remediation.md`` §S10/S13):
``ExtractionService.extract_from_chapter`` was gated (S10), but the
apply step — ``ExtractionService.apply_extraction`` — still trusted the
``novel_id`` path segment. A foreign caller could create entries in the
victim's KB (and, because the per-item handler swallows errors, even
the downstream 403s from KBService were logged-and-skipped rather than
surfaced).

After the fix ``apply_extraction`` runs ``verify_novel_owned`` BEFORE
the apply service is constructed: the owner's apply is unchanged; a
foreign or unknown novel id raises ``NotFoundError`` with ZERO KB
writes. Foreign ≡ unknown (anti-enumeration).

The router previously converted ``NotFoundError`` into HTTP 500 via its
broad ``except Exception`` — both extraction handlers now re-raise it
so the global NarrareError handler maps it to the sanctioned 404 shape.

Sibling matrix: ``test_relationship_dismissed_extraction_ownership.py``
(relationships / dismissed / extract).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.kb.dependencies_extraction import get_extraction_service
from narrare.kb.extraction_service import ExtractionService
from narrare.kb.schemas_extraction import ApplyExtractionItem
from narrare_core.shared.errors import NotFoundError
from tests.unit.api.kb._extraction_helpers import static_resolution
from tests.unit.api.kb._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.schemas import KBEntryCreate, KBEntryUpdate
    from narrare.kb.service import KBService
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

USER_A = uuid4()  # rightful owner of the novel (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A
UNKNOWN_NOVEL_ID = uuid4()

_APPLY_URL = "/api/v1/novels/{novel_id}/kb/extract/apply"
_EXTRACT_URL = "/api/v1/novels/{novel_id}/kb/extract/{chapter_id}"

_OWNERSHIP = {NOVEL_ID: USER_A}


# ---------------------------------------------------------------------------
# Recording fakes (ADR-030: behavioral fakes, not MagicMock)
# ---------------------------------------------------------------------------


class _FakeAppliedEntry:
    """Minimal KB-entry stand-in returned by the fake KBService."""

    def __init__(self, entry_id: UUID, name: str, entity_type: str) -> None:
        self.id = entry_id
        self.name = name
        self.entity_type = entity_type


class _RecordingKBService:
    """Fake KBService — records create/update calls, applies nothing."""

    def __init__(self) -> None:
        self.create_calls: list[tuple[UUID, UUID, str]] = []
        self.update_calls: list[tuple[UUID, UUID, UUID]] = []

    async def create(
        self, *, novel_id: UUID, user_id: UUID, data: KBEntryCreate
    ) -> _FakeAppliedEntry:
        self.create_calls.append((novel_id, user_id, data.name))
        return _FakeAppliedEntry(uuid4(), data.name, data.entity_type)

    async def update(
        self, *, novel_id: UUID, entry_id: UUID, user_id: UUID, data: KBEntryUpdate
    ) -> _FakeAppliedEntry:
        del data
        self.update_calls.append((novel_id, entry_id, user_id))
        return _FakeAppliedEntry(entry_id, "updated", "character")


class _RecordingRelRepo:
    """Fake RelationshipRepository — records created relationship rows."""

    def __init__(self) -> None:
        self.created: list[object] = []

    async def create(self, rel: object) -> object:
        self.created.append(rel)
        return rel


class _NullChapterRepo:
    """Chapter repo stand-in — apply never reads chapters."""

    async def get_by_id(self, chapter_id: UUID, novel_id: UUID) -> None:
        raise AssertionError("apply_extraction must never read chapters")


class _NullKBRepo:
    """KB repo stand-in — apply only uses it for name lookups."""

    async def get_by_name(self, novel_id: UUID, name: str) -> None:
        return None


def _make_service() -> tuple[
    ExtractionService, _RecordingKBService, _RecordingRelRepo, FakeNovelRepo
]:
    """Build an ExtractionService over recording fakes + an ownership map."""
    novel_repo = FakeNovelRepo(_OWNERSHIP)
    kb_service = _RecordingKBService()
    rel_repo = _RecordingRelRepo()
    from narrare_core.llm import ResolvedModelConfig

    config = ResolvedModelConfig(
        provider_name="test", model_id="test-model", temperature=0.7, max_tokens=128
    )
    session = MagicMock(spec=["begin_nested"], name="session")
    session.begin_nested.return_value = AsyncMock()  # async context manager (SAVEPOINT)
    service = ExtractionService(
        registry=cast("ModelRegistry", object()),
        model_resolution=static_resolution(config),
        chapter_repo=cast("ChapterRepositoryProtocol", _NullChapterRepo()),
        kb_repo=cast("KBRepositoryProtocol", _NullKBRepo()),
        composer=cast("PromptComposer", object()),
        novel_repo=cast("NovelRepositoryProtocol", novel_repo),
        kb_service=cast("KBService", kb_service),
        rel_repo=cast("RelationshipRepository", rel_repo),
        session=cast("AsyncSession", session),
    )
    return service, kb_service, rel_repo, novel_repo


def _new_entity_item(name: str = "Alice") -> ApplyExtractionItem:
    return ApplyExtractionItem(
        item_type="new_entity",
        name=name,
        entity_type="character",
        proposed_content={"summary": "protagonist"},
    )


# ---------------------------------------------------------------------------
# Service-level matrix
# ---------------------------------------------------------------------------


class TestApplyExtractionOwnership:
    """apply_extraction: owner applies; foreign/unknown → 404, zero writes."""

    async def test_owner_applies_new_entity(self) -> None:
        service, kb_service, rel_repo, novel_repo = _make_service()

        response = await service.apply_extraction(
            novel_id=NOVEL_ID,
            user_id=USER_A,
            items=[_new_entity_item()],
        )

        assert len(response.created_entries) == 1
        assert response.created_entries[0].name == "Alice"
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_A)]
        assert kb_service.create_calls == [(NOVEL_ID, USER_A, "Alice")]
        assert rel_repo.created == []

    async def test_foreign_raises_not_found_without_writes(self) -> None:
        service, kb_service, rel_repo, novel_repo = _make_service()

        with pytest.raises(NotFoundError) as exc_info:
            await service.apply_extraction(
                novel_id=NOVEL_ID,
                user_id=USER_B,
                items=[_new_entity_item()],
            )

        assert str(exc_info.value) == f"Novel ({NOVEL_ID}) not found"
        assert novel_repo.get_by_id_calls == [(NOVEL_ID, USER_B)]
        assert kb_service.create_calls == []
        assert kb_service.update_calls == []
        assert rel_repo.created == []

    async def test_unknown_shape_matches_foreign(self) -> None:
        service, kb_service, _, _ = _make_service()

        with pytest.raises(NotFoundError) as exc_info:
            await service.apply_extraction(
                novel_id=UNKNOWN_NOVEL_ID,
                user_id=USER_A,
                items=[_new_entity_item()],
            )

        assert str(exc_info.value) == f"Novel ({UNKNOWN_NOVEL_ID}) not found"
        assert kb_service.create_calls == []


# ---------------------------------------------------------------------------
# Router-level matrix (NotFoundError must surface as 404, not 500)
# ---------------------------------------------------------------------------


class _GatedStubService:
    """ExtractionService stand-in raising the gate's NotFoundError."""

    def __init__(self, owner: UUID) -> None:
        self._owner = owner

    async def apply_extraction(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        items: list[object],
        chapter_id: UUID | None = None,
    ):
        if user_id != self._owner:
            raise NotFoundError("Novel", identifier=str(novel_id))
        raise AssertionError("owner path not under test here")

    async def extract_from_chapter(self, *, novel_id: UUID, chapter_id: UUID, user_id: UUID):
        if user_id != self._owner:
            raise NotFoundError("Novel", identifier=str(novel_id))
        raise AssertionError("owner path not under test here")


@pytest.fixture
def app():
    """Test app with overridden auth + the gated stub extraction service."""
    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    application.state.auth_user = str(USER_A)
    application.dependency_overrides[get_current_user_id] = _mock_auth
    application.dependency_overrides[get_extraction_service] = lambda: _GatedStubService(USER_A)
    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


def _assert_404_novel(response, novel_id: UUID) -> None:
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": f"Novel ({novel_id}) not found", "code": "NOT_FOUND"}


class TestExtractionRoutesOwnershipShape:
    """Foreign gate denial over HTTP: 404 (never the 500 of the old catch)."""

    async def test_foreign_apply_returns_404_not_500(self, app, client) -> None:
        app.state.auth_user = str(USER_B)

        response = await client.post(
            _APPLY_URL.format(novel_id=NOVEL_ID),
            json={"items": [_new_entity_item().model_dump(mode="json")]},
        )

        _assert_404_novel(response, NOVEL_ID)

    async def test_foreign_extract_returns_404_not_500(self, app, client) -> None:
        """S10 latent gap: the broad except converted the gate's 404 to 500."""
        app.state.auth_user = str(USER_B)

        response = await client.post(_EXTRACT_URL.format(novel_id=NOVEL_ID, chapter_id=uuid4()))

        _assert_404_novel(response, NOVEL_ID)
