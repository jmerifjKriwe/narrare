"""Base types and registry for structure adapters.

Defines the StructureAdapter Protocol (RULE-03: contract first),
StageDef / BeatDef dataclasses, and the StructureAdapterRegistry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class BeatDef:
    """A single beat within a stage — a plot point or narrative moment."""

    title: str
    description: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class StageDef:
    """A stage (act / phase) within a story structure."""

    id: str  # kebab-case identifier, e.g. "act-1"
    name: str  # human-readable name, e.g. "Act I: Setup"
    description: str
    position: int  # 1-based ordering
    expected_beat_count: int


@runtime_checkable
class StructureAdapter(Protocol):
    """Protocol for story-structure adapters.

    Each adapter knows how to map chapters to stages, provide beat
    expectations, and validate assignments — all pure logic, no I/O.
    """

    @property
    def structure_type(self) -> str:
        """Unique key matching StoryStructure enum values (e.g. 'three_act')."""
        ...

    @property
    def stages(self) -> list[StageDef]:
        """Ordered list of stages for this structure."""
        ...

    def suggest_stage(self, chapter_number: int, total_chapters: int) -> str:
        """Return the stage ID that best fits *chapter_number* out of *total_chapters*."""
        ...

    def validate_assignment(self, stage_id: str, chapter_number: int) -> bool:
        """Return True when *stage_id* is valid for this adapter."""
        ...

    def get_beat_expectations(self, stage_id: str) -> list[BeatDef]:
        """Return expected beats for *stage_id*; empty list if unknown."""
        ...


class StructureAdapterRegistry:
    """Central registry for structure adapters.

    Usage::

        from narrare_core.planning.adapters import registry

        adapter = registry.get("three_act")
        stage = adapter.suggest_stage(5, 20)
    """

    def __init__(self) -> None:
        self._adapters: dict[str, StructureAdapter] = {}

    def register(self, adapter: StructureAdapter) -> None:
        """Register *adapter* under its ``structure_type`` key."""
        self._adapters[adapter.structure_type] = adapter

    def get(self, structure_type: str) -> StructureAdapter:
        """Return the adapter for *structure_type*, or raise ``ValueError``."""
        try:
            return self._adapters[structure_type]
        except KeyError:
            available = ", ".join(sorted(self._adapters)) or "(none)"
            msg = f"Unknown structure type '{structure_type}'. Available: {available}"
            raise ValueError(msg) from None

    @property
    def available_types(self) -> list[str]:
        """Return sorted list of registered structure-type keys."""
        return sorted(self._adapters)

    def __contains__(self, structure_type: str) -> bool:
        return structure_type in self._adapters

    def __len__(self) -> int:
        return len(self._adapters)


__all__ = [
    "BeatDef",
    "StageDef",
    "StructureAdapter",
    "StructureAdapterRegistry",
]
