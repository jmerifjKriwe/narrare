"""S13 — IDOR regression tests: ownership gate on GET /adaptive/{id}/context.

Carried GAP-MINOR from S11 (plan
``docs/superpowers/plans/2026-08-26-idor-remediation.md`` §S11c): the
S11c gate covered ``toggle``/``weights``/``snapshots`` but
``AdaptiveContextService.get_context`` — the dashboard's READ endpoint —
still skipped ``_verify_project_owned``. A foreign caller could read the
victim's adaptive source summary (preference text, voice profiles,
style constraints, avoidance patterns) by project id.

After the fix the service gates ownership FIRST (Pattern B, same
``_verify_project_owned`` the sibling operations use): the owner's
response is unchanged; a foreign or unknown project id gets a
``NotFoundError`` (404, foreign ≡ unknown) with ZERO provider reads.

Sibling matrices: ``test_adaptive_settings_ownership.py`` (toggle /
weights / snapshots).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.adaptive.dependencies import get_adaptive_context_service
from narrare.adaptive.service import AdaptiveContextService
from narrare.novels.models import Novel
from narrare_core.ai_invocation.adaptive_context import AdaptiveContext, AdaptiveSettings
from narrare_core.shared.errors import NotFoundError
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from fastapi import FastAPI

    from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence

USER_A = uuid4()  # rightful owner of the project (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A (project ≡ novel)

_CONTEXT_URL = "/api/v1/adaptive/{project_id}/context"


# ---------------------------------------------------------------------------
# Recording fakes (ADR-030: behavioral fakes, not MagicMock)
# ---------------------------------------------------------------------------


class _RecordingProvider:
    """Minimal AdaptiveContextProvider that records every read."""

    def __init__(self) -> None:
        self.context_calls: list[tuple[UUID, UUID]] = []
        self.settings_calls: list[tuple[UUID, UUID]] = []

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        uid = cast("UUID", user_id)
        pid = cast("UUID", project_id)
        self.context_calls.append((uid, pid))
        return AdaptiveContext(
            user_id=uid,
            project_id=pid,
            preference_text="prefers terse dialogue",
        )

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        self.settings_calls.append((cast("UUID", user_id), cast("UUID", project_id)))
        return AdaptiveSettings(enabled=True)


class _NullSettingsRepo:
    """Fake AdaptiveSettingsRepositoryProtocol — read path never persists."""

    def __init__(self) -> None:
        self.loads: list[UUID] = []

    async def load(self, project_id: UUID) -> AdaptiveSettings | None:
        self.loads.append(project_id)
        return None

    async def save(self, project_id: UUID, settings: AdaptiveSettings) -> None:
        raise AssertionError("get_context must never persist")


class _NullEvidenceRepo:
    """Fake EvidenceSnapshotReader — get_context never reads evidence."""

    async def get_adaptive_snapshots(
        self,
        novel_id: UUID,
        *,
        limit: int = 20,
    ) -> list[FeatureInvocationEvidence]:
        raise AssertionError("get_context must never read evidence snapshots")


class _Bundle:
    """Gated service wired over recording fakes + an owned-novel store."""

    def __init__(self) -> None:
        self.novel_repo = FakeNovelRepository()
        self.novel_repo.seed(Novel(id=NOVEL_ID, user_id=USER_A))
        self.provider = _RecordingProvider()
        self.service = AdaptiveContextService(
            provider=self.provider,
            settings_repo=_NullSettingsRepo(),
            evidence_repo=_NullEvidenceRepo(),
            novel_repo=self.novel_repo,
        )


def _assert_404_novel(response, project_id: UUID) -> None:
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": f"Novel ({project_id}) not found", "code": "NOT_FOUND"}


# ---------------------------------------------------------------------------
# Service-level matrix
# ---------------------------------------------------------------------------


class TestGetContextOwnership:
    """get_context: owner reads; foreign/unknown → 404, zero provider reads."""

    async def test_owner_reads_context(self) -> None:
        bundle = _Bundle()

        response = await bundle.service.get_context(NOVEL_ID, USER_A)

        assert response.project_id == str(NOVEL_ID)
        assert response.enabled is True
        assert response.sources.preference_text == "prefers terse dialogue"
        assert bundle.provider.context_calls == [(USER_A, NOVEL_ID)]
        assert bundle.provider.settings_calls == [(USER_A, NOVEL_ID)]

    async def test_foreign_raises_not_found_without_provider_reads(self) -> None:
        bundle = _Bundle()

        with pytest.raises(NotFoundError) as exc_info:
            await bundle.service.get_context(NOVEL_ID, USER_B)

        assert str(exc_info.value) == f"Novel ({NOVEL_ID}) not found"
        assert bundle.provider.context_calls == []
        assert bundle.provider.settings_calls == []

    async def test_unknown_shape_matches_foreign(self) -> None:
        bundle = _Bundle()
        unknown = uuid4()

        with pytest.raises(NotFoundError) as exc_info:
            await bundle.service.get_context(unknown, USER_A)

        assert str(exc_info.value) == f"Novel ({unknown}) not found"
        assert bundle.provider.context_calls == []


# ---------------------------------------------------------------------------
# Router-level matrix (full HTTP path over the gated service)
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Test app with overridden auth; the adaptive service dependency is
    overridden per-test with the gated real service over recording fakes."""
    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    application.state.auth_user = str(USER_A)
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class TestContextRouteOwnership:
    """Owner unchanged over HTTP; foreign → 404 with zero effects."""

    async def test_owner_context_200(self, app, client) -> None:
        bundle = _Bundle()
        app.dependency_overrides[get_adaptive_context_service] = lambda: bundle.service

        response = await client.get(_CONTEXT_URL.format(project_id=NOVEL_ID))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["project_id"] == str(NOVEL_ID)
        assert response.json()["sources"]["preference_text"] == "prefers terse dialogue"

    async def test_foreign_context_404_without_provider_reads(self, app, client) -> None:
        bundle = _Bundle()
        app.dependency_overrides[get_adaptive_context_service] = lambda: bundle.service
        app.state.auth_user = str(USER_B)

        response = await client.get(_CONTEXT_URL.format(project_id=NOVEL_ID))

        _assert_404_novel(response, NOVEL_ID)
        assert bundle.provider.context_calls == []
        assert bundle.provider.settings_calls == []
