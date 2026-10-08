# tests/unit/api/settings/test_writing_goals_corrupt_rows.py
"""Corrupt stored ``writing_goals`` rows degrade everywhere (STATS-001 E5, fix round 1).

RULE-04 sibling split of ``test_writing_goals.py`` — the corrupt-row/degrade
group moved as one unit (same behavior, class-level boundary): JSONB is
schemaless, so a hand-edited/foreign stored value must never fail a read —

- **``parse_target_words``**: pure typed-accessor matrix (NULL column, empty,
  null target, int) + the non-int garbage matrix (nested and top-level rows
  read as "no goal", never raise). Shape here — the ≤ 0 "no goal" POLICY
  stays in the analytics service (separation pinned by
  ``test_negative_target_passes_through_shape_not_policy``).
- **Corrupt stored rows** (fix round 1, coordinator ruling "graceful
  everywhere"): settings GET passes the raw value through with a 200 (the
  response side is deliberately loose; strict v1 shape lives on the request
  payload) while the same row through the analytics vertical (REAL goal
  source) reports "no goal".

No real DB: the GoalSource adapter rides a fake repo and the analytics ride a
stub repository — both fakes duplicated trivially from the sibling file so
the group moves as one unit (same-dir sibling modules, house pattern).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from narrare.analytics.writing_service import WritingQueryService
from narrare.settings.writing_goals import ProjectSettingsGoalSource, parse_target_words
from tests.unit.api.settings._ownership_helpers import (
    NOVEL_ID,
    _existing_settings,
    _novel,
    install_session,
)

if TYPE_CHECKING:
    from narrare.analytics.contracts import WritingReport
    from narrare.settings.repository import ProjectSettingsRepository


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

    @pytest.mark.parametrize(
        "stored",
        [
            pytest.param({"target_words": "50000"}, id="nested-string-target"),
            pytest.param({"target_words": 1.5}, id="nested-float-target"),
            pytest.param({"target_words": True}, id="nested-bool-target"),
            pytest.param({"target_words": [50000]}, id="nested-list-target"),
            pytest.param(50000, id="top-level-int-row"),
            pytest.param("x", id="top-level-string-row"),
            pytest.param([1], id="top-level-list-row"),
            pytest.param(True, id="top-level-bool-row"),
        ],
    )
    def test_non_int_targets_read_as_no_goal(self, stored: Any) -> None:
        """Hand-edited/foreign rows degrade to "no goal" — never crash the read.

        Covers non-int targets nested in the documented object shape AND
        corrupt top-level rows (fix round 1): JSONB is schemaless, so a
        non-dict value reaches the accessor straight from the column and
        must read as "no goal", never raise.
        """
        assert parse_target_words(stored) is None


# ---------------------------------------------------------------------------
# Fakes — duplicated trivially from test_writing_goals.py (both files need both)
# ---------------------------------------------------------------------------


class _FakeGoalsRepo:
    """ProjectSettingsRepository stand-in recording ``get_writing_goals`` reads.

    ``stored`` is deliberately ``object | None`` — a corrupt JSONB value is
    exactly what the DB can deliver despite the repository's dict annotation
    (fix round 1), and the real source must degrade on it.
    """

    def __init__(self, stored: object | None) -> None:
        self._stored = stored
        self.read_novel_ids: list[Any] = []

    async def get_writing_goals(self, novel_id: Any) -> object | None:
        self.read_novel_ids.append(novel_id)
        return self._stored


class _StubWritingRepo:
    """Minimal WritingStatsQueryRepository stub (dailies/window unused here)."""

    async def daily_totals(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    async def all_time_word_total(self, *args: Any, **kwargs: Any) -> int:
        return 0

    async def novel_word_total(self, novel_id: Any) -> int:
        return 42000


# ---------------------------------------------------------------------------
# Corrupt stored rows degrade everywhere (fix round 1 — coordinator ruling)
# ---------------------------------------------------------------------------


class TestCorruptStoredRowDegradesGracefully:
    """A hand-edited/foreign JSONB row must never fail a read.

    Router level: the settings GET passes the raw stored value through
    (the response side is deliberately loose) with a 200. Same row through
    the analytics vertical: "no goal". Queued fake results mirror the
    proven S11a ownership-test wiring (novel lookup, then settings row).
    """

    _PROJECT_URL = "/api/v1/settings/novels/{novel_id}"

    async def test_corrupt_dict_row_gets_200_and_analytics_shows_no_goal(self, app, client) -> None:
        """Corrupt value inside the object: raw passthrough + no goal."""
        settings = _existing_settings()
        settings.writing_goals = {"target_words": "50000"}
        install_session(app, _novel(), settings)

        response = await client.get(self._PROJECT_URL.format(novel_id=NOVEL_ID))

        assert response.status_code == 200
        assert response.json()["writing_goals"] == {"target_words": "50000"}

        report = await self._analytics_report(settings.writing_goals)
        assert report.goal is None

    async def test_top_level_non_dict_row_still_gets_200(self, app, client) -> None:
        """Pins the response field being ``object | None``, not dict-typed.

        A dict-typed annotation would let pydantic reject the row and 500
        the GET — the exact corruption class ``parse_target_words`` guards
        against. Deliberate annotation bypass: this is DB-level corruption.
        """
        settings = _existing_settings()
        settings.writing_goals = cast("dict[str, object] | None", 50000)
        install_session(app, _novel(), settings)

        response = await client.get(self._PROJECT_URL.format(novel_id=NOVEL_ID))

        assert response.status_code == 200
        assert response.json()["writing_goals"] == 50000

    @staticmethod
    async def _analytics_report(stored: object | None) -> WritingReport:
        """Writing report over the REAL goal source with the stored value."""
        return await WritingQueryService(
            _StubWritingRepo(),  # pyright: ignore[reportArgumentType] — stub in test
            goal_source=ProjectSettingsGoalSource(
                cast("ProjectSettingsRepository", _FakeGoalsRepo(stored))
            ),
        ).writing_report(uuid4(), NOVEL_ID)
