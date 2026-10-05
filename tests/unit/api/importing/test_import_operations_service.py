"""Unit tests for vocabulary v2 (ops + final-space adjustments), F1.

Covers the API-side wiring of ADR-091 Amendment 2:
- preview enrichment: capped split candidates on .md items, ``[]`` for
  .txt items (D2a: .txt chapters are merge-only — even when their content
  contains ``###`` lines, the preview never offers split points);
- commit: ops applied in ORIGINAL index space, exclusions/rename in FINAL
  (post-ops) space, per-op drift errors surfaced from Core unchanged.
"""

from __future__ import annotations

import io
import uuid
from typing import TYPE_CHECKING, cast

from fastapi import UploadFile
from pydantic import ValidationError as PydanticValidationError
from starlette.datastructures import Headers

from narrare.chapters.models import Chapter
from narrare.importing.schemas import (
    ImportCommitAdjustments,
    ImportMergeOperation,
    ImportSplitOperation,
)
from narrare.importing.service import ImportService
from narrare.novels.models import Novel
from narrare_core.shared.errors import ValidationError
from tests.fakes.fake_db_session import FakeDbSession
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare_core.importing.models import DetectedChapter

NOVEL_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        size=len(data),
        filename=name,
        headers=Headers({"content-type": "application/octet-stream"}),
    )


class _FakeChapterRepo:
    """Structurally satisfies ImportChapterRepositoryProtocol — records appends."""

    def __init__(self) -> None:
        self.appended: list[DetectedChapter] = []
        self.start_position = -1

    async def max_position(self, novel_id: uuid.UUID) -> int:
        return 4  # novel already has chapters at positions 0..4

    async def append_chapters(
        self,
        novel_id: uuid.UUID,
        chapters: Sequence[DetectedChapter],
        start_position: int,
    ) -> list[Chapter]:
        self.appended = list(chapters)
        self.start_position = start_position
        # Mirror the real repository contract: the caller reports these rows
        # back in the response (created_count/positions), so return real rows.
        return [
            Chapter(
                novel_id=novel_id,
                title=chapter.title,
                content=chapter.content,
                position=start_position + offset,
                word_count=chapter.word_count,
                status=chapter.status,
            )
            for offset, chapter in enumerate(chapters)
        ]


def _service() -> tuple[ImportService, _FakeChapterRepo]:
    repo = _FakeChapterRepo()
    novel_repo = FakeNovelRepository()
    novel_repo.seed(Novel(id=NOVEL_ID, user_id=USER_ID, title="Import Target"))
    return (
        ImportService(
            session=cast("AsyncSession", FakeDbSession()),  # commit never touches the session
            chapter_repo=repo,
            novel_repo=novel_repo,
        ),
        repo,
    )


def _md_files() -> list[UploadFile]:
    # Fresh streams per call — UploadFile.read() consumes its buffer, so a
    # shared module-level constant would leak empty files between tests.
    return [
        _upload(
            "long.md",
            b"# The Long Chapter\nalpha beta\n### Scene A\ngamma\n### Scene B\ndelta epsilon",
        ),
        _upload("next.md", b"# After\nquiet morning"),
    ]


class TestPreviewEnrichment:
    async def test_md_items_carry_capped_candidates(self) -> None:
        result = await _service()[0].preview(_md_files())
        first = result.items[0]
        assert first.suggested_title == "The Long Chapter"
        assert [(c.ordinal, c.heading, c.words_before) for c in first.split_candidates] == [
            (0, "Scene A", 2),
            (1, "Scene B", 6),
        ]
        # "After" has no subheadings — the field serializes as [] (always present).
        assert result.items[1].split_candidates == []

    async def test_txt_items_carry_empty_candidates(self) -> None:
        result = await _service()[0].preview([_upload("notes.txt", b"Chapter 1\nc1 words")])
        assert result.items[0].split_candidates == []

    async def test_txt_with_subheading_lines_carries_no_candidates(self) -> None:
        # D2a (T3 rider): .txt chapters are merge-only — even when the content
        # contains `###` lines, the preview offers no split points for them.
        result = await _service()[0].preview(
            [_upload("notes.txt", b"Chapter 1\ntext here\n### Scene A\nmore text")]
        )
        assert result.items[0].split_candidates == []

    async def test_txt_extension_gate_is_case_insensitive(self) -> None:
        result = await _service()[0].preview(
            [_upload("NOTES.TXT", b"Chapter 1\ntext here\n### Scene A\nmore text")]
        )
        assert result.items[0].split_candidates == []


class TestCommitOperations:
    async def test_split_then_exclude_and_rename_in_final_space(self) -> None:
        service, repo = _service()
        # _md_files() → originals: 0 "The Long Chapter" (2 candidates), 1 "After".
        # Split 0 at [1] → final rows: [Long part0, Scene B, After].
        adjustments = ImportCommitAdjustments(
            splits=[ImportSplitOperation(index=0, at=[1])],
            merges=[],
            excluded_indices=[1],  # FINAL index 1 = the "Scene B" part
            title_overrides={"0": "Kept Intro"},
        )
        result = await service.commit(_md_files(), NOVEL_ID, USER_ID, adjustments)
        # Final list before selection: [Long Chapter part0, Scene B, After]
        # Exclude final 1 (Scene B) → [part0 (renamed), After]
        assert result.created_count == 2
        assert [c.title for c in repo.appended] == ["Kept Intro", "After"]
        assert repo.appended[0].content == "alpha beta\n### Scene A\ngamma"

    async def test_merge_and_final_space_indices(self) -> None:
        files = [
            _upload("a.md", b"# Storm\nwind and rain"),
            _upload("b.md", b"# Aftermath\nquiet morning"),
            _upload("c.md", b"# Coda\nlast words"),
        ]
        service, repo = _service()
        adjustments = ImportCommitAdjustments(
            merges=[ImportMergeOperation(indices=[0, 1])],
            excluded_indices=[],  # final: [Storm(merged), Coda]
            title_overrides={"0": "Storm & Aftermath"},
        )
        result = await service.commit(files, NOVEL_ID, USER_ID, adjustments)
        assert result.created_count == 2
        assert [c.title for c in repo.appended] == ["Storm & Aftermath", "Coda"]
        assert repo.appended[0].content == "wind and rain\n\nquiet morning"
        assert repo.start_position == 5  # max_position 4 + 1


class TestCommitPerOpDrift:
    async def test_stale_split_ordinal_names_the_op(self) -> None:
        service, _ = _service()
        adjustments = ImportCommitAdjustments(splits=[ImportSplitOperation(index=0, at=[7])])
        try:
            await service.commit(_md_files(), NOVEL_ID, USER_ID, adjustments)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "chapter 0" in str(exc) and "out of range" in str(exc)

    async def test_split_on_txt_chapter_rejected_merge_only_rule(self) -> None:
        # D2a on BOTH phases: preview offers no split candidates for .txt
        # sources, so commit must reject what preview cannot produce — even
        # when the content contains `###` lines (Core is content-pure; the
        # source-file policy lives in the service, same as preview).
        files = [_upload("notes.txt", b"Chapter 1\ntext here\n### Scene A\nmore text")]
        service, _ = _service()
        adjustments = ImportCommitAdjustments(splits=[ImportSplitOperation(index=0, at=[0])])
        try:
            await service.commit(files, NOVEL_ID, USER_ID, adjustments)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "chapter 0" in str(exc) and ".md" in str(exc)

    async def test_split_on_md_chapter_without_candidates(self) -> None:
        # Core's per-op drift path: a split on a .md chapter whose content
        # has no `###`+ subheadings has no candidate ordinals to select.
        files = [_upload("plain.md", b"# Intro\njust words, no subheadings")]
        service, _ = _service()
        adjustments = ImportCommitAdjustments(splits=[ImportSplitOperation(index=0, at=[0])])
        try:
            await service.commit(files, NOVEL_ID, USER_ID, adjustments)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "no split candidates" in str(exc)

    async def test_final_space_exclusion_range_uses_materialized_count(self) -> None:
        service, _ = _service()
        # 2 originals; split 0 at [0, 1] → 3 parts + "After" = 4 final rows
        # (indices 0..3); final index 4 is out of range.
        adjustments = ImportCommitAdjustments(
            splits=[ImportSplitOperation(index=0, at=[0, 1])], excluded_indices=[4]
        )
        try:
            await service.commit(_md_files(), NOVEL_ID, USER_ID, adjustments)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "4" in str(exc)


class TestSchemaStrictness:
    def test_unknown_adjustment_field_rejected(self) -> None:
        # extra="forbid" (ADR-091 Am.2): unknown fields are a loud 422, not a
        # silent drop (version-skew defense). Parsing raises PYDANTIC's
        # ValidationError here (dependencies.py translates it to the domain
        # error at the request boundary).
        try:
            ImportCommitAdjustments.model_validate(
                {"excluded_indices": [], "title_overrides": {}, "split_points": [0]}
            )
            raise AssertionError("expected ValidationError")
        except PydanticValidationError:
            pass

    def test_v1_payload_parses_with_defaults(self) -> None:
        adjustments = ImportCommitAdjustments.model_validate(
            {"excluded_indices": [1], "title_overrides": {"0": "T"}}
        )
        assert adjustments.splits == []
        assert adjustments.merges == []

    def test_splits_list_capped_at_200(self) -> None:
        # Schema-level hardening: op lists are DoS-bounded at the same scale
        # as SPLIT_CANDIDATES_MAX (200); 201 entries must be a loud 422 at
        # the request boundary (dependencies.py), not an unbounded parse.
        try:
            ImportCommitAdjustments.model_validate({"splits": [{"index": 0, "at": [1]}] * 201})
            raise AssertionError("expected ValidationError")
        except PydanticValidationError:
            pass

    def test_splits_at_boundary_200_parses(self) -> None:
        adjustments = ImportCommitAdjustments.model_validate(
            {"splits": [{"index": 0, "at": [1]}] * 200}
        )
        assert len(adjustments.splits) == 200

    def test_merges_list_capped_at_200(self) -> None:
        try:
            ImportCommitAdjustments.model_validate({"merges": [{"indices": [0, 1]}] * 201})
            raise AssertionError("expected ValidationError")
        except PydanticValidationError:
            pass
