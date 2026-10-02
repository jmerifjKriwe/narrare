# Import Split/Merge Boundary Editing — F1 (SETUP-003 follow-up) — Design Spec

> **Status:** Approved design record (2026-10-02) — formalizes the F1 design
> exploration; all project-owner rulings are FINAL (D1a, D2a, D3a, D4a, D5a;
> Option D rejected, Option C = documented escalation path only).
> **ADR:** `docs/architecture/decisions/ADR-091-project-import-v1.md`
> (Amendment 2 — adjustments vocabulary v2)
> **Plan:** `docs/superpowers/plans/2026-10-02-import-split-merge.md`
> **Language of record:** English (project standard)

---

## §1 Scope

**In scope (F1):**

- **Split** any detected Markdown chapter at its `###`-and-deeper ATX
  subheadings (split candidates), keeping a chosen subset of the resulting
  parts.
- **Merge** any contiguous run of detected chapters into one — cross-file
  runs included.
- Adjustments **vocabulary v2**: `splits` + `merges` operation lists riding
  inside the existing `adjustments` commit field; `excluded_indices` /
  `title_overrides` re-interpreted in final (post-ops) space.
- Preview enrichment: per-item `split_candidates[]` (cap 200/chapter).
- Frontend panel upgrade with a single mirrored-semantics simulation module
  (`simulateOperations.ts`), pinned to Core outputs by a shared golden
  fixture, and stable row keys `{origIndex}#{part}`.

**Explicitly out of scope (F1):**

- `.txt` split candidates (TXT is **merge-only** in v1 — D2a).
- Re-splitting at `#`/`##` (re-litigates v1 detection — D2b rejected).
- Splitting a merge result or merging split parts (ops only ever consume
  whole original chapters; split ∩ merge = ∅).
- Arbitrary re-ordering, moving boundaries by character offset, status
  overrides, volume assignment, undo, DOCX, directory upload (unchanged
  v1/ADR-091 exclusions).

---

## §2 Decision table (binding, from the approved exploration)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Adjustment vocabulary | **D1a**: order-free op set in **original-index space** (`splits`/`merges`) + exclusions/renames in **final space**. Identity property: empty ops ⇒ final ≡ original (v1 payloads unchanged in meaning) |
| D2 | Split candidates | **D2a**: `###`+ ATX headings inside detected `.md` chapters only; `.txt` merge-only in v1 |
| D3 | Preview enrichment | **D3a**: inline `split_candidates[]` per preview item, **cap 200/chapter** (first 200 in document order, deterministic on both phases) |
| D4 | Editing model | **D4a**: ops first (original space), then select/rename in final space; FE edit state keyed by stable row keys `{origIndex}#{part}` |
| D5 | Merge semantics | **D5a**: any contiguous run (length ≥ 2, cross-file allowed); title/status/source from the **first** constituent (documented coercion); contents joined with one blank line; word count recomputed |
| C | Server-side adjusted re-preview | **Not built** — documented fallback escalation path only (RULE-21 re-review required to build it) |
| D | Full edited-payload JSON commit | **REJECTED** — breaks ADR-091's server-owns-boundaries guarantee; recorded, do not revisit |

**Supporting rulings (architecture-owned, ratified by the PO's acceptance of
the ★ recommendations):**

- Router and dependencies are **unchanged** — ops ride inside the existing
  `adjustments` JSON form field (already parsed by `get_commit_adjustments`).
- `ImportCommitAdjustments` gains `model_config = ConfigDict(extra="forbid")`
  (unknown fields → 422; prevents silent field-dropping across future skew).
- The frontend gates the **entire** ops affordance on a capability probe:
  `"split_candidates" in preview.items[0]` (see §7 Version skew).
- Core placement: `candidates.py` + `operations.py` in
  `narrare_core/importing/` (pure, I/O-free — same RULE-07 test as the v1
  parser, ADR-081 `core/export` precedent).

---

## §3 Design — module boundary

```
packages/core/narrare_core/importing/         ← pure, deterministic, no I/O
    models.py          (unchanged) DetectedChapter, TITLE_MAX_LENGTH, …
    splitting.py       (unchanged) ATX h1/h2 + TXT marker section split
    detector.py        (unchanged) detect_chapters(filename, text)
    candidates.py      NEW  ATX ###..###### scan of a chapter's content,
                            capped at SPLIT_CANDIDATES_MAX = 200
                            → SplitCandidate(ordinal, heading, start,
                                             words_before)
    operations.py      NEW  op-set model + validation + materialization
                            → SplitOperation, MergeOperation,
                              ImportOperationSet, build_operation_set,
                              validate_operations, apply_operations
    __init__.py        (+ exports)

apps/api/narrare/importing/                   ← only two files change
    schemas.py         EXT  + ImportSplitCandidate{ordinal, heading,
                            words_before}, + ImportSplitOperation{index, at},
                            + ImportMergeOperation{indices};
                            ImportPreviewItem.split_candidates: [];
                            ImportCommitAdjustments + splits/merges +
                            extra="forbid"
    service.py         EXT  preview enrichment; commit applies ops then
                            final-space exclusion/rename
    contracts.py       UNCHANGED (ImportServiceProtocol signatures already
                       carry adjustments: ImportCommitAdjustments — v2 rides
                       the same type; RULE-03 satisfied by the v1 Protocols)
    constants.py       UNCHANGED
    repository.py      UNCHANGED
    router.py          UNCHANGED
    dependencies.py    UNCHANGED (get_commit_adjustments now validates the
                       extended schema — same code path)

packages/web/
    types/importing.ts              EXT  RULE-17 mirror of the v2 schemas;
                                        ImportSelection v2 (ops + stable-key
                                        edits + items); ImportOpsState
    lib/importing/simulateOperations.ts  NEW  THE mirrored-semantics module
    lib/importing/opsState.ts       NEW  pure FE op-state helpers (apply/
                                        clear/merge/unmerge — ergonomics only,
                                        server re-validates everything)
    lib/importing/__fixtures__/operations-golden.json
                                    NEW  shared golden fixture consumed by
                                        pytest (Core side) AND vitest (FE side)
    components/studio/importing/
        ImportPreviewPanel.tsx      EXT  ops controls + stable-key edit state
        SplitCandidatePicker.tsx    NEW  inline candidate checklist
        ImportModal.tsx             EXT  commits via buildAdjustments(selection)
        ImportFailedBanner.tsx      UNCHANGED
    components/studio/wizard/
        useWizardCompletion.ts      EXT  commits via buildAdjustments(selection)
        WizardStep2.tsx / WizardStep5.tsx   UNCHANGED (selection API stable)
    lib/stores/wizardStore.ts       UNCHANGED (holds ImportSelection; type only)

packages/i18n/messages/{en,de,fr}/importing.json   EXT  ops.* keys
                    (namespace already registered — RULE-16 needs keys in
                     all three locales in the first-use task)
```

**Dependency direction (RULE-07, one-way, unchanged):**

```
router → ImportService → ImportChapterRepository → DB
              ↓
   narrare_core.importing.{detector, candidates, operations}   (pure)
   narrare.novels.ownership.verify_novel_owned                 (gate)
```

No DB migration. No new external dependency.

---

## §4 Wire contracts

Errors keep the app-level `NarrareError` shape (`ValidationError` → 422).
Both endpoints and their signatures are byte-identical to v1; only payload
*fields* are extended (additively).

### 4.1 `POST /api/v1/import/preview` — response 200 (v2)

```json
{
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
    },
    {
      "index": 1,
      "suggested_title": "Chapter 1",
      "word_count": 3,
      "source_file": "notes.txt",
      "split_candidates": []
    }
  ],
  "file_count": 2,
  "chapter_count": 2,
  "total_word_count": 14
}
```

- `split_candidates` is always present in v2 (possibly `[]`: `.txt`
  chapters, `.md` chapters without `###`+ subheadings).
- `words_before` = word count of the content strictly **before** the
  candidate's heading line (cumulative; enables exact FE part word counts
  without shipping content).
- Cap: at most `SPLIT_CANDIDATES_MAX` (200) candidates per chapter — the
  **first 200 in document order**. Chapters with more subheadings simply
  do not offer the rest (documented limitation; deterministic on both
  phases because the cap is applied by the same pure function).

### 4.2 `POST /api/v1/import/commit` — `adjustments` (v2)

```json
{
  "splits": [{ "index": 0, "at": [1] }],
  "merges": [{ "indices": [2, 3] }],
  "excluded_indices": [1],
  "title_overrides": { "2": "Renamed Merged Chapter" }
}
```

| Field | Index space | Meaning |
|-------|-------------|---------|
| `splits[].index` | original | chapter to split (preview `items[].index`) |
| `splits[].at` | per-chapter candidate ordinals | which `###`+ headings to cut at (unordered set, ≥ 1, unique, each < capped candidate count of that chapter) |
| `merges[].indices` | original | contiguous ascending run, length ≥ 2, cross-file allowed |
| `excluded_indices` | **final** | indices of the materialized (post-ops) list to drop |
| `title_overrides` | **final** | index (string key) → new title (1..500 chars) |

All five fields are optional (v1 payloads parse unchanged); unknown fields
are **forbidden** (`extra="forbid"` → 422).

**Processing (commit):** guard pipeline (unchanged) → ownership gate
(unchanged) → deterministic re-parse → `validate_operations` against the
re-derived chapter list and re-derived candidates → `apply_operations` →
final-space structural validation of `excluded_indices` /
`title_overrides` against the materialized list → filter + rename →
`position = max+1..n` → bulk insert → single flush (atomicity unchanged).

### 4.3 Validation rules (normative — pure Core, mirrored in FE)

1. `splits[].index` and every `merges[][k]` ∈ `0..chapter_count−1`
   (original count from the fresh re-parse).
2. A chapter referenced by a split **must** have ≥ 1 split candidate
   (`.md` with `###`+ content) — else 422.
3. `splits[].at`: non-empty, no duplicates, every ordinal ∈
   `0..len(candidates_of_that_chapter)−1` (capped list).
4. Each merge: `len ≥ 2`, strictly ascending with step 1 (contiguity).
5. No original index in two merges (overlap).
6. No original index both split and merged (split ∩ merge = ∅).
7. A split may not eliminate its chapter (all parts empty → 422).
8. Final-space: `excluded_indices` ∈ `0..final_count−1`;
   `title_overrides` keys likewise; titles 1..500 chars raw (v1 rules).
9. **Per-op drift errors:** every rejection names the op, e.g.
   `"Split point 5 for chapter 0 is out of range (0..1)."` /
   `"Merge [2, 4] is not contiguous at chapter 4."` /
   `"Chapter 3 cannot be both split and merged."` — a stale preview (file
   set changed between preview and commit) surfaces as a targeted 422.

### 4.4 Determinism statement (extends the v1 contract)

`detect_chapters` (unchanged) and `find_split_candidates` (new) are pure:
identical file sets in identical order yield identical chapter lists and
identical capped candidate lists on preview and commit. Therefore the same
files + the same op set always produce the same import — vocabulary v2
preserves the deterministic re-parse contract; there is still no
server-side session state.

---

## §5 Operation semantics (normative)

### 5.1 Split materialization

For chapter `c` with cut ordinals `at` (validated):

- Selected candidates, sorted by ordinal, partition `c.content`:
  part 0 = text before the first selected heading; part j ≥ 1 = text from
  selected heading j to selected heading j+1 (or chapter end).
- **Titles:** part 0 keeps `c.title`; part j ≥ 1 takes the candidate's
  heading text (clamped to 500 — same rule as v1 titles).
- **Heading lines are not stored in part content** (v1 rule): part j ≥ 1's
  stored content starts after its heading line. Unselected candidate
  headings *between* cuts stay inside the part content (they are ordinary
  text once not chosen as boundaries).
- Parts whose stripped content is empty are dropped (v1 empty-body rule);
  part 0 empty = the v1 preamble rule. If **no** part survives → 422
  (rule 7 above).
- Each part inherits `status` and `source_file`; `word_count` is recomputed
  from the part's content.

### 5.2 Merge materialization

For a validated run `[i..k]`:

- One chapter: `title = chapters[i].title`, `status = chapters[i].status`,
  `source_file = chapters[i].source_file` — **documented coercion**: the
  other constituents' statuses/titles are discarded (a final-space
  `title_overrides` entry can still rename the result; status is not
  user-overridable in v1).
- `content = "\n\n".join(constituent contents)` (pieces are stripped, so
  no tokens glue); `word_count` recomputed from the joined content.
- Cross-file runs are legal because original indices are contiguous across
  file boundaries by construction (multipart order).

### 5.3 Materialization order

Final order = original chapter order with ops folded in: merge runs emit
one chapter at the run's first index; split chapters emit their surviving
parts in order; everything else passes through. Final indices are assigned
in that order. Op declaration order never matters (order freedom, D1a).

### 5.4 Frontend word-count arithmetic (mirror rule)

The FE must derive part word counts **exactly** from serialized data
(items carry no content). With `wb(j)` = candidate j's `words_before`,
`total` = item `word_count`, and `lineWords(j) = 1 + countWords(heading_j)`
(the stored heading excludes the `###` marker, which is one token of the
heading *line*):

```
part 0 word count = wb(first cut)
part j ≥ 1 word count = next − wb(j) − lineWords(j),
    where next = wb(cut j+1)  or  total for the last part
merged row word count = Σ constituent item word_counts
```

`countWords` (TS) = trimmed `split(/\s+/)` count, mirroring Python
`len(str.split())`. The golden fixture pins this equivalence on the test
corpus; FE-displayed counts are advisory (the server recomputes
authoritative counts at commit).

---

## §6 Frontend design

### 6.1 State model (stable keys — the anti-bug-farm core)

```ts
interface ImportOpsState {                    // ORIGINAL space
  splits: Record<number, number[]>;           // origIndex -> cut ordinals
  merges: number[][];                         // contiguous original runs
}
// Edit state lives on STABLE row keys, never on final indices:
//   excludedKeys: Set<`${origIndex}#${part}`>
//   titleByKey:   Record<`${origIndex}#${part}`, string>
```

`simulateOperations(items, ops)` returns rows
`{ key: "${origIndex}#${part}", finalIndex, origIndex, part, title,
wordCount, sourceFile, isMerged, mergedCount }`. Because edits key on
`{origIndex}#{part}`, any op change re-materializes rows **without**
invalidating edits on surviving keys; an edit whose key disappears (e.g.
rename on `5#1`, then un-split) is dropped deterministically (documented).

`ImportSelection` (published to modal/wizard store) becomes:

```ts
interface ImportSelection {
  files: File[];
  items: ImportPreviewItem[];       // authoritative preview (never re-parsed FE-side)
  ops: ImportOpsState;
  excludedKeys: string[];
  titleByKey: Record<string, string>;
  includedCount: number;            // rows.length − excluded∩rows
}
```

`buildAdjustments(selection)` (in `simulateOperations.ts`, the ONE place
that maps stable keys → wire indices) produces the §4.2 payload:
`excluded_indices` / `title_overrides` from the current simulation's
`finalIndex` values; `splits` / `merges` canonicalized (sorted) from
`ops`. Both commit call sites (`ImportModal`, `useWizardCompletion`) use
it — no inline mapping anywhere else.

### 6.2 Mirrored semantics + golden pinning

`simulateOperations.ts` is the **only** FE module that mirrors Core
semantics (validation outcomes, materialization, word arithmetic,
200-cap, 500-clamp). It is pinned by
`packages/web/lib/importing/__fixtures__/operations-golden.json` — one
fixture consumed by **both** suites:

- `tests/unit/core/importing/test_operations.py` (pytest) asserts
  `apply_operations` reproduces `expected` per case;
- `packages/web/lib/importing/simulateOperations.test.ts` (vitest) asserts
  `simulateOperations` reproduces the same `expected` rows.

Any semantic change on either side fails at least one suite; changing
semantics requires updating the fixture in the same commit — reviewed as
a contract change (RULE-17 by value).

### 6.3 Panel UI

`ImportPreviewPanel` renders the simulated final list (one row per
`SimulatedRow`): include-checkbox (`excludedKeys`), title input
(`titleByKey`; clearing an input reverts to the suggested title instead of
storing an empty string), word count, source file (first-constituent file
on merged rows), plus op controls:

- **Split…** — on rows that are part 0 of an unsplit, unmerged original
  `.md` chapter with ≥ 1 candidate. Opens `SplitCandidatePicker` (inline
  expanding region; no dialog dependency): candidate checklist with
  headings → *Apply split* → `applySplit`.
- **Undo split** — on the first row of a split chapter (`clearSplit`).
- **Merge with next** — on rows whose original index is unsplit and whose
  next original index exists and is unsplit (`canMergeWithNext`);
  merges/extends contiguous runs, coalescing adjacent runs
  (`mergeWithNext`).
- **Undo merge** — on merged rows (`unmergeAt`).
- Badges: `Merged {count} chapters` on merged rows; `Part {n}` on split
  parts.

Provisional publish at pick time (before the preview resolves) keeps v1
parity: `{files, items: [], ops: ∅, …, includedCount: files.length}` —
safe because the commit endpoint re-parses and re-validates everything.

**Capability probe:** if `"split_candidates" in preview.items[0]` is
false (old server), the panel hides **all** op controls and behaves as
v1 (see §7).

### 6.4 i18n keys (sketch — `importing` namespace, en/de/fr)

```
ops.split ("Split…") · ops.undoSplit · ops.splitPoints ("Split points")
ops.splitHint · ops.applySplit · ops.cancel · ops.noSplitPoints
ops.mergeWithNext · ops.undoMerge · ops.mergedBadge ("Merged {count} …")
ops.partBadge ("Part {part}")
```

The namespace is already registered (`request.ts`); RULE-16 requires the
keys to exist in all three locales in the same task as first use.

---

## §7 Version skew (documented; no shims — Q-012 precedent)

FE+BE ship together in one image. Residual windows:

| Skew | Behavior |
|------|----------|
| old server + new FE | preview items lack `split_candidates` → probe false → **entire** ops affordance hidden (split AND merge) → exact v1 behavior. The probe is mandatory: a v1 server *silently ignores* unknown adjustment fields (Pydantic default `extra=ignore`), and a silently dropped merge would be a silent boundary loss — the one outcome ADR-091 forbids |
| new server + old FE | v1 payload (no ops) → identity property → identical v1 behavior |
| future unknown fields | `extra="forbid"` on `ImportCommitAdjustments` → loud 422 |

---

## §8 Test strategy (from exploration §1.5)

| Layer | File | Covers |
|-------|------|--------|
| Core unit | `tests/unit/core/importing/test_candidates.py` | levels 3–6 match; h1/h2 never match; cap 200 first-in-order; `words_before` cumulative exactness; start offsets; heading clamp; empty → `[]` |
| Core unit | `tests/unit/core/importing/test_operations.py` | validation matrix (rules 1–7, per-op messages); split materialization (titles, heading-stripping, unselected headings stay inside, empty parts dropped, vanish → 422); merge materialization (first-constituent coercion, cross-file, join + recount); order freedom (permuted op declarations ⇒ same output); identity (empty ops); determinism (repeat call); **golden fixture consumption** |
| API unit | `tests/unit/api/importing/test_import_operations_service.py` | preview enrichment (md vs txt vs cap); commit op application end-to-end with fakes (split+merge+exclude+rename, positions); per-op drift 422s; **v1 suite stays green unchanged (identity proof)** |
| API integration | `tests/integration/importing/test_import_operations_api.py` | multipart commit with splits+merges through the real endpoint (DB positions/titles/contents); preview enrichment over HTTP; per-op drift 422; `extra="forbid"` 422 |
| FE unit | `packages/web/lib/importing/simulateOperations.test.ts` | **golden fixture parity with Core**; buildAdjustments mapping (stable keys → final indices; canonical sorted ops); probe helper |
| FE unit | `packages/web/lib/importing/opsState.test.ts` | applySplit/clearSplit/mergeWithNext (incl. run coalescing, split-neighbor refusal)/unmergeAt/canMergeWithNext |
| FE unit | `packages/web/components/studio/importing/ImportPreviewPanel.test.tsx` | split via picker updates rows + selection; merge/unmerge; rename survives a subsequent merge (key stability); exclusion; empty-input reverts to suggested; probe false → no op controls; published selection shape v2 |
| FE unit | `ImportModal.test.tsx` + wizard tests | commit called with `buildAdjustments` output (incl. ops); degrade path unchanged |

Coverage targets per RULE-10 (Core ≥ 90 %, API ≥ 80 %) — new modules land
with full suites from day one (RULE-20).

---

## §9 Risks & assumptions

| # | Risk | Mitigation / status |
|---|------|---------------------|
| R1 | **Index-space confusion** (original vs final vs stable keys) — the #1 bug farm | §4.2 space table; cross-task contract table in the plan; FE edits never keyed on final indices; identity property pinned by the unchanged v1 suites |
| R2 | Mirrored semantics drift (FE vs Core) | ONE mirror module; shared golden fixture double-pinned (pytest + vitest); server re-validates everything at commit (FE is display-only authority-wise) |
| R3 | Tokenizer divergence Python `str.split()` vs JS `split(/\s+/)` on exotic whitespace | Golden corpus pins agreement; FE counts are advisory; server recomputes at commit |
| R4 | Cap 200 hides split points in pathological chapters | Documented limitation (D3a); deterministic on both phases |
| R5 | Merge status coercion surprises (first constituent wins) | Documented in §5.2 + UI badge; status not user-overridable in v1 |
| R6 | Preview payload growth from enrichment | Bounded: candidates ≤ 200/chapter, each ≥ 4 bytes of source; same guardrail envelope as v1 |
| R7 | Ops sent to an old server (stale tab) would be silently ignored | Capability probe suppresses all op affordances when `split_candidates` absent; `extra="forbid"` for future fields |

**Assumption ratified:** `SPLIT_CANDIDATES_MAX = 200` and the merge/content
rules are protocol constants (like the v1 guardrails) — no settings
surface, pinned by regression tests.
