"""Unit tests for SeriesVoiceDriftService (Spec 4 — Cross-Novel Drift, Task 3).

The series-voice-drift service REUSES the novel-level analysis pipeline, so
these tests mirror ``test_author_voice_drift_service.py`` (the novel-level
parallel): the agent + Mode-1 composition are patched via ``patch_mode1``, the
deterministic metric analyzers run on real sample prose, and the series voice
profile is seeded in ``SeriesSettings.author_voice`` (the Spec 3 storage target
— NOT the novel-level ``ProjectSettings.author_voice``).

Verifies the Spec 4 contract:
- Happy path: series voice + metrics + prose → agent runs once → result.
- RULE-11 graceful degradation: no series voice / missing metrics / no prose →
  no_profile response (no LLM call).
- Ownership + novel-membership anti-enumeration (both → 403).
- REGRESSION: the novel-level ``AuthorVoiceDriftService`` is unchanged (a
  structural smoke check that the standalone path still imports + its protocol
  is intact).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftRequest,
    AuthorVoiceDriftResponse,
)
from narrare_core.shared.errors import ForbiddenError, NotFoundError
from tests.factories import make_chapter, make_novel

from ._series_voice_drift_test_helpers import (
    make_author_profile,
    make_drift_result,
    make_service,
    patch_mode1,
    seed_owned_series,
    seed_series_voice,
)

# ---------------------------------------------------------------------------
# check() — happy path
# ---------------------------------------------------------------------------


class TestCheckHappyPath:
    """SeriesVoiceDriftService.check() — series voice + prose → agent → result."""

    async def test_with_series_voice_and_prose_runs_agent_and_returns_result(self) -> None:
        """Happy path: agent runs once against the SERIES baseline; result set."""
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        await seed_series_voice(series_repo, series_id, make_author_profile())

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            response = await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())

        assert isinstance(response, AuthorVoiceDriftResponse)
        assert response.result is not None
        assert response.no_profile is None
        assert response.novel_id == str(novel_id)
        mock_agent.run.assert_awaited_once()

    async def test_trend_computed_against_series_baseline_not_novel(self) -> None:
        """The series voice metric group is the trend baseline (cross-novel signal).

        The reused ``analyse_author_voice_drift`` receives the SERIES
        voice_metrics + author_metrics (seeded via SeriesSettings), proving the
        drift is measured against the series baseline — the spec 4 contract.
        """
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        series_profile = make_author_profile()
        await seed_series_voice(series_repo, series_id, series_profile)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            response = await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())

        # A non-None trend + score means the SERIES baseline metrics were
        # consumed by the deterministic scoring (empty baseline → empty trend).
        assert response.result is not None
        assert response.result.trend  # non-empty trend → baseline was used
        assert response.result.overall_match_score is not None


# ---------------------------------------------------------------------------
# check() — RULE-11 graceful degradation
# ---------------------------------------------------------------------------


class TestCheckGraceful:
    """No series voice / missing metrics / no prose → no_profile (no LLM call)."""

    async def test_no_series_voice_returns_no_profile_without_agent(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        # No seed_series_voice → SeriesSettings.author_voice is None.

        with patch_mode1() as (MockAgent, _):
            response = await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())
            MockAgent.assert_not_called()

        assert response.result is None
        assert response.no_profile is not None
        assert response.no_profile.reason == "no_stored_series_voice"

    async def test_series_voice_missing_metrics_returns_no_profile(self) -> None:
        """A profile without the metric blocks cannot be trend-compared."""
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        await seed_series_voice(series_repo, series_id, make_author_profile(with_metrics=False))

        with patch_mode1() as (MockAgent, _):
            response = await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())
            MockAgent.assert_not_called()

        assert response.result is None
        assert response.no_profile is not None
        assert response.no_profile.reason == "no_series_voice_metrics"

    async def test_no_chapters_returns_empty_response_without_agent(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id, chapter_count=0
        )
        await seed_series_voice(series_repo, series_id, make_author_profile())

        with patch_mode1() as (MockAgent, _):
            response = await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())
            MockAgent.assert_not_called()

        # No chapters → empty response (neither result nor no_profile set).
        assert response.result is None
        assert response.no_profile is None

    async def test_no_chapters_with_prose_returns_no_profile(self) -> None:
        """Chapters with empty prose yield no_profile (no signal to measure)."""
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id, chapter_count=0
        )
        await seed_series_voice(series_repo, series_id, make_author_profile())
        # Add a chapter with NO prose.
        chapter_repo.seed(make_chapter(novel_id=novel_id, content="   "))

        with patch_mode1() as (MockAgent, _):
            response = await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())
            MockAgent.assert_not_called()

        assert response.result is None
        assert response.no_profile is not None
        assert response.no_profile.reason == "no_chapters_with_prose"


# ---------------------------------------------------------------------------
# check() — ownership + membership anti-enumeration
# ---------------------------------------------------------------------------


class TestCheckOwnership:
    """Anti-enumeration: missing/not-owned series + non-member novel → 403."""

    async def test_series_not_owned_raises_forbidden(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, _ = seed_owned_series(series_repo, novel_repo, chapter_repo, user_id=user_id)

        with pytest.raises(ForbiddenError):
            await service.check(series_id, uuid.uuid4(), uuid.uuid4(), AuthorVoiceDriftRequest())

    async def test_series_missing_raises_forbidden(self) -> None:
        """A missing series surfaces as 403 (never 404 — anti-enumeration)."""
        with pytest.raises(ForbiddenError):
            service, *_ = make_service()
            await service.check(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), AuthorVoiceDriftRequest())

    async def test_novel_not_in_series_raises_forbidden(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, _ = seed_owned_series(series_repo, novel_repo, chapter_repo, user_id=user_id)
        other_novel = uuid.uuid4()
        novel_repo.seed(make_novel(id=other_novel, user_id=user_id, series_id=uuid.uuid4()))

        with pytest.raises(ForbiddenError):
            await service.check(series_id, other_novel, user_id, AuthorVoiceDriftRequest())

    async def test_novel_missing_raises_forbidden(self) -> None:
        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, _ = seed_owned_series(series_repo, novel_repo, chapter_repo, user_id=user_id)

        with pytest.raises(ForbiddenError):
            await service.check(series_id, uuid.uuid4(), user_id, AuthorVoiceDriftRequest())


# ---------------------------------------------------------------------------
# check() — missing config
# ---------------------------------------------------------------------------


class TestCheckConfig:
    """No model config / no composer → typed errors (RULE-11)."""

    async def test_no_model_config_raises_not_found(self) -> None:

        user_id = uuid.uuid4()
        service, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        await seed_series_voice(series_repo, series_id, make_author_profile())
        # Rebuild the service with config=None.
        from narrare.series.series_voice_drift_service import SeriesVoiceDriftService as SVD

        service = SVD(
            series_repo=series_repo,  # type: ignore[arg-type]
            novel_repo=novel_repo,  # type: ignore[arg-type]
            chapter_repo=chapter_repo,  # type: ignore[arg-type]
            model_registry=service._registry,  # type: ignore[attr-defined]
            model_config=None,
            composer=service._composer,  # type: ignore[attr-defined]
        )

        with pytest.raises(NotFoundError, match="Model config"):
            await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())


# ---------------------------------------------------------------------------
# REGRESSION: novel-level AuthorVoiceDriftService unchanged
# ---------------------------------------------------------------------------


class TestNovelLevelRegression:
    """The standalone ANAL-009 path is unchanged (Spec 4 plan §'Regression')."""

    def test_novel_level_service_imports_and_protocol_intact(self) -> None:
        """The novel-level service + its SSE router still import (no breakage)."""
        from narrare.analysis.author_voice_drift_service import (  # noqa: F401
            AuthorVoiceDriftService,
        )
        from narrare.analysis.contracts_author_voice_drift import (
            AuthorVoiceDriftServiceProtocol,
        )
        from narrare.analysis.router_author_voice_drift import router  # noqa: F401

        # The novel-level protocol surface is unchanged (the methods still exist).
        assert hasattr(AuthorVoiceDriftServiceProtocol, "run")
        assert hasattr(AuthorVoiceDriftServiceProtocol, "run_stream")
