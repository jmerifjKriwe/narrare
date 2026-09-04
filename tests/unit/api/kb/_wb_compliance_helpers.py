"""Shared fakes and helpers for worldbuilding prompt-path-compliance tests.

Provides ``SpyComposer``, fake repo/cache classes, ``_make_analyzer``,
and ``_phase1_output`` / ``_phase2_output`` helpers used by both Phase 1
and Phase 2 prompt-path-compliance test files.
"""

from __future__ import annotations

__all__ = [
    "FakeCache",
    "FakeKBEntry",
    "FakeKBRepo",
    "FakeRelRepo",
    "SpyComposer",
    "_make_analyzer",
    "_phase1_output",
    "_phase2_output",
]

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from pydantic_ai.models import Model

from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare_core.prompts.composer import PromptComposer


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeKBEntry:
    """Minimal KB entry fake with entity metadata."""

    def __init__(self, *, entity_type: str = "character", name: str = "Test") -> None:
        self.id = uuid4()
        self.name = name
        self.entity_type = entity_type
        self.metadata_: dict[str, object] | None = {"role": "hero"}
        self.body = "A detailed body describing this entity."
        self.tags: list[str] | None = ["protagonist"]
        self.usage_count = 0


class FakeKBRepo:
    """In-memory fake for KBRepositoryProtocol."""

    def __init__(self, entries: list[FakeKBEntry] | None = None) -> None:
        self._entries = entries or []

    async def get_by_id(self, entry_id: object) -> FakeKBEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None


class FakeRelRepo:
    """In-memory fake for RelationshipRepositoryProtocol."""

    async def get_adjacency_map(
        self, novel_id: object, entity_ids: set[object] | None = None
    ) -> dict[str, set[str]]:
        return {}

    async def list_for_entry(self, entry_id: object, direction: str | None = None) -> list[object]:
        return []


class FakeCache:
    """In-memory fake for WorldbuildingCache."""

    async def get(self, novel_id: str, types_hash: str = "") -> str | None:
        return None

    async def set(self, novel_id: str, value: str, types_hash: str = "") -> None:
        pass


class SpyComposer:
    """Composer spy that records every ``build()`` invocation.

    Raises the configured error (if any) so tests can exercise the fail-fast
    path without involving the real cascade.
    """

    def __init__(self, *, raise_error: Exception | None = None) -> None:
        self.build_calls: list[tuple[Any, Any, dict[str, Any]]] = []
        self._raise_error = raise_error

    async def build(
        self,
        intent: Any,
        context: Any,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        self.build_calls.append((intent, context, {"user_prompt": user_prompt}))
        if self._raise_error is not None:
            raise self._raise_error
        return ComposedPrompt(
            system="spy phase2 system prompt",
            user=user_prompt or "spy phase2 user prompt",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analyzer(
    entries: list[FakeKBEntry],
    *,
    composer_raise: Exception | None = None,
) -> tuple[WorldbuildingAnalyzer, SpyComposer]:
    """Build a WorldbuildingAnalyzer with fake deps and a SpyComposer."""
    from types import SimpleNamespace

    kb_repo = FakeKBRepo(entries)
    spy = SpyComposer(raise_error=composer_raise)
    registry = MagicMock(spec=ModelRegistry)
    # Task 6c: the analyzer resolves via the prepare() assembly point.
    registry.prepare = AsyncMock(
        return_value=SimpleNamespace(
            model=MagicMock(spec=Model),
            model_settings=None,
            usage_limits=None,
        )
    )
    config = MagicMock(spec=ResolvedModelConfig)
    analyzer = WorldbuildingAnalyzer(
        kb_repo=cast("KBRepository", kb_repo),
        rel_repo=cast("RelationshipRepository", FakeRelRepo()),
        cache=cast("WorldbuildingCache", FakeCache()),
        registry=registry,
        config=config,
        composer=cast("PromptComposer", spy),
    )
    return analyzer, spy


def _phase1_output() -> object:
    """Return a canned WorldbuildingPhase1Output for test mocks."""
    from narrare_core.agents.worldbuilding_types import (
        Phase1ConnectionOutput,
        Phase1GapOutput,
        WorldbuildingPhase1Output,
    )

    return WorldbuildingPhase1Output(
        gaps=[
            Phase1GapOutput(
                entity_id="a",
                entity_name="Alice",
                entity_type="character",
                gap_type="missing_field",
                field_key="backstory",
                description="Missing backstory.",
                severity="minor",
            ),
        ],
        connection_suggestions=[
            Phase1ConnectionOutput(
                source_entity_id="a",
                source_entity_name="Alice",
                target_entity_id="b",
                target_entity_name="Bob",
                suggested_rel_type="knows",
                reasoning="They are in the same story.",
                confidence=0.8,
            ),
        ],
        assessment="Needs work.",
        worldbuilding_score=0.6,
        candidate_pairs_for_consistency=[],
    )


def _phase2_output() -> object:
    """Return a canned WorldbuildingPhase2Output for test mocks."""
    from narrare_core.agents.worldbuilding_types import (
        Phase2ConsistencyOutput,
        WorldbuildingPhase2Output,
    )

    return WorldbuildingPhase2Output(
        issues=[
            Phase2ConsistencyOutput(
                category="timeline",
                entity_ids=["a", "b"],
                entity_names=["A", "B"],
                description="Date mismatch.",
                contradiction="Born before parent.",
                severity="moderate",
                confidence=0.7,
            ),
        ],
        assessment="Mostly consistent.",
    )
