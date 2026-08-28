"""Unit tests for AdaptiveContextService.get_adaptive_snapshots (ADR-070)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare.adaptive.service import AdaptiveContextService
from narrare_core.ai_invocation._enums import (
    AuditState,
    KBSuggestedStatus,
    PreferenceStatus,
)
from narrare_core.ai_invocation.evidence_models import FeatureInvocationEvidence
from tests.unit.api.adaptive.conftest import (  # noqa: TC001 - fixture type, keeps conftest import local
    _PermissiveNovelRepo,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.adaptive.contracts import AdaptiveSettingsRepositoryProtocol
    from narrare_core.ai_invocation.adaptive_contracts import AdaptiveContextProvider


class _FakeEvidenceRepo:
    """Fake EvidenceRepositoryImpl — records calls, returns canned snapshots."""

    def __init__(self, snapshots: list[FeatureInvocationEvidence]) -> None:
        self._snapshots = snapshots
        self.last_novel_id: object | None = None
        self.last_limit: int | None = None

    async def get_adaptive_snapshots(
        self,
        novel_id: UUID,
        *,
        limit: int = 20,
    ) -> list[FeatureInvocationEvidence]:
        self.last_novel_id = novel_id
        self.last_limit = limit
        return self._snapshots


def _snapshot(*, weights: dict[str, float] | None) -> FeatureInvocationEvidence:
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
        novel_id=uuid4(),
        created_at=datetime(2026, 7, 23, tzinfo=UTC),
        adaptive_source_summary={"summary": "preferences"},
        adaptive_weights=weights,
    )


@pytest.fixture
def service(
    fake_provider: AdaptiveContextProvider,
    fake_settings_repo: AdaptiveSettingsRepositoryProtocol,
    fake_novel_repo: _PermissiveNovelRepo,
) -> tuple[AdaptiveContextService, _FakeEvidenceRepo]:
    repo = _FakeEvidenceRepo(snapshots=[_snapshot(weights={"preference": 0.7})])
    return (
        AdaptiveContextService(
            provider=fake_provider,
            settings_repo=fake_settings_repo,
            evidence_repo=repo,
            novel_repo=fake_novel_repo,
        ),
        repo,
    )


class TestGetAdaptiveSnapshots:
    async def test_returns_items_and_passes_scope(
        self,
        service: tuple[AdaptiveContextService, _FakeEvidenceRepo],
    ) -> None:
        svc, repo = service
        novel = uuid4()
        response = await svc.get_adaptive_snapshots(project_id=novel, user_id=uuid4(), limit=20)
        assert repo.last_novel_id == novel
        assert repo.last_limit == 20
        assert len(response.items) == 1
        item = response.items[0]
        assert item.source_summary == {"summary": "preferences"}
        assert item.weights is not None
        assert item.weights.preference == 0.7
        assert item.created_at == datetime(2026, 7, 23, tzinfo=UTC)

    async def test_empty_repo_yields_empty_response(
        self,
        fake_provider: AdaptiveContextProvider,
        fake_settings_repo: AdaptiveSettingsRepositoryProtocol,
        fake_novel_repo: _PermissiveNovelRepo,
    ) -> None:
        repo = _FakeEvidenceRepo(snapshots=[])
        svc = AdaptiveContextService(
            provider=fake_provider,
            settings_repo=fake_settings_repo,
            evidence_repo=repo,
            novel_repo=fake_novel_repo,
        )
        response = await svc.get_adaptive_snapshots(project_id=uuid4(), user_id=uuid4())
        assert response.items == []
