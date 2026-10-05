# tests/unit/core/importing/test_candidates.py
"""Golden tests for split-candidate discovery (F1, ADR-091 Amendment 2)."""

from __future__ import annotations

from narrare_core.importing.candidates import (
    SPLIT_CANDIDATES_MAX,
    find_split_candidates,
)


class TestFindSplitCandidates:
    def test_levels_three_to_six_match_in_document_order(self) -> None:
        content = "intro\n### A\nx\n#### B\ny\n##### C\nz\n###### D\nw"
        candidates = find_split_candidates(content)
        assert [c.heading for c in candidates] == ["A", "B", "C", "D"]
        assert [c.ordinal for c in candidates] == [0, 1, 2, 3]

    def test_h1_h2_never_match(self) -> None:
        assert find_split_candidates("# A\nbody\n## B\nbody") == []

    def test_cap_is_200_first_in_document_order(self) -> None:
        content = "\n".join(f"### S{i}" for i in range(300))
        candidates = find_split_candidates(content)
        assert len(candidates) == SPLIT_CANDIDATES_MAX == 200
        assert candidates[0].heading == "S0"
        assert candidates[199].heading == "S199"

    def test_words_before_is_cumulative_and_exact(self) -> None:
        content = "alpha beta\n### Scene A\ngamma\n### Scene B\ndelta epsilon"
        candidates = find_split_candidates(content)
        # words strictly before each heading line: 2, then 2+3+1=6
        assert [c.words_before for c in candidates] == [2, 6]
        # the chapter's total word count (headings included) backs the FE formula
        assert len(content.split()) == 11

    def test_start_offsets_point_at_heading_lines(self) -> None:
        content = "intro\n### A\nbody"
        candidates = find_split_candidates(content)
        assert content[candidates[0].start :].startswith("### A")

    def test_long_heading_clamped_to_title_limit(self) -> None:
        candidates = find_split_candidates(f"### {'x' * 600}")
        assert len(candidates[0].heading) == 500

    def test_no_candidates_yields_empty_list(self) -> None:
        assert find_split_candidates("plain prose only") == []

    def test_deterministic_repeat_call(self) -> None:
        content = "a\n### H\nb"
        assert find_split_candidates(content) == find_split_candidates(content)
