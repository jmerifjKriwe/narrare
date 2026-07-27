"""Tests for AuthorVoiceRepository (RULE-14 JSONB persistence, ADR-074).

Verifies:
- load() returns the stored AuthorVoiceProfile (round-trip save → load).
- load() returns None when no row exists / column is NULL (RULE-11).
- load() returns None when the JSONB is malformed (Pydantic validation).
- save() upserts the profile (creates a row when none exists).
- clear() NULLs the column (the user returns to the default AI style).

Uses FakeSession (in-memory) — no DB I/O. Mirrors
``tests/unit/api/adaptive/test_repository.py`` (the ADR-069 precedent).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from narrare.analysis.author_voice_repository import (
    AuthorVoiceRepository,
    _json_to_profile,  # pyright: ignore[reportPrivateUsage]
    _profile_to_json,  # pyright: ignore[reportPrivateUsage]
)
from narrare_core.profiles.author_voice import AuthorVoiceProfile
from narrare_core.schemas.voice import VoiceAnalysis, VoiceMetrics


class _FakeResult:
    """Mimics the SQLAlchemy result shape the repository reads."""

    def __init__(self, row: dict[str, Any] | None, rowcount: int = 0) -> None:
        self._row = row
        self.rowcount = rowcount

    def scalar_one_or_none(self) -> Any:
        # Real SQLAlchemy scalar_one_or_none() returns the first column's
        # value (not a wrapped row dict). The repo selects
        # ProjectSettings.author_voice, so extract that key from the mocked
        # row dict to correctly simulate the production behaviour.
        if self._row is None:
            return None
        return self._row.get("author_voice")


class _FakeSession:
    """In-memory AsyncSession stand-in.

    The repository issues three statement kinds (select / update / delete).
    For each, the fake returns the seeded row + records the issued statement
    so tests can assert on it. The ``rowcount`` controls the save() insert
    branch (0 → insert a new ProjectSettings row).
    """

    def __init__(
        self,
        row: dict[str, Any] | None = None,
        *,
        update_rowcount: int = 1,
    ) -> None:
        self._row = row
        self._update_rowcount = update_rowcount
        self.add_calls: list[Any] = []
        self.flush_calls = 0
        self.last_stmt: Any = None

    async def execute(self, stmt: Any) -> _FakeResult:
        self.last_stmt = stmt
        # Distinguish by statement type — select returns the seeded row;
        # update/delete return a result whose rowcount drives the save branch.
        stmt_str = str(stmt)
        if "UPDATE" in stmt_str or "DELETE" in stmt_str:
            return _FakeResult(row=None, rowcount=self._update_rowcount)
        return _FakeResult(row=self._row)

    def add(self, model: Any) -> None:
        self.add_calls.append(model)

    async def flush(self) -> None:
        self.flush_calls += 1


def _make_profile() -> AuthorVoiceProfile:
    """Build a fully-populated profile for round-trip tests."""
    return AuthorVoiceProfile(
        voice_analysis=VoiceAnalysis(
            formality=0.7,
            vocabulary_level="complex",
            sentence_profile="varied",
            emotional_range="expressive",
            cultural_regional_markers="literary register",
            voice_examples=["The wind moved through the long grass."],
            voice_metrics=VoiceMetrics(
                avg_sentence_length=14.2,
                type_token_ratio=0.71,
                contraction_rate=0.05,
            ),
        ),
        author_examples=["The wind moved through the long grass."],
        # author_metrics is built by AuthorMetricsAnalyzer; use the Core type
        # for the round-trip (the metric group is part of the stored profile).
        author_metrics=None,
        updated_at="2026-07-27T00:00:00+00:00",
        is_fresh=True,
    )


class TestAuthorVoiceRepositoryLoad:
    """load() returns AuthorVoiceProfile when row exists; None otherwise."""

    @pytest.mark.asyncio
    async def test_load_returns_profile_when_row_exists(self) -> None:
        profile = _make_profile()
        row = {"author_voice": _profile_to_json(profile)}
        repo = AuthorVoiceRepository(_FakeSession(row=row))  # type: ignore[arg-type]
        result = await repo.load(novel_id=uuid4())
        assert result is not None
        assert result.voice_analysis is not None
        assert result.voice_analysis.formality == 0.7
        assert result.voice_analysis.vocabulary_level == "complex"
        assert result.author_examples == ["The wind moved through the long grass."]

    @pytest.mark.asyncio
    async def test_load_returns_none_when_no_row(self) -> None:
        repo = AuthorVoiceRepository(_FakeSession(row=None))  # type: ignore[arg-type]
        result = await repo.load(novel_id=uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_load_returns_none_when_column_null(self) -> None:
        """Existing rows have NULL author_voice — graceful fallback (RULE-11)."""
        row = {"author_voice": None}
        repo = AuthorVoiceRepository(_FakeSession(row=row))  # type: ignore[arg-type]
        result = await repo.load(novel_id=uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_load_returns_none_when_jsonb_malformed(self) -> None:
        """Malformed JSONB (wrong types on known fields) → None (RULE-11).

        ``AuthorVoiceProfile`` uses ``extra="allow"`` so unknown keys do not
        fail validation; a *truly* malformed payload violates the type of a
        known field (e.g. ``is_fresh`` not a bool) and is rejected by Pydantic.
        """
        row = {
            "author_voice": {
                # is_fresh is a known bool field; a list violates the type.
                "is_fresh": ["not", "a", "bool"],
            }
        }
        repo = AuthorVoiceRepository(_FakeSession(row=row))  # type: ignore[arg-type]
        result = await repo.load(novel_id=uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_load_returns_none_when_jsonb_wrong_type(self) -> None:
        """Non-dict JSONB (e.g. a list) → None (RULE-11)."""
        row = {"author_voice": ["not", "a", "dict"]}
        repo = AuthorVoiceRepository(_FakeSession(row=row))  # type: ignore[arg-type]
        result = await repo.load(novel_id=uuid4())
        assert result is None


class TestJsonToProfileHelper:
    """The _json_to_profile helper enforces the graceful-degradation contract."""

    def test_none_input_returns_none(self) -> None:
        assert _json_to_profile(None) is None

    def test_non_dict_input_returns_none(self) -> None:
        assert _json_to_profile(["a", "b"]) is None  # type: ignore[arg-type]
        assert _json_to_profile("not a dict") is None  # type: ignore[arg-type]

    def test_valid_dict_returns_profile(self) -> None:
        profile = _make_profile()
        as_json = _profile_to_json(profile)
        result = _json_to_profile(as_json)
        assert result is not None
        assert isinstance(result, AuthorVoiceProfile)

    def test_round_trip_preserves_descriptive_group(self) -> None:
        profile = _make_profile()
        result = _json_to_profile(_profile_to_json(profile))
        assert result is not None
        assert result.voice_analysis is not None
        assert result.voice_analysis.formality == 0.7
        assert result.voice_analysis.voice_examples == ["The wind moved through the long grass."]
        assert result.author_examples == ["The wind moved through the long grass."]

    def test_round_trip_preserves_metric_group(self) -> None:
        """The metric group survives the round-trip (Phase 2B drift reads it)."""
        profile = _make_profile()
        result = _json_to_profile(_profile_to_json(profile))
        assert result is not None
        assert result.voice_analysis is not None
        assert result.voice_analysis.voice_metrics is not None
        assert result.voice_analysis.voice_metrics.avg_sentence_length == 14.2


class TestAuthorVoiceRepositorySave:
    """save() upserts the author_voice JSONB column."""

    @pytest.mark.asyncio
    async def test_save_calls_flush(self) -> None:
        session = _FakeSession(row=None)
        repo = AuthorVoiceRepository(session)  # type: ignore[arg-type]
        await repo.save(novel_id=uuid4(), profile=_make_profile())
        assert session.flush_calls >= 1

    @pytest.mark.asyncio
    async def test_save_inserts_new_row_when_none_exists(self) -> None:
        """rowcount=0 → repository inserts a new ProjectSettings row."""
        session = _FakeSession(row=None, update_rowcount=0)
        repo = AuthorVoiceRepository(session)  # type: ignore[arg-type]
        await repo.save(novel_id=uuid4(), profile=_make_profile())
        assert len(session.add_calls) == 1

    @pytest.mark.asyncio
    async def test_save_updates_existing_row(self) -> None:
        """rowcount=1 → repository updates; no new row inserted."""
        session = _FakeSession(row=None, update_rowcount=1)
        repo = AuthorVoiceRepository(session)  # type: ignore[arg-type]
        await repo.save(novel_id=uuid4(), profile=_make_profile())
        assert len(session.add_calls) == 0


class TestAuthorVoiceRepositoryClear:
    """clear() NULLs the column (returns the user to the default AI style)."""

    @pytest.mark.asyncio
    async def test_clear_calls_flush(self) -> None:
        session = _FakeSession(row=None)
        repo = AuthorVoiceRepository(session)  # type: ignore[arg-type]
        await repo.clear(novel_id=uuid4())
        assert session.flush_calls >= 1
