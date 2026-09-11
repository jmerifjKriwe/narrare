"""Run-target assembly from the ingest result (plan Task 15, T8 rider).

Population order — ingest fills, drivers consume: ``build_targets``
derives the per-run ``targets`` map (drivers consume it read-only via
``require_target``) and the two chapter-id maps from the build path:

- ``targets['chapter_id']`` — the FIRST ingested chapter
  (``IngestResult.chapters[0]``, corpus order);
- ``targets['entry_id']`` — the FIRST created KB entry across the
  recorded apply responses (``ChapterIngest.created_entry_ids``,
  T8 rider);
- ``series_id`` — deliberately ABSENT in v1: single-novel runs do not
  provision a series (see ``benchmark.runner`` module docstring), so the
  series-scoped check drivers skip STRUCTURALLY via ``require_target`` —
  never a fabricated id.

``chapter_ids`` (stem → run chapter id) feeds the driver context;
``chapter_map`` (run chapter id → stem) lets detection scoring resolve
chapter-pinned report items to the error registry's chapter stems.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.ingest import IngestResult

__all__ = ["RunTargets", "build_targets"]


@dataclass(frozen=True)
class RunTargets:
    """Everything the build path discovered, keyed for the drivers."""

    targets: Mapping[str, str]
    chapter_ids: Mapping[str, str]
    chapter_map: Mapping[str, str]


def build_targets(result: IngestResult) -> RunTargets:
    """Derive run targets + chapter maps from the ingest result (T8 rider)."""
    targets: dict[str, str] = {}
    if result.chapters:
        targets["chapter_id"] = result.chapters[0].chapter_id
    entry_id = next(
        (entry for chapter in result.chapters for entry in chapter.created_entry_ids), None
    )
    if entry_id is not None:
        targets["entry_id"] = entry_id
    return RunTargets(
        targets=targets,
        chapter_ids={chapter.stem: chapter.chapter_id for chapter in result.chapters},
        chapter_map={chapter.chapter_id: chapter.stem for chapter in result.chapters},
    )
