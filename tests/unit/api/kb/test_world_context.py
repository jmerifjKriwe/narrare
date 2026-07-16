"""Unit tests for the KB world-context builder (RULE-04 helper).

Verifies the genuine runtime wiring of the ``{{world_context}}`` prompt
variable used by the kb/merge and kb/extract governed templates. The helper
mirrors the established KB-entity-fetching precedent
(``worldbuilding_entity_assembly.list_entities``) and the graceful-
degradation pattern used by the kb assist/improve services.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from narrare.kb._world_context import fetch_world_context, format_world_context

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


def _entry(
    name: str,
    entity_type: str = "character",
    metadata: dict[str, object] | None = None,
    body: str = "",
) -> SimpleNamespace:
    """Lightweight KBEntry stand-in (only the attributes the helper reads)."""
    return SimpleNamespace(
        name=name,
        entity_type=entity_type,
        metadata_=metadata or {},
        body=body,
    )


class _FakeKBRepo:
    """Fake KBRepositoryProtocol — only ``list_entries`` is exercised."""

    def __init__(self, entries: list[object], total: int | None = None) -> None:
        self._entries = entries
        self._total = total if total is not None else len(entries)
        self.list_entries = AsyncMock(return_value=(self._entries, self._total))


class _FailingKBRepo:
    """Fake repo whose ``list_entries`` always raises."""

    def __init__(self) -> None:
        self.list_entries = AsyncMock(side_effect=RuntimeError("repository offline"))


# ---------------------------------------------------------------------------
# format_world_context — pure formatting
# ---------------------------------------------------------------------------


class TestFormatWorldContext:
    def test_empty_entries_returns_empty_string(self) -> None:
        assert format_world_context([]) == ""

    def test_formats_name_and_entity_type(self) -> None:
        entries = [_entry("Elara", "character")]

        result = format_world_context(entries)  # type: ignore[arg-type]

        assert "Elara" in result
        assert "character" in result

    def test_non_empty_for_project_with_kb_entities(self) -> None:
        """A project with KB entities must yield a non-empty world context."""
        entries = [
            _entry("Elara", "character"),
            _entry("The Shimmering Keep", "location"),
        ]

        result = format_world_context(entries)  # type: ignore[arg-type]

        assert result != ""
        assert result.count("\n") == 1  # two entries -> one newline

    def test_includes_brief_description_from_metadata(self) -> None:
        entries = [
            _entry(
                "Elara",
                "character",
                metadata={"role": "protagonist of the saga"},
            )
        ]

        result = format_world_context(entries)  # type: ignore[arg-type]

        assert "protagonist of the saga" in result

    def test_includes_brief_description_from_body_when_no_metadata(self) -> None:
        entries = [_entry("Keep", "location", body="An ancient fortress.")]

        result = format_world_context(entries)  # type: ignore[arg-type]

        assert "An ancient fortress." in result

    def test_caps_number_of_entries(self) -> None:
        entries = [_entry(f"Entry {i}", "character") for i in range(50)]

        result = format_world_context(entries, max_entries=10)  # type: ignore[arg-type]

        assert result.count("\n") == 9  # 10 entries -> 9 newlines


# ---------------------------------------------------------------------------
# fetch_world_context — async + graceful degradation (RULE-11)
# ---------------------------------------------------------------------------


class TestFetchWorldContext:
    @pytest.mark.asyncio
    async def test_returns_non_empty_when_entries_exist(self) -> None:
        repo = _FakeKBRepo([_entry("Elara", "character")])

        result = await fetch_world_context(repo, uuid4())  # type: ignore[arg-type]

        assert result != ""
        assert "Elara" in result

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_entries(self) -> None:
        repo = _FakeKBRepo([])

        result = await fetch_world_context(repo, uuid4())  # type: ignore[arg-type]

        assert result == ""

    @pytest.mark.asyncio
    async def test_degrades_gracefully_on_repo_failure(self) -> None:
        """RULE-11: a repo failure must not crash the caller."""
        repo = _FailingKBRepo()

        result = await fetch_world_context(repo, uuid4())  # type: ignore[arg-type]

        assert result == ""

    @pytest.mark.asyncio
    async def test_passes_entity_type_filter_to_repo(self) -> None:
        repo = _FakeKBRepo([_entry("Elara", "character")])

        await fetch_world_context(repo, uuid4(), entity_type="character")  # type: ignore[arg-type]

        kwargs = repo.list_entries.call_args.kwargs
        assert kwargs.get("entity_type") == "character"
