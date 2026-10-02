# Import Split/Merge Boundary Editing (F1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add split (`###`+ subheadings) and merge (contiguous, cross-file) boundary editing to the SETUP-003 import preview — riding the existing stateless two-phase API inside the `adjustments` field, with one golden-pinned mirrored-semantics frontend module.

**Architecture:** Two new pure-Core modules (`narrare_core/importing/candidates.py`, `operations.py`) own candidate discovery and op-set validation/materialization. The API changes only `schemas.py` (vocabulary v2: `splits`/`merges` in **original** index space; `excluded_indices`/`title_overrides` re-interpreted in **final** space) and `service.py` (preview enrichment + op application) — router/dependencies/repository/contracts are UNCHANGED. The frontend mirrors the semantics in exactly ONE module (`lib/importing/simulateOperations.ts`), pinned to Core outputs by a golden fixture consumed by both pytest and vitest; the panel keys edit state on stable row keys `{origIndex}#{part}`. See ADR-091 Amendment 2 + spec `docs/superpowers/specs/2026-10-02-import-split-merge-design.md`.

**Tech Stack:** Python 3.14 · Pydantic v2 (`extra="forbid"`) · pytest/vitest · React 19 · next-intl (en/de/fr). No new dependencies.

## Global Constraints

- Project language: **English** — all code, comments, tests; i18n values follow existing locale files.
- **RULE-03:** the `ImportService` Protocols in `apps/api/narrare/importing/contracts.py` are UNCHANGED and already cover v2 (ops ride the existing `ImportCommitAdjustments` type). Do NOT edit `contracts.py`. The binding cross-layer contract is the golden fixture + the RULE-17 schema/type mirror.
- **RULE-04:** hard file-size limits apply (`service.py` ≤ 300, `schemas.py` ≤ 200, any module ≤ 400). `service.py` lands ~207 lines — over the 200 soft target, under the hard limit, accepted: the additions are orchestration only (Core owns the logic); extracting ~19 translation lines would create an untestable fragment. Named extraction point if it grows further: `operations_service.py`.
- **RULE-06:** routers delegate immediately (unchanged files); services hold no SQLAlchemy; `candidates.py`/`operations.py` are pure functions.
- **RULE-07:** `narrare_core/importing/` imports nothing from `apps/`, no FastAPI, no SQLAlchemy, no I/O.
- **RULE-16:** new i18n keys go into the existing `importing` namespace — `en`/`de`/`fr` files updated in the SAME task as first use (Task 6).
- **RULE-17:** `packages/web/types/importing.ts` field names EXACTLY match the Pydantic schemas — same commit as Task 3's backend schemas (Task 5 mirrors; Task 3 does not touch TS).
- **RULE-19:** no new dependency factories (files unchanged); existing ones stay `SessionDep`-based.
- **RULE-20:** no stubs — each task ships complete, tested behavior.
- **RULE-23:** ZERO new `# type: ignore` / `@ts-ignore` anywhere. Fakes implement Protocols properly.
- Errors: raise `narrare_core.shared.errors.ValidationError` (→ 422) only; no router-level try/except; every validation error names the offending op (per-op drift detection).
- Git writes (add/commit/push) are executed by the coordinator via **NarrarePlatformSpecialist**.
- Frontend: this is Next.js 16 — read the relevant guide in `node_modules/next/dist/docs/` before writing FE code if any Next API is touched (none is expected; components only).
- Verification commands (repo root unless noted): backend unit `uv run --all-packages pytest <path> -v`; integration needs services: `just _ensure-services` first; frontend `cd packages/web && pnpm test -- <filter>` (+ `pnpm type-check`); architecture `just check-architecture`; final gate `just verify`.

## Cross-task contract table — INDEX SPACES (the #1 bug farm)

| Field / concept | Space | Produced by | Consumed by |
|---|---|---|---|
| `preview.items[].index` · `splits[].index` · `merges[].indices` | **ORIGINAL** (detected order, re-derived identically at commit) | detector + `service.preview` (T3) | `validate_operations` (T2), commit (T3), integration tests (T4), `simulateOperations` (T5), panel op controls (T6) |
| `splits[].at` ordinals | per-chapter candidate ordinals over the **capped** (≤ 200) list | `find_split_candidates` (T1) via preview enrichment (T3) | validation (T2), `SplitCandidatePicker` (T6), simulation (T5) |
| `excluded_indices` · `title_overrides` keys | **FINAL** (post-ops materialized list; ≡ original iff ops empty — identity property) | `buildAdjustments` from stable keys (T5) | `service._validate_adjustments` + selection loop (T3) |
| FE row key `{origIndex}#{part}` | **STABLE-KEY** (FE-only, never on the wire) | `simulateOperations` (T5) | panel edit state: `excludedKeys`, `titleByKey` (T6) |
| Part word-count arithmetic | `wb(next) − wb(j) − (1 + countWords(heading_j))`; part 0 = `wb(first cut)`; last part's next = `item.word_count` | `words_before` in enrichment (T1/T3) | FE simulation (T5), golden fixture |

**Invariants every implementer must hold:** (1) ops are only ever keyed on original indices; (2) FE edits are only ever keyed on stable row keys — never on final indices; (3) with empty ops, final ≡ original (the v1 suites must stay green, unchanged, as proof); (4) the server re-derives candidates and re-validates ops at commit — FE data is advisory.

## Task sizing deviations (deliberate)

- ≤ 3 *source* files / ≤ 250 *production* LOC per task (tests and i18n data excluded, mirroring the SETUP-003 plan's sizing). Deviations:
  - **T2** touches 4 files — the 4th is the golden fixture (JSON data, not code).
  - **T5** touches 5 files — 2 of them are test files; source = `types/importing.ts`, `simulateOperations.ts`, `opsState.ts`.
  - **T6** touches 6 files — 3 are the mechanical `en`/`de`/`fr` locale triples (RULE-16 forces same-task), 1 is a test file; source = `ImportPreviewPanel.tsx`, `SplitCandidatePicker.tsx`.
  - **T7** is the docs-closure task (mirrors SETUP-003 Task 11 breadth): 2 code files + tests + 3 docs files.

---

### Task 1: Core `candidates.py` — split-candidate discovery

**Files:**
- Create: `packages/core/narrare_core/importing/candidates.py`
- Modify: `packages/core/narrare_core/importing/__init__.py` (exports)
- Test: `tests/unit/core/importing/test_candidates.py`

**Interfaces:**
- Consumes: `narrare_core.importing.models.TITLE_MAX_LENGTH` (existing).
- Produces (T2/T3/T5 rely on these exact names):
  - `SPLIT_CANDIDATES_MAX: Final[int] = 200`
  - `SplitCandidate` frozen dataclass: `ordinal: int`, `heading: str` (≤ 500 chars), `start: int` (char offset of the heading line in the chapter content — Core-internal, NOT serialized), `words_before: int`
  - `find_split_candidates(content: str) -> list[SplitCandidate]` — pure, deterministic, capped

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --all-packages pytest tests/unit/core/importing/test_candidates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare_core.importing.candidates'`

- [ ] **Step 3: Write the implementation**

```python
# packages/core/narrare_core/importing/candidates.py
"""Split-candidate discovery inside detected chapters (F1 — pure, I/O-free).

A split candidate is an ATX subheading (`###`..`######`) line inside a
DETECTED chapter's stored content (ADR-091 Amendment 2 / D2a). Chapter
content never contains `#`/`##` lines (the detector splits on those), so
level 3+ is the complete candidate set. Preview serializes
ordinal/heading/words_before; commit re-derives the identical capped list
and validates op ordinals against it — the deterministic re-parse contract
is preserved (``start`` stays Core-internal).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from narrare_core.importing.models import TITLE_MAX_LENGTH

#: ATX subheading line inside a chapter body: 3-6 '#' + whitespace + text.
ATX_SUBHEADING_RE = re.compile(r"^(#{3,6})\s+(.+?)\s*$", re.MULTILINE)

#: Deterministic per-chapter cap (D3a): a pathological chapter (5 MB of
#: `### x` lines) must not blow up the preview payload or validation cost.
#: The FIRST 200 candidates in document order are offered; ordinals are
#: assigned over the capped list, so ordinal >= 200 is unreachable.
SPLIT_CANDIDATES_MAX: Final[int] = 200


@dataclass(frozen=True, slots=True)
class SplitCandidate:
    """One `###`+ subheading usable as a split point.

    ``start``: char offset of the heading line inside the chapter content.
    ``words_before``: word count of the content strictly before this
    heading line — cumulative, so the frontend computes any part's word
    count exactly by subtraction (preview items carry no content).
    """

    ordinal: int
    heading: str
    start: int
    words_before: int


def find_split_candidates(content: str) -> list[SplitCandidate]:
    """Return the chapter's split candidates (capped, document order).

    Deterministic: identical content ⇒ identical list.
    """
    candidates: list[SplitCandidate] = []
    words_seen = 0
    cursor = 0
    for ordinal, match in enumerate(ATX_SUBHEADING_RE.finditer(content)):
        if ordinal == SPLIT_CANDIDATES_MAX:
            break
        # Words between the previous heading and this one (body prefix +
        # earlier heading lines) — counted incrementally, each char once.
        words_seen += len(content[cursor : match.start()].split())
        candidates.append(
            SplitCandidate(
                ordinal=ordinal,
                heading=match.group(2)[:TITLE_MAX_LENGTH],
                start=match.start(),
                words_before=words_seen,
            )
        )
        cursor = match.start()
    return candidates
```

Update `packages/core/narrare_core/importing/__init__.py`:

```python
# packages/core/narrare_core/importing/__init__.py
"""Pure chapter-detection engine for project import (SETUP-003, ADR-091)."""

from narrare_core.importing.candidates import (
    SPLIT_CANDIDATES_MAX,
    SplitCandidate,
    find_split_candidates,
)
from narrare_core.importing.detector import detect_chapters
from narrare_core.importing.models import CHAPTER_STATUSES, TITLE_MAX_LENGTH, DetectedChapter

__all__ = [
    "CHAPTER_STATUSES",
    "DetectedChapter",
    "SPLIT_CANDIDATES_MAX",
    "TITLE_MAX_LENGTH",
    "SplitCandidate",
    "detect_chapters",
    "find_split_candidates",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --all-packages pytest tests/unit/core/importing/ -v`
Expected: PASS (new candidate tests + existing v1 splitting/detector suites)

- [ ] **Step 5: Commit**

```bash
git add packages/core/narrare_core/importing/ tests/unit/core/importing/test_candidates.py
git commit -m "feat(importing): pure Core split-candidate discovery capped at 200 (F1)"
```

---

### Task 2: Core `operations.py` — op-set validation + materialization + shared golden fixture

**Files:**
- Create: `packages/core/narrare_core/importing/operations.py`
- Modify: `packages/core/narrare_core/importing/__init__.py` (exports)
- Create: `packages/web/lib/importing/__fixtures__/operations-golden.json` (data — shared with Task 5)
- Test: `tests/unit/core/importing/test_operations.py`

**Interfaces:**
- Consumes: `find_split_candidates` (T1), `DetectedChapter` (v1), `narrare_core.shared.errors.ValidationError`.
- Produces (T3/T5 rely on these exact names):
  - `SplitOperation` frozen dataclass: `index: int`, `at: tuple[int, ...]`
  - `MergeOperation` frozen dataclass: `indices: tuple[int, ...]`
  - `ImportOperationSet` frozen dataclass: `splits: tuple[SplitOperation, ...] = ()`, `merges: tuple[MergeOperation, ...] = ()`
  - `build_operation_set(splits: Sequence[tuple[int, Sequence[int]]] = (), merges: Sequence[Sequence[int]] = ()) -> ImportOperationSet`
  - `validate_operations(chapters: Sequence[DetectedChapter], ops: ImportOperationSet) -> None` (raises `ValidationError`, per-op messages)
  - `apply_operations(chapters: Sequence[DetectedChapter], ops: ImportOperationSet) -> list[DetectedChapter]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/importing/test_operations.py
"""Operation-set semantics for import F1 (ADR-091 Amendment 2, spec §5)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

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


MD = ("The Long Chapter", "alpha beta\n### Scene A\ngamma\n### Scene B\ndelta epsilon", "draft", "long.md")
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
        chapters = [DetectedChapter(title="Whatever", content=content, word_count=4, status="draft", source_file="a.md")]
        result = apply_operations(chapters, build_operation_set(splits=[(0, [0])]))
        assert [c.title for c in result] == ["Only"]
        assert result[0].content == "body words"

    def test_split_that_would_vanish_chapter_rejected(self) -> None:
        content = "### A\n### B"
        chapters = [DetectedChapter(title="T", content=content, word_count=4, status="draft", source_file="a.md")]
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
        chapters = _chapters(prelude, ("Interlude", "i words", "draft", "b.md"),
                             ("X", "x words", "reviewed", "c.md"), ("Y", "y words", "draft", "c.md"))
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


class TestGoldenContract:
    """Double-pin: the SAME fixture is consumed by the vitest suite (Task 5).

    Any semantic change to operations.py must update this fixture in the
    same commit — and then the frontend suite enforces the mirror catches
    up (RULE-17 by value).
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --all-packages pytest tests/unit/core/importing/test_operations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'narrare_core.importing.operations'` (the golden test also fails on the missing fixture)

- [ ] **Step 3: Write the golden fixture (data — hand-computed, double-consumed)**

```json
// packages/web/lib/importing/__fixtures__/operations-golden.json
{
  "cases": [
    {
      "name": "identity-no-ops",
      "chapters": [
        { "title": "Storm", "content": "wind and rain", "word_count": 3, "status": "final", "source_file": "part1.md" },
        { "title": "Aftermath", "content": "quiet morning", "word_count": 2, "status": "draft", "source_file": "part2.md" }
      ],
      "items": [
        { "index": 0, "suggested_title": "Storm", "word_count": 3, "source_file": "part1.md", "split_candidates": [] },
        { "index": 1, "suggested_title": "Aftermath", "word_count": 2, "source_file": "part2.md", "split_candidates": [] }
      ],
      "ops": { "splits": [], "merges": [] },
      "expected": [
        { "title": "Storm", "content": "wind and rain", "word_count": 3, "status": "final", "source_file": "part1.md" },
        { "title": "Aftermath", "content": "quiet morning", "word_count": 2, "status": "draft", "source_file": "part2.md" }
      ]
    },
    {
      "name": "split-at-second-candidate",
      "chapters": [
        { "title": "The Long Chapter", "content": "alpha beta\n### Scene A\ngamma\n### Scene B\ndelta epsilon", "word_count": 11, "status": "draft", "source_file": "long.md" }
      ],
      "items": [
        {
          "index": 0,
          "suggested_title": "The Long Chapter",
          "word_count": 11,
          "source_file": "long.md",
          "split_candidates": [
            { "ordinal": 0, "heading": "Scene A", "words_before": 2 },
            { "ordinal": 1, "heading": "Scene B", "words_before": 6 }
          ]
        }
      ],
      "ops": { "splits": [{ "index": 0, "at": [1] }], "merges": [] },
      "expected": [
        { "title": "The Long Chapter", "content": "alpha beta\n### Scene A\ngamma", "word_count": 6, "status": "draft", "source_file": "long.md" },
        { "title": "Scene B", "content": "delta epsilon", "word_count": 2, "status": "draft", "source_file": "long.md" }
      ]
    },
    {
      "name": "split-skips-unselected-middle-candidate",
      "chapters": [
        { "title": "Original", "content": "one two\n### A\na1 a2\n### B\nb1\n### C\nc1 c2 c3", "word_count": 17, "status": "draft", "source_file": "mid.md" }
      ],
      "items": [
        {
          "index": 0,
          "suggested_title": "Original",
          "word_count": 17,
          "source_file": "mid.md",
          "split_candidates": [
            { "ordinal": 0, "heading": "A", "words_before": 2 },
            { "ordinal": 1, "heading": "B", "words_before": 7 },
            { "ordinal": 2, "heading": "C", "words_before": 11 }
          ]
        }
      ],
      "ops": { "splits": [{ "index": 0, "at": [0, 2] }], "merges": [] },
      "expected": [
        { "title": "Original", "content": "one two", "word_count": 2, "status": "draft", "source_file": "mid.md" },
        { "title": "A", "content": "a1 a2\n### B\nb1", "word_count": 6, "status": "draft", "source_file": "mid.md" },
        { "title": "C", "content": "c1 c2 c3", "word_count": 3, "status": "draft", "source_file": "mid.md" }
      ]
    },
    {
      "name": "merge-contiguous-cross-file",
      "chapters": [
        { "title": "Storm", "content": "wind and rain", "word_count": 3, "status": "final", "source_file": "part1.md" },
        { "title": "Aftermath", "content": "quiet morning", "word_count": 2, "status": "draft", "source_file": "part2.md" }
      ],
      "items": [
        { "index": 0, "suggested_title": "Storm", "word_count": 3, "source_file": "part1.md", "split_candidates": [] },
        { "index": 1, "suggested_title": "Aftermath", "word_count": 2, "source_file": "part2.md", "split_candidates": [] }
      ],
      "ops": { "splits": [], "merges": [{ "indices": [0, 1] }] },
      "expected": [
        { "title": "Storm", "content": "wind and rain\n\nquiet morning", "word_count": 5, "status": "final", "source_file": "part1.md" }
      ]
    },
    {
      "name": "split-and-merge-disjoint",
      "chapters": [
        { "title": "Prelude", "content": "p text\n### S1\ns body", "word_count": 6, "status": "draft", "source_file": "a.md" },
        { "title": "Interlude", "content": "i words", "word_count": 2, "status": "draft", "source_file": "b.md" },
        { "title": "X", "content": "x words", "word_count": 2, "status": "reviewed", "source_file": "c.md" },
        { "title": "Y", "content": "y words", "word_count": 2, "status": "draft", "source_file": "c.md" }
      ],
      "items": [
        {
          "index": 0, "suggested_title": "Prelude", "word_count": 6, "source_file": "a.md",
          "split_candidates": [{ "ordinal": 0, "heading": "S1", "words_before": 2 }]
        },
        { "index": 1, "suggested_title": "Interlude", "word_count": 2, "source_file": "b.md", "split_candidates": [] },
        { "index": 2, "suggested_title": "X", "word_count": 2, "source_file": "c.md", "split_candidates": [] },
        { "index": 3, "suggested_title": "Y", "word_count": 2, "source_file": "c.md", "split_candidates": [] }
      ],
      "ops": { "splits": [{ "index": 0, "at": [0] }], "merges": [{ "indices": [2, 3] }] },
      "expected": [
        { "title": "Prelude", "content": "p text", "word_count": 2, "status": "draft", "source_file": "a.md" },
        { "title": "S1", "content": "s body", "word_count": 2, "status": "draft", "source_file": "a.md" },
        { "title": "Interlude", "content": "i words", "word_count": 2, "status": "draft", "source_file": "b.md" },
        { "title": "X", "content": "x words\n\ny words", "word_count": 4, "status": "reviewed", "source_file": "c.md" }
      ]
    },
    {
      "name": "split-drops-empty-first-part",
      "chapters": [
        { "title": "Whatever", "content": "### Only\nbody words", "word_count": 4, "status": "draft", "source_file": "a.md" }
      ],
      "items": [
        {
          "index": 0, "suggested_title": "Whatever", "word_count": 4, "source_file": "a.md",
          "split_candidates": [{ "ordinal": 0, "heading": "Only", "words_before": 0 }]
        }
      ],
      "ops": { "splits": [{ "index": 0, "at": [0] }], "merges": [] },
      "expected": [
        { "title": "Only", "content": "body words", "word_count": 2, "status": "draft", "source_file": "a.md" }
      ]
    },
    {
      "name": "txt-merge-only",
      "chapters": [
        { "title": "Chapter 1", "content": "c1 words", "word_count": 2, "status": "draft", "source_file": "notes.txt" },
        { "title": "Chapter 2", "content": "c2 words", "word_count": 2, "status": "draft", "source_file": "notes.txt" }
      ],
      "items": [
        { "index": 0, "suggested_title": "Chapter 1", "word_count": 2, "source_file": "notes.txt", "split_candidates": [] },
        { "index": 1, "suggested_title": "Chapter 2", "word_count": 2, "source_file": "notes.txt", "split_candidates": [] }
      ],
      "ops": { "splits": [], "merges": [{ "indices": [0, 1] }] },
      "expected": [
        { "title": "Chapter 1", "content": "c1 words\n\nc2 words", "word_count": 4, "status": "draft", "source_file": "notes.txt" }
      ]
    }
  ]
}
```

- [ ] **Step 4: Write the implementation**

```python
# packages/core/narrare_core/importing/operations.py
"""Split/merge operation-set semantics for import F1 — pure, deterministic.

Vocabulary v2 (ADR-091 Amendment 2):

- ``splits``/``merges`` address ORIGINAL detected-chapter indices — the
  preview ``items[].index`` space, re-derived identically at commit.
- ``excluded_indices``/``title_overrides`` (applied by the API service
  AFTER :func:`apply_operations`) address FINAL indices — the materialized
  list. Identity property: an empty op set maps final space onto original
  space, so v1 payloads keep their exact meaning.

Order freedom: every op is keyed on original indices and op sets are
pairwise disjoint (split ∩ merge = ∅; merges non-overlapping), so the
declared order of ops never affects the materialized result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from narrare_core.importing.candidates import find_split_candidates
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.importing.models import DetectedChapter


@dataclass(frozen=True, slots=True)
class SplitOperation:
    """Split one original chapter at the given candidate ordinals."""

    index: int
    at: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MergeOperation:
    """Merge a contiguous ascending run of original chapters (len >= 2)."""

    indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ImportOperationSet:
    splits: tuple[SplitOperation, ...] = ()
    merges: tuple[MergeOperation, ...] = ()


def build_operation_set(
    splits: Sequence[tuple[int, Sequence[int]]] = (),
    merges: Sequence[Sequence[int]] = (),
) -> ImportOperationSet:
    """Construct from primitives (the API layer's translation seam)."""
    return ImportOperationSet(
        splits=tuple(SplitOperation(index=index, at=tuple(at)) for index, at in splits),
        merges=tuple(MergeOperation(indices=tuple(indices)) for indices in merges),
    )


def validate_operations(
    chapters: Sequence[DetectedChapter], ops: ImportOperationSet
) -> None:
    """Structural validation against the freshly (re-)parsed chapter list.

    Every rejection names the offending op (per-op drift detection): a
    stale preview surfaces as a targeted 422, never a silently wrong
    import (ADR-091 Amendment 2, spec §4.3).
    """
    chapter_count = len(chapters)
    split_indexes: set[int] = set()

    for op in ops.splits:
        _require_original_index(op.index, chapter_count, f"Split for chapter {op.index}")
        if op.index in split_indexes:
            raise ValidationError(f"Duplicate split operation for chapter {op.index}.")
        split_indexes.add(op.index)
        if not op.at:
            raise ValidationError(f"Split for chapter {op.index} selects no split points.")
        if len(set(op.at)) != len(op.at):
            raise ValidationError(f"Split for chapter {op.index} repeats a split point.")
        candidates = find_split_candidates(chapters[op.index].content)
        if min(op.at) < 0 or max(op.at) >= len(candidates):
            offender = min(op.at) if min(op.at) < 0 else max(op.at)
            raise ValidationError(
                f"Split point {offender} for chapter {op.index} is out of range "
                f"(0..{len(candidates) - 1})."
            )

    merged_indexes: set[int] = set()
    for op in ops.merges:
        if len(op.indices) < 2:
            raise ValidationError(
                f"Merge {list(op.indices)} must combine at least two chapters."
            )
        for position, index in enumerate(op.indices):
            _require_original_index(index, chapter_count, f"Merge {list(op.indices)}")
            if position and index != op.indices[position - 1] + 1:
                raise ValidationError(
                    f"Merge {list(op.indices)} is not contiguous at chapter {index}."
                )
            if index in merged_indexes:
                raise ValidationError(f"Chapter {index} appears in more than one merge.")
            if index in split_indexes:
                raise ValidationError(f"Chapter {index} cannot be both split and merged.")
            merged_indexes.add(index)


def apply_operations(
    chapters: Sequence[DetectedChapter], ops: ImportOperationSet
) -> list[DetectedChapter]:
    """Validate the op set, then materialize the final chapter list.

    Deterministic: identical chapters + identical op set ⇒ identical
    output. Application order is original chapter order (ops are folds,
    not rewrites).
    """
    validate_operations(chapters, ops)

    split_at = {op.index: tuple(sorted(op.at)) for op in ops.splits}
    merge_root: dict[int, int] = {}
    merge_members: dict[int, tuple[int, ...]] = {}
    for op in ops.merges:
        merge_members[op.indices[0]] = op.indices
        for index in op.indices:
            merge_root[index] = op.indices[0]

    result: list[DetectedChapter] = []
    for index, chapter in enumerate(chapters):
        root = merge_root.get(index)
        if root is not None:
            if index == root:
                result.append(_merge_chapters(chapters, merge_members[root]))
            continue
        cuts = split_at.get(index)
        if cuts is not None:
            result.extend(_split_chapter(index, chapter, cuts))
            continue
        result.append(chapter)
    return result


def _require_original_index(index: int, chapter_count: int, context: str) -> None:
    if not 0 <= index < chapter_count:
        raise ValidationError(
            f"{context}: index {index} is out of range (0..{chapter_count - 1})."
        )


def _split_chapter(
    index: int, chapter: DetectedChapter, cuts: Sequence[int]
) -> list[DetectedChapter]:
    """Materialize split parts (v1 heading-split semantics at level 3+).

    Part 0 keeps the chapter title and the content before the first cut;
    part j >= 1 starts at its heading line — the heading becomes the part
    title and is NOT stored in the content (v1 rule). Unselected candidate
    headings between cuts stay inside the part content. Empty parts are
    dropped (v1 rules); if NO part survives, the op would delete the
    chapter — a loud ValidationError instead.
    """
    candidates = find_split_candidates(chapter.content)
    by_ordinal = {candidate.ordinal: candidate for candidate in candidates}
    selected = [by_ordinal[ordinal] for ordinal in cuts]
    bounds = [0] + [candidate.start for candidate in selected] + [len(chapter.content)]
    titles = [chapter.title] + [candidate.heading for candidate in selected]

    parts: list[DetectedChapter] = []
    for position in range(len(selected) + 1):
        segment = chapter.content[bounds[position] : bounds[position + 1]]
        if position > 0:
            # The heading line itself is not stored in the part content.
            newline = segment.find("\n")
            segment = segment[newline + 1 :] if newline != -1 else ""
        body = segment.strip()
        if not body:
            continue
        parts.append(
            DetectedChapter(
                title=titles[position],
                content=body,
                word_count=len(body.split()),
                status=chapter.status,
                source_file=chapter.source_file,
            )
        )
    if not parts:
        raise ValidationError(
            f"Split for chapter {index} would remove it entirely (no part has content)."
        )
    return parts


def _merge_chapters(
    chapters: Sequence[DetectedChapter], indices: tuple[int, ...]
) -> DetectedChapter:
    """Materialize one merged chapter (D5a).

    Title/status/source come from the FIRST constituent (documented
    coercion — other constituents' statuses are discarded). Contents join
    with one blank line; the word count is recomputed from the joined
    content.
    """
    members = [chapters[index] for index in indices]
    first = members[0]
    content = "\n\n".join(member.content for member in members)
    return DetectedChapter(
        title=first.title,
        content=content,
        word_count=len(content.split()),
        status=first.status,
        source_file=first.source_file,
    )
```

Update `packages/core/narrare_core/importing/__init__.py` — extend the imports/`__all__`:

```python
from narrare_core.importing.operations import (
    ImportOperationSet,
    MergeOperation,
    SplitOperation,
    apply_operations,
    build_operation_set,
    validate_operations,
)
```

and add `"ImportOperationSet"`, `"MergeOperation"`, `"SplitOperation"`, `"apply_operations"`, `"build_operation_set"`, `"validate_operations"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --all-packages pytest tests/unit/core/importing/ -v`
Expected: PASS (T1 + T2 suites, including `TestGoldenContract`)

- [ ] **Step 6: Run the architecture gate**

Run: `just check-architecture`
Expected: exit 0.

- [ ] **Step 7: Commit**

```bash
git add packages/core/narrare_core/importing/ packages/web/lib/importing/__fixtures__/ tests/unit/core/importing/test_operations.py
git commit -m "feat(importing): Core op-set validation/materialization + shared golden fixture (F1)"
```

---

### Task 3: API vocabulary v2 — schemas extension + service wiring

**Files:**
- Modify: `apps/api/narrare/importing/schemas.py`
- Modify: `apps/api/narrare/importing/service.py`
- Test: `tests/unit/api/importing/test_import_operations_service.py`
- (Proof, no edit: the EXISTING v1 suites `tests/unit/api/importing/test_import_service_preview.py` + `test_import_service_commit.py` must stay green UNCHANGED — identity property.)

**Interfaces:**
- Consumes: `find_split_candidates`, `build_operation_set`, `apply_operations` (T1/T2).
- Produces (T4 FE-contract + T5 RULE-17 mirror rely on these exact JSON names):
  - `ImportSplitCandidate{ordinal: int (ge 0), heading: str (1..500), words_before: int (ge 0)}`
  - `ImportSplitOperation{index: int (ge 0), at: list[int] (min 1)}`
  - `ImportMergeOperation{indices: list[int] (min 2)}`
  - `ImportPreviewItem.split_candidates: list[ImportSplitCandidate]` (always serialized, `[]` when none)
  - `ImportCommitAdjustments{splits, merges, excluded_indices, title_overrides}` with `model_config = ConfigDict(extra="forbid")`
  - `service.commit` now: build op set → `apply_operations(detected, op_set)` → final-space exclusion/rename over `materialized`

- [ ] **Step 1: Write the failing unit tests**

```python
# tests/unit/api/importing/test_import_operations_service.py
"""Unit tests for vocabulary v2 (ops + final-space adjustments), F1."""

from __future__ import annotations

import io
import uuid

from fastapi import UploadFile
from narrare.importing.schemas import ImportCommitAdjustments
from narrare.importing.service import ImportService
from narrare_core.importing.models import DetectedChapter
from narrare_core.shared.errors import ValidationError
from starlette.datastructures import Headers


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        size=len(data),
        filename=name,
        headers=Headers({"content-type": "application/octet-stream"}),
    )


class _FakeChapterRepo:
    def __init__(self) -> None:
        self.appended: list[DetectedChapter] = []
        self.start_position = -1

    async def max_position(self, novel_id: uuid.UUID) -> int:
        return 4

    async def append_chapters(self, novel_id, chapters, start_position):
        self.appended = list(chapters)
        self.start_position = start_position
        return []


class _FakeNovelRepo:
    async def get_by_id(self, novel_id, user_id):
        return object()  # owned


def _service() -> tuple[ImportService, _FakeChapterRepo]:
    repo = _FakeChapterRepo()
    return ImportService(session=None, chapter_repo=repo, novel_repo=_FakeNovelRepo()), repo  # type: ignore[arg-type]  # reason: unit test injects protocol-conformant fakes


MD_FILES = [
    _upload("long.md", b"# The Long Chapter\nalpha beta\n### Scene A\ngamma\n### Scene B\ndelta epsilon"),
    _upload("next.md", b"# After\nquiet morning"),
]


class TestPreviewEnrichment:
    async def test_md_items_carry_capped_candidates(self) -> None:
        result = await _service()[0].preview(MD_FILES)
        first = result.items[0]
        assert first.suggested_title == "The Long Chapter"
        assert [(c.ordinal, c.heading, c.words_before) for c in first.split_candidates] == [
            (0, "Scene A", 2),
            (1, "Scene B", 6),
        ]

    async def test_txt_items_carry_empty_candidates(self) -> None:
        result = await _service()[0].preview([_upload("notes.txt", b"Chapter 1\nc1 words")])
        assert result.items[0].split_candidates == []


class TestCommitOperations:
    async def test_split_then_exclude_and_rename_in_final_space(self) -> None:
        service, repo = _service()
        # MD_FILES → originals: 0 "The Long Chapter" (2 candidates), 1 "After".
        # Split 0 at [1] → final rows: [Long part0, Scene B, After].
        adjustments = ImportCommitAdjustments(
            splits=[{"index": 0, "at": [1]}],
            merges=[],
            excluded_indices=[1],  # FINAL index 1 = the "Scene B" part
            title_overrides={"0": "Kept Intro"},
        )
        result = await service.commit(MD_FILES, uuid.uuid4(), uuid.uuid4(), adjustments)
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
            merges=[{"indices": [0, 1]}],
            excluded_indices=[],  # final: [Storm(merged), Coda]
            title_overrides={"0": "Storm & Aftermath"},
        )
        result = await service.commit(files, uuid.uuid4(), uuid.uuid4(), adjustments)
        assert result.created_count == 2
        assert [c.title for c in repo.appended] == ["Storm & Aftermath", "Coda"]
        assert repo.appended[0].content == "wind and rain\n\nquiet morning"
        assert repo.start_position == 5  # max_position 4 + 1


class TestCommitPerOpDrift:
    async def test_stale_split_ordinal_names_the_op(self) -> None:
        service, _ = _service()
        adjustments = ImportCommitAdjustments(splits=[{"index": 0, "at": [7]}])
        try:
            await service.commit(MD_FILES, uuid.uuid4(), uuid.uuid4(), adjustments)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "chapter 0" in str(exc) and "out of range" in str(exc)

    async def test_split_on_chapter_without_candidates(self) -> None:
        files = [_upload("notes.txt", b"Chapter 1\nc1 words")]
        service, _ = _service()
        adjustments = ImportCommitAdjustments(splits=[{"index": 0, "at": [0]}])
        try:
            await service.commit(files, uuid.uuid4(), uuid.uuid4(), adjustments)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "no split candidates" in str(exc)

    async def test_final_space_exclusion_range_uses_materialized_count(self) -> None:
        service, _ = _service()
        # 2 originals; split 0 at [0, 1] → 3 parts + "After" = 4 final rows
        # (indices 0..3); final index 4 is out of range.
        adjustments = ImportCommitAdjustments(
            splits=[{"index": 0, "at": [0, 1]}], excluded_indices=[4]
        )
        try:
            await service.commit(MD_FILES, uuid.uuid4(), uuid.uuid4(), adjustments)
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            assert "4" in str(exc)


class TestSchemaStrictness:
    def test_unknown_adjustment_field_rejected(self) -> None:
        try:
            ImportCommitAdjustments.model_validate(
                {"excluded_indices": [], "title_overrides": {}, "split_points": [0]}
            )
            raise AssertionError("expected ValidationError")
        except ValidationError:
            pass

    def test_v1_payload_parses_with_defaults(self) -> None:
        adjustments = ImportCommitAdjustments.model_validate(
            {"excluded_indices": [1], "title_overrides": {"0": "T"}}
        )
        assert adjustments.splits == []
        assert adjustments.merges == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --all-packages pytest tests/unit/api/importing/test_import_operations_service.py -v`
Expected: FAIL — `ImportPreviewItem` has no `split_candidates` / `ImportCommitAdjustments` has no `splits`

- [ ] **Step 3: Extend the schemas**

```python
# apps/api/narrare/importing/schemas.py — full replacement content
"""Import module Pydantic schemas (request/response) — RULE-17 mirror of
packages/web/types/importing.ts.

Vocabulary v2 (ADR-091 Amendment 2): ``splits``/``merges`` address
ORIGINAL detected indices; ``excluded_indices``/``title_overrides``
address FINAL (post-ops) indices. ``extra="forbid"`` makes unknown
fields a loud 422 instead of a silent drop (version-skew defense).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ImportSplitCandidate(BaseModel):
    """One `###`+ subheading offered as a split point (capped, ≤ 200)."""

    ordinal: int = Field(ge=0)
    heading: str = Field(min_length=1, max_length=500)
    words_before: int = Field(ge=0)


class ImportSplitOperation(BaseModel):
    """Split chapter ``index`` at the given candidate ordinals."""

    index: int = Field(ge=0)
    at: list[int] = Field(min_length=1)


class ImportMergeOperation(BaseModel):
    """Merge a contiguous ascending run of original chapters (≥ 2)."""

    indices: list[int] = Field(min_length=2)


class ImportPreviewItem(BaseModel):
    """One detected chapter in a preview (index = ORIGINAL space key)."""

    index: int = Field(ge=0)
    suggested_title: str = Field(min_length=1, max_length=500)
    word_count: int = Field(ge=0)
    source_file: str
    split_candidates: list[ImportSplitCandidate] = Field(default_factory=list[ImportSplitCandidate])


class ImportPreviewResponse(BaseModel):
    items: list[ImportPreviewItem]
    file_count: int = Field(ge=1)
    chapter_count: int = Field(ge=1)
    total_word_count: int = Field(ge=0)


class ImportCommitAdjustments(BaseModel):
    """User edits applied on top of the deterministic re-parse (v2)."""

    model_config = ConfigDict(extra="forbid")

    splits: list[ImportSplitOperation] = Field(default_factory=list[ImportSplitOperation])
    merges: list[ImportMergeOperation] = Field(default_factory=list[ImportMergeOperation])
    excluded_indices: list[int] = Field(default_factory=list[int])  # FINAL space
    title_overrides: dict[str, str] = Field(default_factory=dict)  # FINAL space


class ImportCommitChapterInfo(BaseModel):
    id: str
    title: str
    position: int
    word_count: int


class ImportCommitResponse(BaseModel):
    novel_id: str
    created_count: int = Field(ge=1)
    first_position: int = Field(ge=0)
    last_position: int = Field(ge=0)
    chapters: list[ImportCommitChapterInfo]
```

- [ ] **Step 4: Wire the service**

In `apps/api/narrare/importing/service.py`:

1. Extend imports:

```python
from narrare.importing.schemas import (
    ImportCommitAdjustments,
    ImportCommitChapterInfo,
    ImportCommitResponse,
    ImportPreviewItem,
    ImportPreviewResponse,
    ImportSplitCandidate,
)
from narrare_core.importing.candidates import find_split_candidates
from narrare_core.importing.operations import apply_operations, build_operation_set
```

(`ImportCommitAdjustments` stays where it is in the current file — it is
only used in annotations, so the `TYPE_CHECKING` placement remains correct;
the new RUNTIME imports this task needs are `find_split_candidates`,
`apply_operations`, `build_operation_set`, and `ImportSplitCandidate`.)

2. In `preview()` — enrich the items:

```python
        items = [
            ImportPreviewItem(
                index=i,
                suggested_title=c.title,
                word_count=c.word_count,
                source_file=c.source_file,
                split_candidates=[
                    ImportSplitCandidate(
                        ordinal=candidate.ordinal,
                        heading=candidate.heading,
                        words_before=candidate.words_before,
                    )
                    for candidate in find_split_candidates(c.content)
                ],
            )
            for i, c in enumerate(detected)
        ]
```

3. In `commit()` — apply ops, then final-space selection (replacing the current `selected = [...]` block):

```python
        op_set = build_operation_set(
            splits=[(op.index, op.at) for op in adjustments.splits],
            merges=[op.indices for op in adjustments.merges],
        )
        materialized = apply_operations(detected, op_set)
        self._validate_adjustments(adjustments, len(materialized))

        selected = [
            dataclasses.replace(
                chapter,
                title=adjustments.title_overrides.get(str(final_index), chapter.title),
            )
            for final_index, chapter in enumerate(materialized)
            if final_index not in adjustments.excluded_indices
        ]
```

4. Update `_validate_adjustments` docstring: `"""FINAL-space indices must reference the materialized (post-ops) list."""` and the two error messages to say `final chapter index` / `final chapter` instead of `chapter` (keep the v1 sentence shapes; e.g. `f"Excluded index {index} is out of range (0..{final_count - 1})."`).

5. Extend the commit log line: `splits=len(op_set.splits), merges=len(op_set.merges),`.

- [ ] **Step 5: Run unit tests to verify they pass — including the UNCHANGED v1 suites**

Run: `uv run --all-packages pytest tests/unit/api/importing/ -v`
Expected: PASS — new v2 tests AND the unchanged v1 `test_import_service_preview.py` / `test_import_service_commit.py` (identity property: empty ops ⇒ final ≡ original).

- [ ] **Step 6: Run the architecture gate + type check**

Run: `just check-architecture && uv run --all-packages basedpyright apps/api/narrare/importing/ 2>/dev/null || just check-architecture`
Expected: exit 0 (architecture gate at minimum; run the repo's standard type gate via `just verify` at the end).

- [ ] **Step 7: Commit**

```bash
git add apps/api/narrare/importing/schemas.py apps/api/narrare/importing/service.py tests/unit/api/importing/test_import_operations_service.py
git commit -m "feat(importing): adjustments vocabulary v2 — ops in original space, edits in final space (F1)"
```

---

### Task 4: API integration — ops through the real endpoints

**Files:**
- Test: `tests/integration/importing/test_import_operations_api.py`

**Interfaces:**
- Consumes: the deployed v2 endpoints (Task 3); fixtures `client`, `auth_headers`, `db_session`, `user_id` from the existing importing conftest patterns (`tests/integration/importing/test_import_commit_api.py`).
- Produces: nothing (verification task).

- [ ] **Step 1: Write the integration tests**

```python
# tests/integration/importing/test_import_operations_api.py
"""Integration tests for split/merge ops over HTTP (F1, ADR-091 Am. 2)."""

from __future__ import annotations

import uuid

from narrare.novels.models import Novel


async def _create_novel(db_session, user_id: uuid.UUID) -> Novel:
    novel = Novel(user_id=user_id, title="F1 Target")
    db_session.add(novel)
    await db_session.flush()
    return novel


def _files():
    return [
        ("files", ("long.md", b"# The Long Chapter\nalpha beta\n### Scene A\ngamma\n### Scene B\ndelta epsilon", "text/markdown")),
        ("files", ("next.md", b"# After\nquiet morning", "text/markdown")),
    ]


class TestPreviewEnrichment:
    async def test_preview_returns_split_candidates(self, client, auth_headers) -> None:
        response = await client.post(
            "/api/v1/import/preview", headers=auth_headers, files=_files()
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["split_candidates"] == [
            {"ordinal": 0, "heading": "Scene A", "words_before": 2},
            {"ordinal": 1, "heading": "Scene B", "words_before": 6},
        ]
        assert response.json()["items"][1]["split_candidates"] == []

    async def test_preview_txt_has_empty_candidates(self, client, auth_headers) -> None:
        response = await client.post(
            "/api/v1/import/preview",
            headers=auth_headers,
            files=[("files", ("notes.txt", b"Chapter 1\nc1 words", "text/plain"))],
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["split_candidates"] == []


class TestCommitWithOperations:
    async def test_split_merge_exclude_rename_persists_expected_rows(
        self, client, auth_headers, db_session, user_id
    ) -> None:
        novel = await _create_novel(db_session, user_id)
        adjustments = (
            '{"splits": [{"index": 0, "at": [1]}], "merges": [], '
            '"excluded_indices": [1], "title_overrides": {"0": "Kept Intro"}}'
        )
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": adjustments},
            files=_files(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["created_count"] == 2
        assert [c["title"] for c in body["chapters"]] == ["Kept Intro", "After"]

        chapters = await client.get(
            f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers
        )
        assert [c["title"] for c in chapters.json()] == ["Kept Intro", "After"]

    async def test_cross_file_merge_first_constituent_wins(
        self, client, auth_headers, db_session, user_id
    ) -> None:
        novel = await _create_novel(db_session, user_id)
        files = [
            ("files", ("a.md", b"# Storm\nwind and rain", "text/markdown")),
            ("files", ("b.md", b"# After\nquiet morning", "text/markdown")),
        ]
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"merges": [{"indices": [0, 1]}]}'},
            files=files,
        )
        assert response.status_code == 200
        assert response.json()["created_count"] == 1
        chapters = await client.get(
            f"/api/v1/novels/{novel.id}/chapters", headers=auth_headers
        )
        chapter = chapters.json()[0]
        assert chapter["title"] == "Storm"
        assert chapter["word_count"] == 5  # recomputed from joined content


class TestCommitRejections:
    async def test_stale_split_ordinal_422_names_the_op(self, client, auth_headers, db_session, user_id) -> None:
        novel = await _create_novel(db_session, user_id)
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"splits": [{"index": 0, "at": [9]}]}'},
            files=_files(),
        )
        assert response.status_code == 422
        assert "chapter 0" in response.json()["detail"]

    async def test_non_contiguous_merge_422(self, client, auth_headers, db_session, user_id) -> None:
        novel = await _create_novel(db_session, user_id)
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"merges": [{"indices": [0, 5]}]}'},
            files=_files(),
        )
        assert response.status_code == 422
        assert "not contiguous" in response.json()["detail"]

    async def test_unknown_adjustment_field_422(self, client, auth_headers, db_session, user_id) -> None:
        novel = await _create_novel(db_session, user_id)
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"split_points": [0]}'},
            files=_files(),
        )
        assert response.status_code == 422

    async def test_v1_style_adjustments_still_commit(self, client, auth_headers, db_session, user_id) -> None:
        novel = await _create_novel(db_session, user_id)
        response = await client.post(
            "/api/v1/import/commit",
            headers=auth_headers,
            data={"novel_id": str(novel.id), "adjustments": '{"excluded_indices": [1]}'},
            files=_files(),
        )
        assert response.status_code == 200
        assert response.json()["created_count"] == 1
```

- [ ] **Step 2: Run the integration suite**

Run: `just _ensure-services && uv run --all-packages pytest tests/integration/importing/ -v`
Expected: PASS (v1 integration suite unchanged + new F1 tests).

- [ ] **Step 3: Run the architecture gate**

Run: `just check-architecture`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/importing/test_import_operations_api.py
git commit -m "test(importing): F1 ops integration — enrichment, split/merge commit, per-op drift, strictness"
```

---

### Task 5: FE types v2 + `simulateOperations` (mirrored semantics) + `opsState` helpers

**Files:**
- Modify: `packages/web/types/importing.ts`
- Create: `packages/web/lib/importing/simulateOperations.ts`
- Create: `packages/web/lib/importing/opsState.ts`
- Test: `packages/web/lib/importing/simulateOperations.test.ts`
- Test: `packages/web/lib/importing/opsState.test.ts`

**Interfaces:**
- Consumes: the golden fixture `./__fixtures__/operations-golden.json` (T2); `ImportPreviewItem` etc.
- Produces (T6/T7 rely on these exact names):
  - `simulateOperations(items: ImportPreviewItem[], ops: ImportOpsState): SimulatedRow[]`
  - `SimulatedRow { key: string; finalIndex: number; origIndex: number; part: number; title: string; wordCount: number; sourceFile: string; isMerged: boolean; mergedCount: number }`
  - `buildAdjustments(selection: ImportSelection): ImportCommitAdjustments`
  - `serverSupportsOps(preview: ImportPreviewResponse): boolean`
  - `opsState`: `applySplit`, `clearSplit`, `mergeWithNext`, `unmergeAt`, `canMergeWithNext`, `EMPTY_OPS`
  - types: `ImportSplitCandidate`, `ImportSplitOperation`, `ImportMergeOperation`, `ImportOpsState`; `ImportSelection` v2 shape

- [ ] **Step 1: Extend the types (RULE-17 mirror of Task 3's schemas)**

```typescript
// packages/web/types/importing.ts — full replacement content
// Project Import types — RULE-17 mirror of apps/api/narrare/importing/schemas.py.
// ImportSelection / ImportOpsState / SimulatedRow are frontend-only (File
// objects and stable keys never cross the wire as JSON).

export interface ImportSplitCandidate {
  ordinal: number;
  heading: string;
  words_before: number;
}

export interface ImportPreviewItem {
  index: number;
  suggested_title: string;
  word_count: number;
  source_file: string;
  split_candidates: ImportSplitCandidate[];
}

export interface ImportPreviewResponse {
  items: ImportPreviewItem[];
  file_count: number;
  chapter_count: number;
  total_word_count: number;
}

export interface ImportSplitOperation {
  index: number;
  at: number[];
}

export interface ImportMergeOperation {
  indices: number[];
}

export interface ImportCommitAdjustments {
  splits: ImportSplitOperation[];
  merges: ImportMergeOperation[];
  excluded_indices: number[];
  title_overrides: Record<string, string>;
}

export interface ImportCommitChapterInfo {
  id: string;
  title: string;
  position: number;
  word_count: number;
}

export interface ImportCommitResponse {
  novel_id: string;
  created_count: number;
  first_position: number;
  last_position: number;
  chapters: ImportCommitChapterInfo[];
}

/** Operation state in ORIGINAL index space (FE-only wire-precursor). */
export interface ImportOpsState {
  splits: Record<number, number[]>;
  merges: number[][];
}

/** Current pick state of the shared import panel (frontend-only, v2). */
export interface ImportSelection {
  files: File[];
  items: ImportPreviewItem[];
  ops: ImportOpsState;
  excludedKeys: string[];
  titleByKey: Record<string, string>;
  includedCount: number;
}
```

- [ ] **Step 2: Write the failing tests (golden pinning FIRST)**

```typescript
// packages/web/lib/importing/simulateOperations.test.ts
/**
 * Golden-pinned mirror tests: simulateOperations MUST reproduce the same
 * titles/word counts/orders that the Core operations.py produces — pinned
 * by the SAME fixture consumed by tests/unit/core/importing/test_operations.py.
 */
import golden from "./__fixtures__/operations-golden.json";
import { buildAdjustments, serverSupportsOps, simulateOperations } from "./simulateOperations";
import type { ImportPreviewItem, ImportSelection } from "@/types";

type GoldenCase = {
  name: string;
  items: Array<Record<string, unknown>>;
  ops: { splits: Array<{ index: number; at: number[] }>; merges: Array<{ indices: number[] }> };
  expected: Array<{ title: string; word_count: number }>;
};

describe("simulateOperations (golden parity with Core)", () => {
  for (const raw of (golden as { cases: GoldenCase[] }).cases) {
    it(`case: ${raw.name}`, () => {
      const items = raw.items as ImportPreviewItem[];
      const ops = {
        splits: Object.fromEntries(raw.ops.splits.map((s) => [s.index, [...s.at]])),
        merges: raw.ops.merges.map((m) => [...m.indices]),
      };
      const rows = simulateOperations(items, ops);
      expect(rows.map((r) => ({ title: r.title, word_count: r.wordCount }))).toEqual(raw.expected);
      expect(rows.map((r) => r.finalIndex)).toEqual(rows.map((_, i) => i));
    });
  }
});

describe("row keys and merge flags", () => {
  const ITEMS: ImportPreviewItem[] = [
    {
      index: 0, suggested_title: "Long", word_count: 11, source_file: "long.md",
      split_candidates: [
        { ordinal: 0, heading: "Scene A", words_before: 2 },
        { ordinal: 1, heading: "Scene B", words_before: 6 },
      ],
    },
    { index: 1, suggested_title: "After", word_count: 2, source_file: "next.md", split_candidates: [] },
  ];

  it("keys split rows as {origIndex}#{part} and unsplit rows as {origIndex}#0", () => {
    const rows = simulateOperations(ITEMS, { splits: { 0: [0, 1] }, merges: [] });
    expect(rows.map((r) => r.key)).toEqual(["0#0", "0#1", "0#2", "1#0"]);
    expect(rows.map((r) => r.part)).toEqual([0, 1, 2, 0]);
  });

  it("keys merged rows by the run's first original index", () => {
    const rows = simulateOperations(ITEMS, { splits: {}, merges: [[0, 1]] });
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ key: "0#0", isMerged: true, mergedCount: 2, wordCount: 13 });
  });

  it("throws on invalid ops (mirror of Core validation)", () => {
    expect(() => simulateOperations(ITEMS, { splits: { 0: [9] }, merges: [] })).toThrow(/out of range/);
    expect(() => simulateOperations(ITEMS, { splits: {}, merges: [[0, 5]] })).toThrow(/not contiguous/);
    expect(() => simulateOperations(ITEMS, { splits: { 0: [0] }, merges: [[0, 1]] })).toThrow(/both split and merged/);
  });
});

describe("buildAdjustments", () => {
  it("maps stable keys to FINAL indices and canonicalizes ops", () => {
    const items: ImportPreviewItem[] = [
      {
        index: 0, suggested_title: "Long", word_count: 11, source_file: "long.md",
        split_candidates: [{ ordinal: 0, heading: "Scene A", words_before: 2 }],
      },
      { index: 1, suggested_title: "After", word_count: 2, source_file: "next.md", split_candidates: [] },
    ];
    const file = new File(["x"], "long.md");
    // Split 0 at [0] → final rows: ["0#0" Long-part0, "0#1" Scene A, "1#0" After]
    const selection: ImportSelection = {
      files: [file],
      items,
      ops: { splits: { 0: [0] }, merges: [] },
      excludedKeys: ["0#1"],
      titleByKey: { "0#0": "Intro" },
      includedCount: 2,
    };
    expect(buildAdjustments(selection)).toEqual({
      splits: [{ index: 0, at: [0] }],
      merges: [],
      excluded_indices: [1],
      title_overrides: { "0": "Intro" },
    });
  });

  it("keeps v1 semantics when no ops and no edits exist", () => {
    const items: ImportPreviewItem[] = [
      { index: 0, suggested_title: "A", word_count: 1, source_file: "a.md", split_candidates: [] },
    ];
    const selection: ImportSelection = {
      files: [], items, ops: { splits: {}, merges: [] }, excludedKeys: [], titleByKey: {}, includedCount: 1,
    };
    expect(buildAdjustments(selection)).toEqual({
      splits: [], merges: [], excluded_indices: [], title_overrides: {},
    });
  });
});

describe("serverSupportsOps", () => {
  it("is true when the v2 field is present (even empty)", () => {
    expect(serverSupportsOps({
      items: [{ index: 0, suggested_title: "A", word_count: 1, source_file: "a.txt", split_candidates: [] }],
      file_count: 1, chapter_count: 1, total_word_count: 1,
    })).toBe(true);
  });

  it("is false for v1-shaped items (old server)", () => {
    const legacy = { items: [{ index: 0, suggested_title: "A", word_count: 1, source_file: "a.txt" }] };
    expect(serverSupportsOps(legacy as never)).toBe(false);
  });
});
```

```typescript
// packages/web/lib/importing/opsState.test.ts
/** Op-state helper tests (FE ergonomics; the server re-validates all ops). */
import { applySplit, canMergeWithNext, clearSplit, mergeWithNext, unmergeAt } from "./opsState";
import type { ImportOpsState, ImportPreviewItem } from "@/types";

const ITEMS: ImportPreviewItem[] = [
  {
    index: 0, suggested_title: "Long", word_count: 6, source_file: "long.md",
    split_candidates: [{ ordinal: 0, heading: "S1", words_before: 2 }],
  },
  { index: 1, suggested_title: "B", word_count: 1, source_file: "b.md", split_candidates: [] },
  { index: 2, suggested_title: "C", word_count: 1, source_file: "c.md", split_candidates: [] },
];

const EMPTY: ImportOpsState = { splits: {}, merges: [] };

describe("opsState", () => {
  it("applySplit stores sorted cut ordinals; clearSplit removes them", () => {
    const split = applySplit(EMPTY, 0, [1, 0]);
    expect(split.splits[0]).toEqual([0, 1]);
    expect(clearSplit(split, 0).splits[0]).toBeUndefined();
  });

  it("mergeWithNext creates then extends a contiguous run", () => {
    const one = mergeWithNext(EMPTY, 1, ITEMS);
    expect(one.merges).toEqual([[1, 2]]);
    const two = mergeWithNext(one, 0, ITEMS);
    expect(two.merges).toEqual([[0, 1, 2]]);
  });

  it("mergeWithNext coalesces adjacent runs", () => {
    const start: ImportOpsState = { splits: {}, merges: [[0, 1]] };
    expect(mergeWithNext(start, 2, ITEMS).merges).toEqual([[0, 1, 2]]);
  });

  it("mergeWithNext refuses when the next chapter is split (split∩merge=∅)", () => {
    const split: ImportOpsState = { splits: { 1: [0] }, merges: [] };
    expect(mergeWithNext(split, 0, ITEMS)).toBe(split);
  });

  it("mergeWithNext is a no-op at the end of the list", () => {
    expect(mergeWithNext(EMPTY, 2, ITEMS)).toBe(EMPTY);
  });

  it("unmergeAt removes the run containing the index", () => {
    const ops: ImportOpsState = { splits: {}, merges: [[0, 1]] };
    expect(unmergeAt(ops, 1).merges).toEqual([]);
  });

  it("canMergeWithNext encodes the UI gating rules", () => {
    expect(canMergeWithNext(ITEMS, EMPTY, 0)).toBe(true);
    expect(canMergeWithNext(ITEMS, EMPTY, 2)).toBe(false); // no next chapter
    expect(canMergeWithNext(ITEMS, { splits: { 1: [0] }, merges: [] }, 0)).toBe(false); // next is split
    expect(canMergeWithNext(ITEMS, { splits: { 0: [0] }, merges: [] }, 0)).toBe(false); // self is split
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd packages/web && pnpm test -- simulateOperations opsState`
Expected: FAIL — modules not found. (If the JSON import errors on `resolveJsonModule`, enable it in `packages/web/tsconfig.json` — Next.js default is enabled; verify, do not assume.)

- [ ] **Step 4: Implement `simulateOperations.ts`**

```typescript
// packages/web/lib/importing/simulateOperations.ts
/**
 * THE mirrored-semantics module (ADR-091 Amendment 2 / F1 spec §6.2).
 *
 * Mirrors packages/core/narrare_core/importing/operations.py exactly —
 * validation outcomes, materialization order, title/word-count rules —
 * and is pinned to the Core outputs by the shared golden fixture
 * (operations-golden.json) consumed by BOTH pytest and vitest. The server
 * remains the authority: commit re-derives candidates and re-validates
 * every op. Displayed word counts are advisory.
 */

import type {
  ImportCommitAdjustments,
  ImportOpsState,
  ImportPreviewItem,
  ImportPreviewResponse,
  ImportSelection,
} from "@/types";

export const SPLIT_CANDIDATES_MAX = 200;
export const TITLE_MAX_LENGTH = 500;

export interface SimulatedRow {
  /** Stable FE key `${origIndex}#${part}` — never sent on the wire. */
  key: string;
  finalIndex: number;
  origIndex: number;
  part: number;
  title: string;
  wordCount: number;
  sourceFile: string;
  isMerged: boolean;
  mergedCount: number;
}

export const EMPTY_OPS: ImportOpsState = { splits: {}, merges: [] };

function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

/** The stored heading excludes the `###` marker; the heading LINE in the
 *  stored content has exactly one extra token (the marker itself). */
function headingLineWords(heading: string): number {
  return 1 + countWords(heading);
}

function splitIndexesOf(ops: ImportOpsState): Set<number> {
  return new Set(Object.keys(ops.splits).map(Number));
}

/** Mirror of Core validate_operations — throws on any invalid op. */
export function validateOps(items: ImportPreviewItem[], ops: ImportOpsState): void {
  const count = items.length;
  const splitIndexes = splitIndexesOf(ops);

  for (const [key, at] of Object.entries(ops.splits)) {
    const index = Number(key);
    if (!(0 <= index && index < count)) {
      throw new Error(`Split for chapter ${index}: index ${index} is out of range (0..${count - 1}).`);
    }
    if (at.length === 0) throw new Error(`Split for chapter ${index} selects no split points.`);
    if (new Set(at).size !== at.length) throw new Error(`Split for chapter ${index} repeats a split point.`);
    const candidates = items[index].split_candidates ?? [];
    const min = Math.min(...at);
    const max = Math.max(...at);
    if (min < 0 || max >= candidates.length) {
      const offender = min < 0 ? min : max;
      throw new Error(
        `Split point ${offender} for chapter ${index} is out of range (0..${candidates.length - 1}).`,
      );
    }
  }

  const merged = new Set<number>();
  for (const run of ops.merges) {
    if (run.length < 2) throw new Error(`Merge [${run}] must combine at least two chapters.`);
    run.forEach((index, position) => {
      if (!(0 <= index && index < count)) {
        throw new Error(`Merge [${run}]: index ${index} is out of range (0..${count - 1}).`);
      }
      if (position > 0 && index !== run[position - 1] + 1) {
        throw new Error(`Merge [${run}] is not contiguous at chapter ${index}.`);
      }
      if (merged.has(index)) throw new Error(`Chapter ${index} appears in more than one merge.`);
      if (splitIndexes.has(index)) throw new Error(`Chapter ${index} cannot be both split and merged.`);
      merged.add(index);
    });
  }
}

/** Mirror of Core apply_operations (see the golden fixture for parity). */
export function simulateOperations(items: ImportPreviewItem[], ops: ImportOpsState): SimulatedRow[] {
  validateOps(items, ops);

  const splitAt = new Map<number, number[]>();
  for (const [key, at] of Object.entries(ops.splits)) {
    splitAt.set(Number(key), [...at].sort((a, b) => a - b));
  }
  const mergeRoot = new Map<number, number>();
  const mergeMembers = new Map<number, number[]>();
  for (const run of ops.merges) {
    mergeMembers.set(run[0], run);
    for (const index of run) mergeRoot.set(index, run[0]);
  }

  const rows: SimulatedRow[] = [];
  const push = (row: Omit<SimulatedRow, "finalIndex">) => rows.push({ ...row, finalIndex: rows.length });

  items.forEach((item, index) => {
    const root = mergeRoot.get(index);
    if (root !== undefined) {
      if (index === root) {
        const members = mergeMembers.get(root)!;
        push({
          key: `${index}#0`, origIndex: index, part: 0,
          title: item.suggested_title,
          wordCount: members.reduce((sum, i) => sum + items[i].word_count, 0),
          sourceFile: item.source_file, isMerged: true, mergedCount: members.length,
        });
      }
      return;
    }
    const cuts = splitAt.get(index);
    if (cuts === undefined) {
      push({
        key: `${index}#0`, origIndex: index, part: 0, title: item.suggested_title,
        wordCount: item.word_count, sourceFile: item.source_file, isMerged: false, mergedCount: 1,
      });
      return;
    }
    const candidates = item.split_candidates ?? [];
    const selected = cuts.map((ordinal) => candidates[ordinal]);
    for (let j = 0; j <= selected.length; j++) {
      let wordCount: number;
      if (j === 0) {
        wordCount = selected.length > 0 ? selected[0].words_before : item.word_count;
      } else {
        const nextBound = j < selected.length ? selected[j].words_before : item.word_count;
        wordCount = nextBound - selected[j - 1].words_before - headingLineWords(selected[j - 1].heading);
      }
      if (wordCount <= 0) continue; // empty part dropped (Core empty-body rule)
      push({
        key: `${index}#${j}`, origIndex: index, part: j,
        title: j === 0 ? item.suggested_title : selected[j - 1].heading.slice(0, TITLE_MAX_LENGTH),
        wordCount, sourceFile: item.source_file, isMerged: false, mergedCount: 1,
      });
    }
  });
  return rows;
}

/**
 * The ONE place mapping stable-key edit state to the wire payload:
 * excluded/renames land in FINAL space; ops are canonicalized (sorted).
 */
export function buildAdjustments(selection: ImportSelection): ImportCommitAdjustments {
  const rows = simulateOperations(selection.items, selection.ops);
  const excluded = new Set(selection.excludedKeys);
  const excluded_indices: number[] = [];
  const title_overrides: Record<string, string> = {};
  for (const row of rows) {
    if (excluded.has(row.key)) excluded_indices.push(row.finalIndex);
    const title = selection.titleByKey[row.key];
    if (title !== undefined) title_overrides[String(row.finalIndex)] = title;
  }
  const splits = Object.entries(selection.ops.splits)
    .map(([key, at]) => ({ index: Number(key), at: [...at].sort((a, b) => a - b) }))
    .sort((a, b) => a.index - b.index);
  const merges = selection.ops.merges
    .map((run) => [...run].sort((a, b) => a - b))
    .sort((a, b) => a[0] - b[0]);
  return { splits, merges, excluded_indices, title_overrides };
}

/** Capability probe (spec §7): v2 servers always serialize the field. */
export function serverSupportsOps(preview: ImportPreviewResponse): boolean {
  const first = preview.items[0] as Record<string, unknown> | undefined;
  return first !== undefined && "split_candidates" in first;
}
```

- [ ] **Step 5: Implement `opsState.ts`**

```typescript
// packages/web/lib/importing/opsState.ts
/**
 * Pure FE op-state helpers (original index space). Ergonomics only — the
 * server re-validates every op at commit; these helpers simply make it
 * hard to construct an invalid set from the UI.
 */

import type { ImportOpsState, ImportPreviewItem } from "@/types";

function splitIndexesOf(ops: ImportOpsState): Set<number> {
  return new Set(Object.keys(ops.splits).map(Number));
}

function coalesce(runs: number[][]): number[][] {
  const sorted = runs.map((r) => [...r].sort((a, b) => a - b)).sort((a, b) => a[0] - b[0]);
  const out: number[][] = [];
  for (const run of sorted) {
    const last = out[out.length - 1];
    if (last && run[0] <= last[last.length - 1] + 1) last.push(...run);
    else out.push([...run]);
  }
  return out;
}

export function applySplit(ops: ImportOpsState, index: number, at: number[]): ImportOpsState {
  return { ...ops, splits: { ...ops.splits, [index]: [...at].sort((a, b) => a - b) } };
}

export function clearSplit(ops: ImportOpsState, index: number): ImportOpsState {
  const splits = { ...ops.splits };
  delete splits[index];
  return { ...ops, splits };
}

export function mergeWithNext(ops: ImportOpsState, index: number, items: ImportPreviewItem[]): ImportOpsState {
  const splitIndexes = splitIndexesOf(ops);
  if (splitIndexes.has(index)) return ops;
  const runs = ops.merges.map((r) => [...r]);
  let run = runs.find((r) => r.includes(index));
  if (!run) {
    run = [index];
    runs.push(run);
  }
  const next = run[run.length - 1] + 1;
  if (next > items.length - 1 || splitIndexes.has(next)) return ops;
  const other = runs.find((r) => r !== run && r.includes(next));
  if (other) {
    run.push(...other);
    runs.splice(runs.indexOf(other), 1);
  } else {
    run.push(next);
  }
  return { ...ops, merges: coalesce(runs) };
}

export function unmergeAt(ops: ImportOpsState, index: number): ImportOpsState {
  return { ...ops, merges: ops.merges.filter((run) => !run.includes(index)) };
}

export function canMergeWithNext(items: ImportPreviewItem[], ops: ImportOpsState, index: number): boolean {
  if (splitIndexesOf(ops).has(index)) return false;
  const next = index + 1;
  if (next > items.length - 1) return false;
  return !splitIndexesOf(ops).has(next);
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd packages/web && pnpm test -- simulateOperations opsState && pnpm type-check`
Expected: PASS / 0 errors. The golden cases passing on BOTH suites is the F1 parity gate.

- [ ] **Step 7: Commit**

```bash
git add packages/web/types/importing.ts packages/web/lib/importing/simulateOperations.ts packages/web/lib/importing/opsState.ts packages/web/lib/importing/simulateOperations.test.ts packages/web/lib/importing/opsState.test.ts
git commit -m "feat(web): mirrored simulateOperations + op-state helpers, golden-pinned against Core (F1)"
```

---

### Task 6: Panel ops UI + `SplitCandidatePicker` + i18n keys

**Files:**
- Modify: `packages/web/components/studio/importing/ImportPreviewPanel.tsx`
- Create: `packages/web/components/studio/importing/SplitCandidatePicker.tsx`
- Modify: `packages/i18n/messages/en/importing.json`, `de/importing.json`, `fr/importing.json`
- Test: `packages/web/components/studio/importing/ImportPreviewPanel.test.tsx`

**Interfaces:**
- Consumes: `simulateOperations`, `buildAdjustments` types, `opsState` helpers, `serverSupportsOps` (T5); `useTranslations("importing")`.
- Produces (T7 relies on): the panel publishes `ImportSelection` v2 (`{files, items, ops, excludedKeys, titleByKey, includedCount}`); op controls per §6.3 of the spec.

- [ ] **Step 1: Add the i18n keys (RULE-16 — same task as first use, all three locales)**

Merge into the existing top-level object of each `importing.json`:

```json
// packages/i18n/messages/en/importing.json  (addition)
"ops": {
  "split": "Split…",
  "undoSplit": "Undo split",
  "splitPoints": "Split points",
  "splitHint": "Create new chapters at the selected subheadings.",
  "applySplit": "Split chapter",
  "cancel": "Cancel",
  "noSplitPoints": "This chapter has no subheadings to split at.",
  "mergeWithNext": "Merge with next",
  "undoMerge": "Undo merge",
  "mergedBadge": "Merged {count, plural, one {# chapter} other {# chapters}}",
  "partBadge": "Part {part}"
}
```

```json
// packages/i18n/messages/de/importing.json  (addition)
"ops": {
  "split": "Teilen…",
  "undoSplit": "Teilung aufheben",
  "splitPoints": "Trennstellen",
  "splitHint": "Erstellt neue Kapitel an den gewählten Zwischenüberschriften.",
  "applySplit": "Kapitel teilen",
  "cancel": "Abbrechen",
  "noSplitPoints": "Dieses Kapitel hat keine Zwischenüberschriften zum Teilen.",
  "mergeWithNext": "Mit folgendem zusammenführen",
  "undoMerge": "Zusammenführung aufheben",
  "mergedBadge": "{count, plural, one {# Kapitel} other {# Kapitel}} zusammengeführt",
  "partBadge": "Teil {part}"
}
```

```json
// packages/i18n/messages/fr/importing.json  (addition)
"ops": {
  "split": "Diviser…",
  "undoSplit": "Annuler la division",
  "splitPoints": "Points de découpe",
  "splitHint": "Crée de nouveaux chapitres aux sous-titres sélectionnés.",
  "applySplit": "Diviser le chapitre",
  "cancel": "Annuler",
  "noSplitPoints": "Ce chapitre n'a aucun sous-titre où diviser.",
  "mergeWithNext": "Fusionner avec le suivant",
  "undoMerge": "Annuler la fusion",
  "mergedBadge": "{count, plural, one {# chapitre} other {# chapitres}} fusionnés",
  "partBadge": "Partie {part}"
}
```

- [ ] **Step 2: Write the failing component tests (extend `ImportPreviewPanel.test.tsx`)**

```tsx
// packages/web/components/studio/importing/ImportPreviewPanel.test.tsx
// — v1 cases stay, with their published-selection assertions updated to the
// v2 shape; new cases below. Full updated expectations:
/**
 * Tests for the shared import preview panel (F1: split/merge ops).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImportPreviewPanel } from "./ImportPreviewPanel";

vi.mock("@/lib/api/client", () => ({
  importApi: { preview: vi.fn(), commit: vi.fn() },
}));

import { importApi } from "@/lib/api/client";

function renderPanel(onSelectionChange: (s: unknown) => void = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ImportPreviewPanel onSelectionChange={onSelectionChange} />
    </QueryClientProvider>,
  );
}

const MD_PREVIEW = {
  items: [
    {
      index: 0, suggested_title: "Long", word_count: 11, source_file: "long.md",
      split_candidates: [
        { ordinal: 0, heading: "Scene A", words_before: 2 },
        { ordinal: 1, heading: "Scene B", words_before: 6 },
      ],
    },
    { index: 1, suggested_title: "After", word_count: 2, source_file: "next.md", split_candidates: [] },
  ],
  file_count: 1, chapter_count: 2, total_word_count: 13,
};

const V1_PREVIEW = {
  // old-server shape: no split_candidates field anywhere
  items: [
    { index: 0, suggested_title: "A", word_count: 1, source_file: "a.md" },
  ],
  file_count: 1, chapter_count: 1, total_word_count: 1,
};

async function pickFiles(preview: unknown, onSelectionChange: (s: unknown) => void = vi.fn()) {
  vi.mocked(importApi.preview).mockResolvedValueOnce(preview as never);
  renderPanel(onSelectionChange);
  const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["x"], "long.md")] } });
  await waitFor(() => expect(screen.getByDisplayValue("Long")).toBeInTheDocument());
  return onSelectionChange;
}

describe("ImportPreviewPanel (F1 ops)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("publishes the v2 selection shape after preview", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        ops: { splits: {}, merges: [] },
        excludedKeys: [],
        titleByKey: {},
        includedCount: 2,
      }),
    );
  });

  it("applies a split via the picker and re-materializes rows", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getByRole("button", { name: /split/i }));

    const picker = await screen.findByTestId("split-candidate-picker");
    expect(picker).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Scene A"));
    fireEvent.click(screen.getByTestId("apply-split-btn"));

    await waitFor(() => expect(screen.getByDisplayValue("Scene A")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Long")).toBeInTheDocument(); // part 0
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ ops: { splits: { 0: [0] }, merges: [] }, includedCount: 3 }),
    );
  });

  it("merges two chapters and merges the row identity into the first", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getAllByRole("button", { name: /merge with next/i })[0]);
    await waitFor(() => expect(screen.getByText(/merged 2 chapters/i)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ ops: { splits: {}, merges: [[0, 1]] }, includedCount: 1 }),
    );
  });

  it("renames survive a subsequent merge (stable-key edits)", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    fireEvent.change(screen.getByDisplayValue("Long"), { target: { value: "Renamed" } });
    fireEvent.click(screen.getAllByRole("button", { name: /merge with next/i })[0]);
    await waitFor(() => expect(screen.getByText(/merged 2 chapters/i)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ titleByKey: { "0#0": "Renamed" } }),
    );
  });

  it("undo merge restores two rows", async () => {
    await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getAllByRole("button", { name: /merge with next/i })[0]);
    fireEvent.click(await screen.findByRole("button", { name: /undo merge/i }));
    await waitFor(() => expect(screen.getByDisplayValue("After")).toBeInTheDocument());
  });

  it("excluding a row updates includedCount", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getAllByRole("checkbox")[1]);
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ excludedKeys: ["1#0"], includedCount: 1 }),
    );
  });

  it("hides all op controls when the server lacks the v2 field (probe)", async () => {
    await pickFiles(V1_PREVIEW);
    expect(screen.queryByRole("button", { name: /split/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /merge with next/i })).not.toBeInTheDocument();
  });

  it("preview failure surfaces the error and publishes null (v1 regression)", async () => {
    vi.mocked(importApi.preview).mockRejectedValueOnce(new Error("bad UTF-8"));
    const onSelectionChange = vi.fn();
    renderPanel(onSelectionChange);
    fireEvent.change(screen.getByLabelText(/choose files/i) as HTMLInputElement, {
      target: { files: [new File(["x"], "a.md")] },
    });
    await waitFor(() => expect(screen.getByText(/bad UTF-8/)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(null);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd packages/web && pnpm test -- ImportPreviewPanel`
Expected: FAIL — no split controls / `SplitCandidatePicker` not found

- [ ] **Step 4: Implement `SplitCandidatePicker.tsx`**

```tsx
// packages/web/components/studio/importing/SplitCandidatePicker.tsx
"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ImportSplitCandidate } from "@/types";

/**
 * Inline candidate checklist for the split affordance (no dialog
 * dependency): user selects which `###`+ subheadings become new chapter
 * boundaries, then applies. Ordinals are the chapter's capped candidate
 * ordinals (original-space op input).
 */
interface SplitCandidatePickerProps {
  readonly candidates: readonly ImportSplitCandidate[];
  readonly onApply: (ordinals: number[]) => void;
  readonly onCancel: () => void;
}

export function SplitCandidatePicker({ candidates, onApply, onCancel }: SplitCandidatePickerProps) {
  const t = useTranslations("importing.ops");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggle = (ordinal: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ordinal)) next.delete(ordinal);
      else next.add(ordinal);
      return next;
    });
  };

  if (candidates.length === 0) {
    return <p className="mt-2 text-xs text-muted-foreground">{t("noSplitPoints")}</p>;
  }

  return (
    <div className="mt-2 rounded-md border border-border bg-background p-3" data-testid="split-candidate-picker">
      <p className="text-xs font-medium text-foreground">{t("splitPoints")}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{t("splitHint")}</p>
      <ul className="mt-2 max-h-40 overflow-y-auto">
        {candidates.map((candidate) => (
          <li key={candidate.ordinal} className="flex items-center gap-2 py-0.5">
            <input
              type="checkbox"
              id={`split-cand-${candidate.ordinal}`}
              checked={selected.has(candidate.ordinal)}
              onChange={() => toggle(candidate.ordinal)}
              className="h-4 w-4"
            />
            <label htmlFor={`split-cand-${candidate.ordinal}`} className="text-sm">
              {candidate.heading}
            </label>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md bg-secondary px-3 py-1.5 text-xs font-medium text-secondary-foreground hover:bg-accent transition-colors"
        >
          {t("cancel")}
        </button>
        <button
          type="button"
          data-testid="apply-split-btn"
          disabled={selected.size === 0}
          onClick={() => onApply([...selected].sort((a, b) => a - b))}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {t("applySplit")}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Re-implement the panel rows with ops + stable-key edits**

`ImportPreviewPanel.tsx` — replace the row-edit state and list rendering (file pick / sort / provisional-publish logic from v1 stays; `handleFiles` additionally resets `ops`, `excludedKeys`, `titleByKey`, `pickerFor`):

```tsx
"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { importApi } from "@/lib/api/client";
import { EMPTY_OPS, serverSupportsOps, simulateOperations } from "@/lib/importing/simulateOperations";
import { applySplit, canMergeWithNext, clearSplit, mergeWithNext, unmergeAt } from "@/lib/importing/opsState";
import type { ImportOpsState, ImportPreviewResponse, ImportSelection } from "@/types";
import { SplitCandidatePicker } from "./SplitCandidatePicker";

/**
 * Shared import surface (F1): pick files → server preview → split/merge
 * boundary editing (original-space ops) + include/exclude/rename on the
 * simulated FINAL list (stable row keys `{origIndex}#{part}` — edits never
 * key on final indices). Publishes the v2 selection upward; the modal /
 * wizard commit via buildAdjustments. The server re-validates everything.
 */
interface ImportPreviewPanelProps {
  readonly onSelectionChange: (selection: ImportSelection | null) => void;
}

export function ImportPreviewPanel({ onSelectionChange }: ImportPreviewPanelProps) {
  const t = useTranslations("importing");
  const tOps = useTranslations("importing.ops");
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [ops, setOps] = useState<ImportOpsState>(EMPTY_OPS);
  const [excludedKeys, setExcludedKeys] = useState<Set<string>>(new Set());
  const [titleByKey, setTitleByKey] = useState<Record<string, string>>({});
  const [pickerFor, setPickerFor] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const opsEnabled = preview !== null && serverSupportsOps(preview);
  const rows = useMemo(
    () => (preview ? simulateOperations(preview.items, ops) : []),
    [preview, ops],
  );
  // First row per original index (undo-split anchor).
  const firstKeyPerOrig = useMemo(() => {
    const map = new Map<number, string>();
    for (const row of rows) if (!map.has(row.origIndex)) map.set(row.origIndex, row.key);
    return map;
  }, [rows]);

  useEffect(() => {
    if (files.length === 0) {
      onSelectionChange(null);
      return;
    }
    if (!preview) {
      // Provisional pick-time publish (v1 parity): server re-parses at commit.
      onSelectionChange({
        files, items: [], ops: EMPTY_OPS, excludedKeys: [], titleByKey: {},
        includedCount: files.length,
      });
      return;
    }
    const included = rows.filter((row) => !excludedKeys.has(row.key)).length;
    onSelectionChange({
      files, items: preview.items, ops,
      excludedKeys: [...excludedKeys], titleByKey, includedCount: included,
    });
  }, [files, preview, ops, excludedKeys, titleByKey, rows, onSelectionChange]);

  const handleFiles = async (picked: FileList | null) => {
    if (!picked || picked.length === 0) return;
    const sorted = [...picked].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { numeric: true }),
    );
    setFiles(sorted);
    setOps(EMPTY_OPS);
    setExcludedKeys(new Set());
    setTitleByKey({});
    setPickerFor(null);
    setError(null);
    setPreview(null);
    setIsLoading(true);
    try {
      const result = await importApi.preview(sorted);
      if (!result) return;
      setPreview(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      onSelectionChange(null);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleRow = (key: string) => {
    setExcludedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const renameRow = (key: string, suggested: string, value: string) => {
    setTitleByKey((prev) => {
      const next = { ...prev };
      // Empty input reverts to the suggested title (never store empties).
      if (value.trim() === "" || value === suggested) delete next[key];
      else next[key] = value;
      return next;
    });
  };

  return (
    <div className="flex flex-col gap-3" data-testid="import-preview-panel">
      <input
        ref={inputRef}
        id="import-file-input"
        type="file"
        multiple
        accept=".md,.txt"
        aria-label={t("chooseFiles")}
        className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:text-primary-foreground"
        onChange={(e) => void handleFiles(e.target.files)}
      />

      {isLoading && <p className="text-sm text-muted-foreground animate-pulse">{t("loading")}</p>}
      {error && (
        <p className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm" role="alert">
          {t("errors.previewFailed", { message: error })}
        </p>
      )}

      {preview && (
        <>
          <p className="text-xs text-muted-foreground">
            {t("summary", {
              files: preview.file_count,
              chapters: rows.length,
              words: rows.reduce((sum, row) => sum + row.wordCount, 0).toLocaleString(),
            })}
          </p>
          <ul className="max-h-72 overflow-y-auto rounded-md border border-border">
            {rows.map((row) => {
              const currentTitle = titleByKey[row.key] ?? row.title;
              const isSplit = ops.splits[row.origIndex] !== undefined;
              const isSplitHead = isSplit && firstKeyPerOrig.get(row.origIndex) === row.key;
              const splittable =
                opsEnabled && row.part === 0 && !row.isMerged && !isSplit
                && (preview.items[row.origIndex]?.split_candidates?.length ?? 0) > 0;
              const mergeable =
                opsEnabled && canMergeWithNext(preview.items, ops, row.origIndex);
              return (
                <li
                  key={row.key}
                  className="flex flex-col border-b border-border/50 px-3 py-2 last:border-b-0"
                  data-testid={`import-row-${row.key}`}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={!excludedKeys.has(row.key)}
                      onChange={() => toggleRow(row.key)}
                      aria-label={t("column.include")}
                      className="h-4 w-4"
                    />
                    <label htmlFor={`import-chapter-title-${row.key}`} className="sr-only">
                      {currentTitle}
                    </label>
                    <input
                      id={`import-chapter-title-${row.key}`}
                      type="text"
                      value={currentTitle}
                      onChange={(e) => renameRow(row.key, row.title, e.target.value)}
                      className="min-w-0 flex-1 rounded border border-border bg-background px-2 py-1 text-sm"
                    />
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {t("column.words")}: {row.wordCount.toLocaleString()}
                    </span>
                    {row.isMerged && (
                      <span className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] text-accent-foreground">
                        {tOps("mergedBadge", { count: row.mergedCount })}
                      </span>
                    )}
                    {isSplit && !row.isMerged && (
                      <span className="shrink-0 rounded bg-accent px-1.5 py-0.5 text-[10px] text-accent-foreground">
                        {tOps("partBadge", { part: row.part + 1 })}
                      </span>
                    )}
                    <span
                      className="shrink-0 max-w-32 truncate text-xs text-muted-foreground/70"
                      title={row.sourceFile}
                    >
                      {row.sourceFile}
                    </span>
                  </div>
                  {opsEnabled && (
                    <div className="mt-1 flex flex-wrap gap-2 pl-6 text-xs">
                      {splittable && (
                        <button type="button" onClick={() => setPickerFor(row.origIndex)} className="text-primary underline-offset-2 hover:underline">
                          {tOps("split")}
                        </button>
                      )}
                      {isSplitHead && (
                        <button type="button" onClick={() => setOps((o) => clearSplit(o, row.origIndex))} className="text-primary underline-offset-2 hover:underline">
                          {tOps("undoSplit")}
                        </button>
                      )}
                      {mergeable && (
                        <button type="button" onClick={() => setOps((o) => mergeWithNext(o, row.origIndex, preview.items))} className="text-primary underline-offset-2 hover:underline">
                          {tOps("mergeWithNext")}
                        </button>
                      )}
                      {row.isMerged && (
                        <button type="button" onClick={() => setOps((o) => unmergeAt(o, row.origIndex))} className="text-primary underline-offset-2 hover:underline">
                          {tOps("undoMerge")}
                        </button>
                      )}
                    </div>
                  )}
                  {pickerFor === row.origIndex && (
                    <SplitCandidatePicker
                      candidates={preview.items[row.origIndex].split_candidates}
                      onApply={(ordinals) => {
                        setOps((o) => applySplit(o, row.origIndex, ordinals));
                        setPickerFor(null);
                      }}
                      onCancel={() => setPickerFor(null)}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Run tests to verify they pass + i18n parity**

Run: `cd packages/web && pnpm test -- ImportPreviewPanel && pnpm test -- i18n && pnpm type-check`
Expected: PASS (component + RULE-16 locale parity) / 0 type errors.

- [ ] **Step 7: Commit**

```bash
git add packages/web/components/studio/importing/ packages/i18n/messages/
git commit -m "feat(web): import panel split/merge ops with stable row keys + i18n (F1)"
```

---

### Task 7: Commit consumers (`buildAdjustments`) + docs closure + full gate

**Files:**
- Modify: `packages/web/components/studio/importing/ImportModal.tsx` (commit payload)
- Modify: `packages/web/components/studio/wizard/useWizardCompletion.ts` (commit payload)
- Test: `packages/web/components/studio/importing/ImportModal.test.tsx` (updated expectations)
- Test: `packages/web/components/studio/wizard/wizard.test.tsx` (updated expectations)
- Modify: `docs/architecture/decisions/INDEX.md` (ADR-091 row: note Amendment 2 implemented)
- Modify: `docs/_shared/CURRENT_STATE.md` (dated F1 entry)
- Modify: `docs/features/setup/SETUP-003-import.md` (F1 history row → implemented)

**Interfaces:**
- Consumes: `buildAdjustments(selection)` (T5); `ImportSelection` v2 (T6 publishes).
- Produces: both commit call sites send vocabulary-v2 payloads via the single mapping; docs closure.

- [ ] **Step 1: Update the failing tests first**

In `ImportModal.test.tsx`, the commit-call assertions change from
`{ excluded_indices: [], title_overrides: {} }` to the canonical v2 payload:

```typescript
expect(importApi.commit).toHaveBeenCalledWith(
  [expect.any(File)],
  "novel-1",
  { splits: [], merges: [], excluded_indices: [], title_overrides: {} },
);
```

In `wizard.test.tsx`, every `importApi.commit` expectation gains the same
`splits: [], merges: []` fields, and any fixture building an
`importSelection` state switches to the v2 shape:

```typescript
useWizardStore.setState({
  state: { ...useWizardStore.getState().state, starter: "import" },
  importSelection: {
    files: [file],
    items: [{ index: 0, suggested_title: "A", word_count: 1, source_file: "a.md", split_candidates: [] }],
    ops: { splits: {}, merges: [] },
    excludedKeys: [],
    titleByKey: {},
    includedCount: 1,
  },
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd packages/web && pnpm test -- ImportModal wizard`
Expected: FAIL — commit called with v1-shaped adjustments.

- [ ] **Step 3: Switch both call sites to `buildAdjustments`**

`ImportModal.tsx` — `handleCommit` body becomes:

```typescript
      await importApi.commit(selection.files, novelId, buildAdjustments(selection));
```

with `import { buildAdjustments } from "@/lib/importing/simulateOperations";` (drop the now-unused `ImportCommitAdjustments`-shaped literal).

`useWizardCompletion.ts` — the commit block becomes:

```typescript
      try {
        await importApi.commit(
          importSelection.files,
          result.novel_id,
          buildAdjustments(importSelection),
        );
      } catch {
```

with the same import added.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd packages/web && pnpm test -- ImportModal wizard && pnpm type-check`
Expected: PASS / 0 errors.

- [ ] **Step 5: Docs closure**

1. `docs/architecture/decisions/INDEX.md` — append to the ADR-091 row's title cell: `; Amendment 2 (2026-10-02): F1 split/merge adjustments vocabulary v2 — ops in original space, edits in final space, preview enrichment (cap 200), extra="forbid" — implemented`.
2. `docs/_shared/CURRENT_STATE.md` — new dated entry (follow the established format): F1 scope, ADR-091 Amendment 2 + spec + plan links, module list (`candidates.py`, `operations.py`, schemas/service wiring, `simulateOperations.ts`/`opsState.ts`, panel/picker), golden-fixture double-pin evidence, test counts.
3. `docs/features/setup/SETUP-003-import.md` — Status & History: add the implemented row (mirrors the "in progress" row added with this plan, now with commit range); update the Constraints bullet that deferred split/merge.

- [ ] **Step 6: Full verification gate**

Run: `just verify`
Expected: all checks + backend + frontend suites green; zero new `# type: ignore`/`@ts-ignore` (RULE-23 ratchet); no RULE-04 violations in touched modules.

- [ ] **Step 7: Final sweep**

Run: `grep -rn "excludedIndices\|titleOverrides" packages/web/components packages/web/lib | grep -v test`
Expected: no matches (v1 selection field names fully migrated to `excludedKeys`/`titleByKey`).

- [ ] **Step 8: Commit**

```bash
git add packages/web/components/studio/importing/ImportModal.tsx packages/web/components/studio/wizard/useWizardCompletion.ts packages/web/components/studio/importing/ImportModal.test.tsx packages/web/components/studio/wizard/wizard.test.tsx docs/
git commit -m "feat(web): commit via buildAdjustments everywhere; docs closure (F1 complete)"
```

---

## Self-Review (executed by the plan author)

1. **Spec coverage:** candidates + cap 200 (T1); op semantics + validation rules 1–7 + per-op messages + order freedom + determinism (T2, golden); preview enrichment + vocabulary v2 + extra=forbid + final-space adjustments + identity proof via unchanged v1 suites (T3); HTTP-level parity incl. drift + strictness + v1-payload compat (T4); mirrored simulation + golden pin + stable-key mapping + probe (T5); panel ops UI + picker + stable keys + i18n en/de/fr (T6); single mapping at both consumers + docs (T7). Spec §7 version-skew probe → T5 `serverSupportsOps` + T6 gating test. Gap check: §5.4 word-count arithmetic → T5 golden cases 2/3/5 pin it (part word counts incl. unselected-middle-candidate subtraction). ✔
2. **Placeholder scan:** no TBD/TODO/"add error handling"/"similar to Task N" — every step carries code or an exact command; the only conditional (tsconfig `resolveJsonModule`) names the verification and the fix. ✔
3. **Type consistency:** `SplitCandidate(ordinal, heading, start, words_before)` (T1) ↔ `ImportSplitCandidate{ordinal, heading, words_before}` (T3) ↔ TS mirror (T5) ✔; `build_operation_set`/`apply_operations` (T2) ↔ service wiring (T3) ✔; `ImportOpsState`/`SimulatedRow`/`buildAdjustments`/`serverSupportsOps`/opsState helpers (T5) ↔ panel usage (T6) ↔ consumers (T7) ✔; row key `{origIndex}#{part}` consistent across T5 (`${index}#${j}`) and T6 (`row.key`) ✔; fixture `items`/`expected` fields align with both the pytest (`chapters`/`expected`) and vitest (`items`/`expected`) readers ✔.
