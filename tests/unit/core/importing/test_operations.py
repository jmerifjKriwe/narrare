# tests/unit/core/importing/test_operations.py
"""Operation-set semantics for import F1 (ADR-091 Amendment 2, spec §5)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from narrare_core.importing.models import DetectedChapter
from narrare_core.importing.operations import (
    apply_operations,
    build_operation_set,
    validate_operations,
)
from narrare_core.shared.errors import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = REPO_ROOT / "packages/web/lib/importing/__fixtures__/operations-golden.json"


def _chapters(*specs: tuple[str, str, str, str]) -> list[DetectedChapter]:
    return [
        DetectedChapter(
            title=title,
            content=content,
            word_count=len(content.split()),
            status=status,
            source_file=source,
        )
        for title, content, status, source in specs
    ]


MD = (
    "The Long Chapter",
    "alpha beta\n### Scene A\ngamma\n### Scene B\ndelta epsilon",
    "draft",
    "long.md",
)
MD2 = ("Original", "one two\n### A\na1 a2\n### B\nb1\n### C\nc1 c2 c3", "draft", "mid.md")
PLAIN1 = ("Storm", "wind and rain", "final", "part1.md")
PLAIN2 = ("Aftermath", "quiet morning", "draft", "part2.md")


class TestValidation:
    def test_out_of_range_split_index(self) -> None:
        chapters = _chapters(MD)
        ops = build_operation_set(splits=[(5, [0])])
        try:
            validate_operations(chapters, ops)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "chapter 5" in str(exc)

    def test_split_without_candidates_rejected(self) -> None:
        chapters = _chapters(PLAIN1)
        ops = build_operation_set(splits=[(0, [0])])
        try:
            validate_operations(chapters, ops)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "no split candidates" in str(exc)

    def test_split_ordinal_out_of_capped_range(self) -> None:
        chapters = _chapters(MD)  # 2 candidates
        ops = build_operation_set(splits=[(0, [2])])
        try:
            validate_operations(chapters, ops)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "out of range" in str(exc) and "0..1" in str(exc)

    def test_negative_split_ordinal_rejected(self) -> None:
        chapters = _chapters(MD)
        ops = build_operation_set(splits=[(0, [-1])])
        try:
            validate_operations(chapters, ops)
            raise AssertionError("expected ValidationError")
        except ValidationError:
            pass

    def test_empty_and_duplicate_cut_rejected(self) -> None:
        chapters = _chapters(MD)
        for at in ([], [0, 0]):
            ops = build_operation_set(splits=[(0, at)])
            try:
                validate_operations(chapters, ops)
                raise AssertionError("expected ValidationError")
            except ValidationError:
                pass

    def test_non_contiguous_merge_rejected_with_gap(self) -> None:
        chapters = _chapters(MD, MD2, PLAIN1, PLAIN2)
        ops = build_operation_set(merges=[[0, 2]])
        try:
            validate_operations(chapters, ops)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "not contiguous" in str(exc)

    def test_overlapping_merges_rejected(self) -> None:
        chapters = _chapters(MD, MD2, PLAIN1, PLAIN2)
        ops = build_operation_set(merges=[[0, 1], [1, 2]])
        try:
            validate_operations(chapters, ops)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "more than one merge" in str(exc)

    def test_split_and_merge_same_chapter_rejected(self) -> None:
        chapters = _chapters(MD, MD2, PLAIN1, PLAIN2)
        ops = build_operation_set(splits=[(1, [0])], merges=[[1, 2]])
        try:
            validate_operations(chapters, ops)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "both split and merged" in str(exc)

    def test_single_chapter_merge_rejected(self) -> None:
        chapters = _chapters(MD, MD2)
        ops = build_operation_set(merges=[[0]])
        try:
            validate_operations(chapters, ops)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "at least two" in str(exc)


class TestMaterialization:
    def test_identity_when_no_ops(self) -> None:
        chapters = _chapters(MD, PLAIN1)
        assert apply_operations(chapters, build_operation_set()) == chapters

    def test_split_cuts_unselected_headings_stay_inside(self) -> None:
        result = apply_operations(_chapters(MD), build_operation_set(splits=[(0, [1])]))
        assert [c.title for c in result] == ["The Long Chapter", "Scene B"]
        assert result[0].content == "alpha beta\n### Scene A\ngamma"
        assert result[0].word_count == 6
        assert result[1].content == "delta epsilon"
        assert all(c.status == "draft" and c.source_file == "long.md" for c in result)

    def test_split_multiple_cuts_drop_empty_part0(self) -> None:
        content = "### Only\nbody words"
        chapters = [
            DetectedChapter(
                title="Whatever", content=content, word_count=4, status="draft", source_file="a.md"
            )
        ]
        result = apply_operations(chapters, build_operation_set(splits=[(0, [0])]))
        assert [c.title for c in result] == ["Only"]
        assert result[0].content == "body words"

    def test_split_that_would_vanish_chapter_rejected(self) -> None:
        content = "### A\n### B"
        chapters = [
            DetectedChapter(
                title="T", content=content, word_count=4, status="draft", source_file="a.md"
            )
        ]
        try:
            apply_operations(chapters, build_operation_set(splits=[(0, [0, 1])]))
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "remove it entirely" in str(exc)

    def test_merge_takes_first_constituent_identity_cross_file(self) -> None:
        result = apply_operations(_chapters(PLAIN1, PLAIN2), build_operation_set(merges=[[0, 1]]))
        assert len(result) == 1
        assert result[0].title == "Storm"
        assert result[0].status == "final"  # documented coercion: first wins
        assert result[0].source_file == "part1.md"
        assert result[0].content == "wind and rain\n\nquiet morning"
        assert result[0].word_count == 5

    def test_split_and_merge_disjoint_order_interleaved(self) -> None:
        prelude = ("Prelude", "p text\n### S1\ns body", "draft", "a.md")
        chapters = _chapters(
            prelude,
            ("Interlude", "i words", "draft", "b.md"),
            ("X", "x words", "reviewed", "c.md"),
            ("Y", "y words", "draft", "c.md"),
        )
        ops = build_operation_set(splits=[(0, [0])], merges=[[2, 3]])
        result = apply_operations(chapters, ops)
        assert [c.title for c in result] == ["Prelude", "S1", "Interlude", "X"]
        assert result[3].content == "x words\n\ny words"
        assert result[3].status == "reviewed"

    def test_order_freedom_permuted_declaration_same_output(self) -> None:
        chapters = _chapters(MD, MD2, PLAIN1, PLAIN2)
        ops_a = build_operation_set(splits=[(0, [0]), (1, [1])], merges=[[2, 3]])
        ops_b = build_operation_set(splits=[(1, [1]), (0, [0])], merges=[[3, 2]])
        assert apply_operations(chapters, ops_a) == apply_operations(chapters, ops_b)

    def test_determinism_repeat_call(self) -> None:
        chapters = _chapters(MD, PLAIN1)
        ops = build_operation_set(splits=[(0, [0])], merges=[])
        assert apply_operations(chapters, ops) == apply_operations(chapters, ops)


@pytest.mark.mutation_inert
class TestGoldenContract:
    """Double-pin: the SAME fixture is consumed by the vitest suite (Task 5).

    Any semantic change to operations.py must update this fixture in the
    same commit — and then the frontend suite enforces the mirror catches
    up (RULE-17 by value).

    ``mutation_inert``: reads the committed golden fixture via ``parents[4]``,
    which resolves to a non-existent location inside MutMut's ``mutants/``
    sandbox (issue #146). MutMut's ``-m "not mutation_inert"`` filter excludes
    it — consistent with the reference asset tests. Enforced by
    scripts/checks/check_mutation_inert_assets.py.
    """

    def test_operations_match_pinned_fixture(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            chapters = [DetectedChapter(**raw) for raw in case["chapters"]]
            ops = build_operation_set(
                splits=[(s["index"], s["at"]) for s in case["ops"]["splits"]],
                merges=[m["indices"] for m in case["ops"]["merges"]],
            )
            result = apply_operations(chapters, ops)
            assert [asdict(c) for c in result] == case["expected"], case["name"]
