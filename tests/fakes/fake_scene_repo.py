"""Fake scene plan repository for unit tests (PLAN-001 — RULE-23)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.models import Chapter
    from narrare.planning.models import ScenePlan


class FakeScenePlanRepository:
    """In-memory fake for ScenePlanRepositoryProtocol.

    Mirrors the real ``ScenePlanRepository`` contract without a database:
    ``bulk_replace`` deletes rows absent from the payload (by id), replaces
    stored rows for present ids, and renumbers ``position`` 1..N in payload
    order. An incoming id belonging to a DIFFERENT chapter is treated as an
    insert by the real repo → PK collision at flush → ``IntegrityError``;
    the fake mirrors that outcome by raising ``IntegrityError`` up front
    (deterministic, like the real collision — hence no fault toggle) and
    leaving its state untouched, mirroring the rolled-back flush. T4's
    foreign-scene-id error translation must test against this raising path.
    ``list_by_chapter`` orders by position; ``list_by_novel`` scopes
    through seeded chapters (INNER JOIN mirror — scenes whose chapter was
    never seeded are not returned) and orders by chapter, then scene
    position. Seed chapters via :meth:`seed_chapters` so novel scoping has
    data to join against. Timestamps are caller-provided (no DB defaults).
    """

    def __init__(self) -> None:
        self._scenes: dict[uuid.UUID, ScenePlan] = {}
        self._chapters: dict[uuid.UUID, Chapter] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *scenes: ScenePlan) -> None:
        """Pre-populate with scene plans. Keyed by scene id."""
        for scene in scenes:
            self._scenes[scene.id] = scene

    def seed_chapters(self, *chapters: Chapter) -> None:
        """Pre-populate the chapter join table used by ``list_by_novel``."""
        for chapter in chapters:
            self._chapters[chapter.id] = chapter

    async def list_by_chapter(self, chapter_id: uuid.UUID) -> list[ScenePlan]:
        self.calls.append(CallRecord("list_by_chapter", kwargs={"chapter_id": chapter_id}))
        return sorted(
            (scene for scene in self._scenes.values() if scene.chapter_id == chapter_id),
            key=lambda scene: scene.position,
        )

    async def list_by_novel(self, novel_id: uuid.UUID) -> list[ScenePlan]:
        self.calls.append(CallRecord("list_by_novel", kwargs={"novel_id": novel_id}))
        novel_chapters = {
            chapter.id: chapter
            for chapter in self._chapters.values()
            if chapter.novel_id == novel_id
        }
        joined = [
            (novel_chapters[scene.chapter_id], scene)
            for scene in self._scenes.values()
            if scene.chapter_id in novel_chapters
        ]
        joined.sort(key=lambda pair: (pair[0].position, pair[1].position))
        return [scene for _, scene in joined]

    async def get(self, scene_id: uuid.UUID) -> ScenePlan | None:
        self.calls.append(CallRecord("get", kwargs={"scene_id": scene_id}))
        return self._scenes.get(scene_id)

    async def bulk_replace(self, chapter_id: uuid.UUID, rows: list[ScenePlan]) -> list[ScenePlan]:
        self.calls.append(
            CallRecord("bulk_replace", kwargs={"chapter_id": chapter_id, "rows": rows})
        )
        # Foreign-id mirror: the real repo cannot find these ids among the
        # chapter's rows → inserts them → PK collision at flush. Raise before
        # any mutation so the failed "transaction" leaves state untouched.
        for row in rows:
            stored = self._scenes.get(row.id)
            if stored is not None and stored.chapter_id != chapter_id:
                raise IntegrityError(
                    "INSERT INTO scene_plans",
                    {},
                    Exception('duplicate key value violates unique constraint "scene_plans_pkey"'),
                )

        chapter_scene_ids = {
            scene.id for scene in self._scenes.values() if scene.chapter_id == chapter_id
        }
        incoming_ids = {row.id for row in rows}
        for scene_id in chapter_scene_ids - incoming_ids:
            del self._scenes[scene_id]

        result: list[ScenePlan] = []
        for position, incoming in enumerate(rows, start=1):
            incoming.chapter_id = chapter_id
            incoming.position = position
            self._scenes[incoming.id] = incoming
            result.append(incoming)
        return result

    def call_count(self, method: str) -> int:
        return sum(1 for call in self.calls if call.method == method)

    def assert_called_once(self, method: str) -> None:
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")
