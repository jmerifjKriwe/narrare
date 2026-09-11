"""S11 — IDOR regression tests: ownership gates on adaptive settings surfaces.

Service-level + router-level matrix over the adaptive dashboard endpoints
(plan ``docs/superpowers/plans/2026-08-26-idor-remediation.md`` §S11c):

* POST ``/adaptive/{project_id}/toggle``
* POST ``/adaptive/{project_id}/weights``
* GET  ``/adaptive/{project_id}/snapshots``

Before the S11 fix ``AdaptiveContextService`` accepted ``user_id`` but
never gated with it: ``set_enabled``/``set_weights`` persisted into the
victim's ``ProjectSettings.adaptive_settings`` column (foreign project
config WRITE), and ``get_adaptive_snapshots`` carried the comment
``del user_id  # ownership handled at router`` — which was false (the
router only threads identity through) — reading the victim's adaptive
evidence unscoped.

After the fix the service gates via an injected ``NovelRepository``
(Pattern B): owner unchanged (incl. first-touch save creating the
adaptive settings), foreign/unknown → ``NotFoundError`` (404, foreign ≡
unknown) with ZERO persistence and ZERO evidence reads.

The settings-surface sibling matrix lives in
``tests/unit/api/settings/test_project_settings_ownership.py``.
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
from narrare.adaptive.schemas import AdaptiveWeightsInput
from narrare.adaptive.service import AdaptiveContextService
from narrare.novels.models import Novel
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.adaptive_context import AdaptiveContext, AdaptiveSettings
from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence
from narrare_core.shared.errors import NotFoundError
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from fastapi import FastAPI

USER_A = uuid4()  # rightful owner of the project (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A (project ≡ novel)

_TOGGLE_URL = "/api/v1/adaptive/{project_id}/toggle"
_WEIGHTS_URL = "/api/v1/adaptive/{project_id}/weights"
_SNAPSHOTS_URL = "/api/v1/adaptive/{project_id}/snapshots"


# ---------------------------------------------------------------------------
# Recording fakes (ADR-030: behavioral fakes, not MagicMock)
# ---------------------------------------------------------------------------


class _StubProvider:
    """Minimal AdaptiveContextProvider — unused by the gated operations.

    Parameters stay ``object`` (protocol-contravariant) and are cast to
    ``UUID`` at the AdaptiveContext boundary — no suppression needed.
    """

    async def get_context(self, user_id: object, project_id: object) -> AdaptiveContext:
        return AdaptiveContext(
            user_id=cast("UUID", user_id),
            project_id=cast("UUID", project_id),
        )

    async def get_settings(self, user_id: object, project_id: object) -> AdaptiveSettings:
        return AdaptiveSettings()


class _RecordingSettingsRepo:
    """Fake AdaptiveSettingsRepositoryProtocol — records load/save calls."""

    def __init__(self, loaded: AdaptiveSettings | None = None) -> None:
        self._loaded = loaded
        self.loads: list[UUID] = []
        self.saves: list[tuple[UUID, AdaptiveSettings]] = []

    async def load(self, project_id: UUID) -> AdaptiveSettings | None:
        self.loads.append(project_id)
        return self._loaded

    async def save(self, project_id: UUID, settings: AdaptiveSettings) -> None:
        self.saves.append((project_id, settings))


class _RecordingEvidenceRepo:
    """Fake EvidenceSnapshotReader — records read calls."""

    def __init__(self, snapshots: list[FeatureInvocationEvidence] | None = None) -> None:
        self._snapshots = snapshots or []
        self.calls: list[tuple[UUID, int]] = []

    async def get_adaptive_snapshots(
        self,
        novel_id: UUID,
        *,
        limit: int = 20,
    ) -> list[FeatureInvocationEvidence]:
        self.calls.append((novel_id, limit))
        return list(self._snapshots)


class _Bundle:
    """Gated service wired over recording fakes + an owned-novel store."""

    def __init__(self, *, loaded: AdaptiveSettings | None = None) -> None:
        self.novel_repo = FakeNovelRepository()
        self.novel_repo.seed(Novel(id=NOVEL_ID, user_id=USER_A))
        self.settings_repo = _RecordingSettingsRepo(loaded=loaded)
        self.evidence_repo = _RecordingEvidenceRepo(snapshots=[_snapshot()])
        self.service = AdaptiveContextService(
            provider=_StubProvider(),
            settings_repo=self.settings_repo,
            evidence_repo=self.evidence_repo,
            novel_repo=self.novel_repo,
        )


def _snapshot() -> FeatureInvocationEvidence:
    return FeatureInvocationEvidence(
        feature_id="dialogue_coach",
        intent="dialogue_coach",
        mode="dialogue_coach",
        prompt_route="ai_assist/dialogue_coach",
        preference_status=PreferenceStatus.PROVIDED,
        kb_suggested_status=KBSuggestedStatus.NOT_APPLICABLE,
        final_prompt_validated=True,
        audit_state=AuditState.ADOPTED,
        invocation_id=uuid4(),
        novel_id=NOVEL_ID,
        adaptive_source_summary={"summary": "preferences"},
        adaptive_weights={"preference": 0.7},
    )


# ---------------------------------------------------------------------------
# Service-level matrix (toggle / weights / snapshots)
# ---------------------------------------------------------------------------


class TestToggleOwnership:
    """set_enabled: owner persists (first-touch save); foreign/unknown → 404."""

    async def test_owner_first_touch_save(self) -> None:
        bundle = _Bundle(loaded=None)

        response = await bundle.service.set_enabled(NOVEL_ID, USER_A, enabled=False)

        assert response.enabled is False
        assert bundle.settings_repo.loads == [NOVEL_ID]
        assert len(bundle.settings_repo.saves) == 1
        saved_novel_id, saved = bundle.settings_repo.saves[0]
        assert saved_novel_id == NOVEL_ID
        assert saved.enabled is False

    async def test_owner_preserves_existing_weights(self) -> None:
        existing = AdaptiveSettings(enabled=True)
        bundle = _Bundle(loaded=existing)

        response = await bundle.service.set_enabled(NOVEL_ID, USER_A, enabled=False)

        assert response.enabled is False
        assert bundle.settings_repo.saves[0][1].weights == existing.weights

    async def test_foreign_raises_not_found_without_persistence(self) -> None:
        bundle = _Bundle()

        with pytest.raises(NotFoundError) as exc_info:
            await bundle.service.set_enabled(NOVEL_ID, USER_B, enabled=False)

        assert str(exc_info.value) == f"Novel ({NOVEL_ID}) not found"
        assert bundle.settings_repo.loads == []
        assert bundle.settings_repo.saves == []

    async def test_unknown_shape_matches_foreign(self) -> None:
        bundle = _Bundle()
        unknown = uuid4()

        with pytest.raises(NotFoundError) as exc_info:
            await bundle.service.set_enabled(unknown, USER_A, enabled=True)

        assert str(exc_info.value) == f"Novel ({unknown}) not found"
        assert bundle.settings_repo.saves == []


class TestWeightsOwnership:
    """set_weights: owner clamps + persists; foreign/unknown → 404, no write."""

    async def test_owner_clamps_and_persists(self) -> None:
        bundle = _Bundle()

        response = await bundle.service.set_weights(
            NOVEL_ID,
            USER_A,
            AdaptiveWeightsInput(preference=-0.5, voice_fidelity=2.0),
        )

        assert response.weights.preference == 0.0
        assert response.weights.voice_fidelity == 1.0
        saved = bundle.settings_repo.saves[0][1]
        assert saved.weights.preference == 0.0
        assert saved.weights.voice_fidelity == 1.0

    async def test_foreign_raises_not_found_without_persistence(self) -> None:
        bundle = _Bundle()

        with pytest.raises(NotFoundError) as exc_info:
            await bundle.service.set_weights(NOVEL_ID, USER_B, AdaptiveWeightsInput(preference=0.5))

        assert str(exc_info.value) == f"Novel ({NOVEL_ID}) not found"
        assert bundle.settings_repo.loads == []
        assert bundle.settings_repo.saves == []


class TestSnapshotsOwnership:
    """get_adaptive_snapshots: owner reads; foreign/unknown → 404, no read."""

    async def test_owner_reads_evidence(self) -> None:
        bundle = _Bundle()

        response = await bundle.service.get_adaptive_snapshots(NOVEL_ID, USER_A, limit=20)

        assert bundle.evidence_repo.calls == [(NOVEL_ID, 20)]
        assert len(response.items) == 1
        assert response.items[0].weights is not None
        assert response.items[0].weights.preference == 0.7

    async def test_foreign_raises_not_found_without_read(self) -> None:
        bundle = _Bundle()

        with pytest.raises(NotFoundError) as exc_info:
            await bundle.service.get_adaptive_snapshots(NOVEL_ID, USER_B)

        assert str(exc_info.value) == f"Novel ({NOVEL_ID}) not found"
        assert bundle.evidence_repo.calls == []

    async def test_unknown_shape_matches_foreign(self) -> None:
        bundle = _Bundle()
        unknown = uuid4()

        with pytest.raises(NotFoundError) as exc_info:
            await bundle.service.get_adaptive_snapshots(unknown, USER_A)

        assert str(exc_info.value) == f"Novel ({unknown}) not found"
        assert bundle.evidence_repo.calls == []


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
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


def _install_service(app: FastAPI, bundle: _Bundle) -> None:
    app.dependency_overrides[get_adaptive_context_service] = lambda: bundle.service


def _as_user(app: FastAPI, user_id: UUID) -> None:
    app.state.auth_user = str(user_id)


def _assert_404_novel(response, project_id: UUID) -> None:
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": f"Novel ({project_id}) not found", "code": "NOT_FOUND"}


class TestAdaptiveRoutesOwnership:
    """Owner unchanged over HTTP; foreign/unknown → 404 with zero effects."""

    async def test_owner_toggle_200(self, app, client) -> None:
        bundle = _Bundle(loaded=None)
        _install_service(app, bundle)

        response = await client.post(
            _TOGGLE_URL.format(project_id=NOVEL_ID), json={"enabled": False}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["enabled"] is False
        assert len(bundle.settings_repo.saves) == 1

    async def test_foreign_toggle_404_without_persistence(self, app, client) -> None:
        bundle = _Bundle()
        _install_service(app, bundle)
        _as_user(app, USER_B)

        response = await client.post(
            _TOGGLE_URL.format(project_id=NOVEL_ID), json={"enabled": False}
        )

        _assert_404_novel(response, NOVEL_ID)
        assert bundle.settings_repo.loads == []
        assert bundle.settings_repo.saves == []

    async def test_foreign_weights_404_shape_matches_unknown(self, app, client) -> None:
        bundle = _Bundle()
        _install_service(app, bundle)
        _as_user(app, USER_B)
        unknown = uuid4()

        foreign = await client.post(
            _WEIGHTS_URL.format(project_id=NOVEL_ID),
            json={"preference": 0.5, "voice_fidelity": 0.6},
        )
        unknown_response = await client.post(
            _WEIGHTS_URL.format(project_id=unknown),
            json={"preference": 0.5, "voice_fidelity": 0.6},
        )

        _assert_404_novel(foreign, NOVEL_ID)
        _assert_404_novel(unknown_response, unknown)
        assert bundle.settings_repo.saves == []

    async def test_owner_snapshots_200(self, app, client) -> None:
        bundle = _Bundle()
        _install_service(app, bundle)

        response = await client.get(_SNAPSHOTS_URL.format(project_id=NOVEL_ID))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["items"]) == 1
        assert bundle.evidence_repo.calls == [(NOVEL_ID, 20)]

    async def test_foreign_snapshots_404_without_read(self, app, client) -> None:
        bundle = _Bundle()
        _install_service(app, bundle)
        _as_user(app, USER_B)

        response = await client.get(_SNAPSHOTS_URL.format(project_id=NOVEL_ID))

        _assert_404_novel(response, NOVEL_ID)
        assert bundle.evidence_repo.calls == []
