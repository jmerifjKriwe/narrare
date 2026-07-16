"""Shared test doubles for the KB-context provider tests (ADR-067).

Holds the lightweight ``KBEntry`` stand-in, the fake/failing KB and
relationship repositories, and the provider factory used across the split
KB-context provider test modules. Only the repositories are faked; the
provider's fetch path exercises the real ``list_entities`` /
``format_entities`` / ``format_relationships``.

Named ``_kb_context_helpers`` to match the directory's ``_*_helpers`` /
``_*_fakes`` convention (e.g. ``_extraction_helpers``, ``_merge_test_helpers``).
Symbols are public (no leading underscore) because they are imported by the
two sibling test modules.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from narrare.kb._context_provider import KBContextProvider

#: Relationship-edge tuple shape expected by ``format_relationships``:
#: ``(source_name, rel_type, label, target_name, direction)``.
Edge = tuple[str, str, str | None, str, str]


def make_entry(
    name: str,
    entity_type: str = "character",
    *,
    body: str = "",
    source: str = "manual",
    review_status: str = "approved",
    status: str = "canon",
    metadata: dict[str, object] | None = None,
) -> SimpleNamespace:
    """Lightweight ``KBEntry`` stand-in (only the attributes the provider reads)."""
    return SimpleNamespace(
        id=uuid4(),
        entity_type=entity_type,
        name=name,
        body=body,
        updated_at=None,
        metadata_=metadata or {},
        status=status,
        source=source,
        review_status=review_status,
    )


class FakeKBRepo:
    """Fake ``KBRepositoryProtocol`` — only ``list_entries`` is exercised."""

    def __init__(self, entries: list[SimpleNamespace]) -> None:
        self._entries = entries
        self.list_entries = AsyncMock(return_value=(self._entries, len(self._entries)))


class FailingKBRepo:
    """Fake repo whose ``list_entries`` always raises (RULE-11 path)."""

    def __init__(self) -> None:
        self.list_entries = AsyncMock(side_effect=RuntimeError("repository offline"))


class FakeRelRepo:
    """Fake ``RelationshipRepositoryProtocol`` — only ``get_relationships_with_names``."""

    def __init__(self, edges: list[Edge]) -> None:
        self.get_relationships_with_names = AsyncMock(return_value=edges)


class FailingRelRepo:
    """Fake rel repo whose ``get_relationships_with_names`` always raises."""

    def __init__(self) -> None:
        self.get_relationships_with_names = AsyncMock(
            side_effect=RuntimeError("relationship store offline")
        )


def make_provider(
    kb_repo: object | None,
    rel_repo: object | None = None,
) -> KBContextProvider:
    """Construct a ``KBContextProvider`` from fake repos.

    The fakes only partially implement the repository Protocols; the single
    ``type: ignore`` here silences that Protocol mismatch once for every test.
    """
    return KBContextProvider(kb_repo, rel_repo)  # type: ignore[arg-type]


def populated_entries() -> list[SimpleNamespace]:
    """One character, one location, one faction."""
    return [
        make_entry("Elara", "character", body="A gifted storm-caller."),
        make_entry("The Shimmering Keep", "location", body="An ancient fortress."),
        make_entry("Night Watch", "faction", body="An order of wardens."),
    ]
