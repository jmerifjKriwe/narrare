# tests/unit/api/settings/test_writing_goals.py
"""Novel ``writing_goals`` storage + GoalSource wiring (STATS-001 E5, spec E-4/E-5).

One behavior — the novel writing-goal vertical — tested at the lowest level
per layer (house precedent: the recorder test file merges layers serving one
behavior):

- **PATCH surface**: v1 shape validation (``target_words`` int ≥ 0 or null;
  garbage ⇒ 422 at the FastAPI boundary via pydantic; unknown keys forbidden —
  whole-object replace semantics v1) and the repository-contract dump (plain
  dict via the field serializer, sibling fields untouched).
- **Repository round-trip** over the fake upsert session: set → stored,
  unset (``{"target_words": null}``) → stored, and an autosave-only PATCH
  never touches ``writing_goals``.
- **``parse_target_words``**: pure typed-accessor matrix (NULL column, empty,
  null target, int, non-int garbage, bool). Shape here — the ≤ 0 "no goal"
  POLICY stays in the analytics service (separation pinned by
  ``test_negative_target_passes_through_shape_not_policy``).
- **``ProjectSettingsGoalSource``**: pure adapter over a fake repository
  (set / NULL / missing row — the ≤ 0 policy stays downstream) + runtime
  ``GoalSource`` conformance; the repository's read-only
  ``get_writing_goals`` query shape is pinned at statement level.
- **Service with the REAL source**: goal block appears in the writing report
  when set, absent when unset (E4 pinned the seam with a fake source; E5
  pins the real one end-to-end at service level over a fake repository).

No real DB: the fake session models the house upsert ``get()`` (mirrors
``test_settings_repository_update.py``), ``FakeDbSession`` pins the
read-only repository query, and the GoalSource adapter rides a fake repo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Select

from narrare.analytics.contracts import GoalSource, WritingGoalProgress
from narrare.analytics.writing_service import WritingQueryService
from narrare.settings.schemas import (
    ProjectSettingsResponse,
    UpdateProjectSettingsRequest,
)
from narrare.settings.writing_goals import ProjectSettingsGoalSource, parse_target_words
from tests.fakes.fake_db_session import FakeDbSession, FakeResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.settings.repository import ProjectSettingsRepository

_NOVEL_ID = uuid4()


# ---------------------------------------------------------------------------
# Fake session for the repository update path (upsert get() + setattr flush)
# ---------------------------------------------------------------------------


class _GoalsUpdateSession:
    """Fake session tracking upsert-based ``get()`` state (house pattern).

    First SELECT misses; the ON CONFLICT DO NOTHING INSERT stores the row;
    the re-SELECT reads it back. ``flush`` persists setattr changes.
    """

    def __init__(self) -> None:
        self._stored: Any = None
        self.insert_count = 0

    def add(self, entity: Any) -> None:
        raise AssertionError("add() must not be called in the upsert path")

    async def flush(self) -> None:
        pass

    async def refresh(self, entity: Any) -> None:
        pass

    async def execute(self, stmt: Any) -> Any:
        if isinstance(stmt, Select):
            return FakeResult(value=self._stored)
        params = stmt.compile().params
        from narrare.settings.models import ProjectSettings

        self._stored = ProjectSettings(**params)
        self.insert_count += 1
        return FakeResult(value=None)


def _repo() -> tuple[Any, _GoalsUpdateSession]:
    from narrare.settings.repository import ProjectSettingsRepository

    session = _GoalsUpdateSession()
    return ProjectSettingsRepository(cast("AsyncSession", session)), session


# ---------------------------------------------------------------------------
# PATCH surface: UpdateProjectSettingsRequest validation + dump contract
# ---------------------------------------------------------------------------


class TestWritingGoalsPatchSchema:
    """``writing_goals`` on the project-settings PATCH (garbage ⇒ 422)."""

    def test_valid_target_words_dumps_as_plain_dict(self) -> None:
        """Set: the repository-contract dump carries a plain dict (serializer)."""
        request = UpdateProjectSettingsRequest.model_validate(
            {"writing_goals": {"target_words": 50000}}
        )
        assert request.writing_goals is not None
        assert request.writing_goals.target_words == 50000
        # The repository setattr-loop stores exactly this value in the JSONB
        # column — a pydantic object here would break JSON serialization.
        assert request.model_dump(exclude_none=True) == {"writing_goals": {"target_words": 50000}}

    def test_null_target_words_is_a_valid_unset(self) -> None:
        """``{"target_words": null}`` is the v1 unset (whole-object replace)."""
        request = UpdateProjectSettingsRequest.model_validate(
            {"writing_goals": {"target_words": None}}
        )
        assert request.model_dump(exclude_none=True) == {"writing_goals": {"target_words": None}}

    @pytest.mark.parametrize("garbage", [-5, "abc", 1.5, [50000], {"a": 1}])
    def test_garbage_target_words_is_rejected(self, garbage: Any) -> None:
        """Non-conforming ``target_words`` ⇒ ValidationError ⇒ FastAPI 422.

        bool is deliberately absent: pydantic v2 lax mode coerces
        ``True/False`` to ``1/0`` for EVERY int field project-wide (sibling
        ``autosave_interval`` behaves identically) — a degenerate int the
        ≤ 0 service policy already neutralizes, not garbage.
        """
        with pytest.raises(ValidationError):
            UpdateProjectSettingsRequest.model_validate(
                {"writing_goals": {"target_words": garbage}}
            )

    def test_unknown_keys_inside_the_object_are_rejected(self) -> None:
        """Whole-object replace v1: exactly one documented key, extra forbidden."""
        with pytest.raises(ValidationError):
            UpdateProjectSettingsRequest.model_validate(
                {"writing_goals": {"target_words": 1, "daily_words": 2}}
            )

    def test_omitted_field_touches_nothing(self) -> None:
        """PATCH isolation: only asked-for keys appear in the dump."""
        request = UpdateProjectSettingsRequest(autosave_interval=60)
        assert request.model_dump(exclude_none=True) == {"autosave_interval": 60}

    def test_response_schema_exposes_the_typed_shape(self) -> None:
        """GET round-trip: the stored dict validates into the nested payload."""
        payload = {
            "novel_id": str(_NOVEL_ID),
            "autosave_interval": 30,
            "default_language": "en",
            "ai_provider": "",
            "ai_model": "",
            "model_overrides": "{}",
            "category_overrides": {},
            "intent_overrides": {},
            "token_limit_overrides": {},
            "use_series_voice": True,
            "writing_goals": {"target_words": 50000},
            "updated_at": datetime(2026, 10, 8, tzinfo=UTC).isoformat(),
        }
        response = ProjectSettingsResponse.model_validate(payload)
        assert response.writing_goals is not None
        assert response.writing_goals.target_words == 50000

        unset = ProjectSettingsResponse.model_validate({**payload, "writing_goals": None})
        assert unset.writing_goals is None


# ---------------------------------------------------------------------------
# Repository round-trip (fake upsert session — no DB)
# ---------------------------------------------------------------------------


class TestProjectSettingsRepositoryWritingGoals:
    """set / unset / read round-trip + PATCH isolation on the repository."""

    async def test_set_then_unset_round_trip(self) -> None:
        """Set stores the v1 shape; unset replaces it with the null target."""
        repo, _ = _repo()

        set_result = await repo.update(
            _NOVEL_ID,
            UpdateProjectSettingsRequest.model_validate({"writing_goals": {"target_words": 50000}}),
        )
        assert set_result.writing_goals == {"target_words": 50000}

        unset_result = await repo.update(
            _NOVEL_ID,
            UpdateProjectSettingsRequest.model_validate({"writing_goals": {"target_words": None}}),
        )
        assert unset_result.writing_goals == {"target_words": None}

    async def test_autosave_only_patch_never_touches_writing_goals(self) -> None:
        """PATCH touches only the keys it is asked to (sibling isolation)."""
        repo, session = _repo()
        await repo.update(
            _NOVEL_ID,
            UpdateProjectSettingsRequest.model_validate({"writing_goals": {"target_words": 50000}}),
        )

        result = await repo.update(_NOVEL_ID, UpdateProjectSettingsRequest(autosave_interval=99))
        assert result.autosave_interval == 99
        assert result.writing_goals == {"target_words": 50000}
        assert session.insert_count == 1  # no second auto-create upsert

    async def test_unset_goal_on_fresh_row_stays_none(self) -> None:
        """A fresh settings row without any goal PATCH has ``writing_goals`` None."""
        repo, _ = _repo()
        result = await repo.update(_NOVEL_ID, UpdateProjectSettingsRequest(default_language="de"))
        assert result.writing_goals is None


# ---------------------------------------------------------------------------
# Typed accessor: parse_target_words (shape, not policy)
# ---------------------------------------------------------------------------


class TestParseTargetWords:
    """Pure matrix over the v1 JSONB shape ``{"target_words": int | null}``."""

    def test_null_column_reads_as_no_goal(self) -> None:
        assert parse_target_words(None) is None

    def test_empty_object_reads_as_no_goal(self) -> None:
        assert parse_target_words({}) is None

    def test_null_target_reads_as_no_goal(self) -> None:
        assert parse_target_words({"target_words": None}) is None

    def test_int_target_passes_through(self) -> None:
        assert parse_target_words({"target_words": 50000}) == 50000

    def test_negative_target_passes_through_shape_not_policy(self) -> None:
        """The accessor reports the stored int; the ≤ 0 no-goal POLICY lives
        in the analytics service (``_goal_block``). One concern each."""
        assert parse_target_words({"target_words": -5}) == -5

    @pytest.mark.parametrize("hand_edited", ["50000", 1.5, True, [50000]])
    def test_non_int_targets_read_as_no_goal(self, hand_edited: Any) -> None:
        """Hand-edited/foreign rows degrade to "no goal" — never crash the read."""
        assert parse_target_words({"target_words": hand_edited}) is None


# ---------------------------------------------------------------------------
# ProjectSettingsGoalSource over a fake repository (+ read-only query pin)
# ---------------------------------------------------------------------------


class _FakeGoalsRepo:
    """ProjectSettingsRepository stand-in recording ``get_writing_goals`` reads."""

    def __init__(self, stored: dict[str, object] | None) -> None:
        self._stored = stored
        self.read_novel_ids: list[Any] = []

    async def get_writing_goals(self, novel_id: Any) -> dict[str, object] | None:
        self.read_novel_ids.append(novel_id)
        return self._stored


class TestProjectSettingsGoalSource:
    """Pure adapter over the repository's read-only goals read."""

    def _source(self, stored: dict[str, object] | None) -> ProjectSettingsGoalSource:
        return ProjectSettingsGoalSource(cast("ProjectSettingsRepository", _FakeGoalsRepo(stored)))

    async def test_set_goal_reads_the_target(self) -> None:
        repo = _FakeGoalsRepo({"target_words": 123})
        source = ProjectSettingsGoalSource(cast("ProjectSettingsRepository", repo))

        assert await source.target_words(_NOVEL_ID) == 123
        # Passthrough: the adapter forwards the novel id — no caching, no
        # filtering (an unknown novel simply reads None downstream).
        assert repo.read_novel_ids == [_NOVEL_ID]

    async def test_missing_row_reads_as_no_goal(self) -> None:
        """No settings row (never auto-created — reads must not write)."""
        assert await self._source(None).target_words(_NOVEL_ID) is None

    async def test_null_column_and_null_target_read_as_no_goal(self) -> None:
        cases: tuple[dict[str, object] | None, ...] = (
            None,
            {"target_words": None},
            {},
        )
        for stored in cases:
            assert await self._source(stored).target_words(_NOVEL_ID) is None

    def test_satisfies_the_goal_source_protocol(self) -> None:
        """E5's real source structurally satisfies the E4 seam (RULE-03)."""
        assert isinstance(self._source(None), GoalSource)


class TestGetWritingGoalsQuery:
    """The repository read behind the adapter: read-only, PK-scoped, single column."""

    async def test_query_shape_scopes_novel_and_reads_only_the_goal_column(self) -> None:
        from narrare.settings.repository import ProjectSettingsRepository

        session = FakeDbSession(results=[FakeResult(value={"target_words": 1})])
        repo = ProjectSettingsRepository(cast("AsyncSession", session))

        assert await repo.get_writing_goals(_NOVEL_ID) == {"target_words": 1}
        assert len(session.statements) == 1
        sql = str(session.statements[0])
        assert "project_settings" in sql
        assert "writing_goals" in sql
        # No INSERT/ON CONFLICT: a reporting read must never auto-create
        # (contrast ProjectSettingsRepository.get — IDOR S11a).
        assert "insert" not in sql.lower()


# ---------------------------------------------------------------------------
# Service level: the REAL source plugged into WritingQueryService
# ---------------------------------------------------------------------------


class _StubWritingRepo:
    """Minimal WritingStatsQueryRepository stub (dailies/window unused here)."""

    async def daily_totals(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    async def all_time_word_total(self, *args: Any, **kwargs: Any) -> int:
        return 0

    async def novel_word_total(self, novel_id: Any) -> int:
        return 42000


class TestWritingServiceWithRealGoalSource:
    """E4 pinned the seam with a fake source; E5 pins the real one."""

    def _service(self, stored: dict[str, object] | None) -> WritingQueryService:
        return WritingQueryService(
            _StubWritingRepo(),  # pyright: ignore[reportArgumentType] — stub in test
            goal_source=ProjectSettingsGoalSource(
                cast("ProjectSettingsRepository", _FakeGoalsRepo(stored))
            ),
        )

    async def test_goal_block_appears_when_target_is_set(self) -> None:
        report = await self._service({"target_words": 50000}).writing_report(uuid4(), _NOVEL_ID)
        assert report.goal == WritingGoalProgress(
            target_words=50000, current_words=42000, progress_pct=84.0
        )

    @pytest.mark.parametrize("stored", [None, {"target_words": None}, {}])
    async def test_goal_block_absent_when_unset(self, stored: Any) -> None:
        report = await self._service(stored).writing_report(uuid4(), _NOVEL_ID)
        assert report.goal is None
