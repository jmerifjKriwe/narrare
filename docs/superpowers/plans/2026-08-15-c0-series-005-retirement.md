# C0 — SERIES-005 Retirement (Docs Pass) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formally retire SERIES-005 (Series Export) as YAGNI across all documentation so no reference points to a phantom future spec; declare the Series program complete with Specs 1–4.

**Architecture:** Pure documentation-consistency pass (program item C0 of the post-export-followups program, design doc `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §2). No production code, no schemas, no migrations. Historical records (dated changelog rows, dated CURRENT_STATE entries, INDEX footer "Prior" chains) are **preserved verbatim** — only forward-looking references are annotated.

**Tech Stack:** Markdown docs; verification via `rg` sweep + `just check-ssot` + pre-commit hooks.

## Global Constraints

- **Docs-only.** No file outside the `Files:` lists of the tasks below may be created, modified, or deleted. Zero production code.
- **Project language: English** (all edited text in English).
- **Retirement annotation reference (use verbatim where cited):** `2026-08-14-post-export-followups-design.md` §2 (relative to `docs/superpowers/specs/`).
- **Locate by text, not line numbers.** Line numbers in this plan are from 2026-08-15 and may have drifted; the `oldString` text is the authoritative locator.
- **Never rewrite historical records:** dated changelog rows, dated CURRENT_STATE.md entries, and the INDEX.md footer "Prior …" chain stay untouched (only prepend/append, never edit their interior).
- **One commit per task**, conventional-commit subject + detailed body as given verbatim. NO `--no-verify`/`-n` ever; if a hook fails, STOP and report the exact hook output.
- **No push.** Commits only.
- **Execution gate:** this plan runs only after the PO's explicit go ("noch keine Umsetzung" stands until revoked).

---

### Task 1: ADR Scope-Note Annotations (ADR-075, ADR-077, ADR-078)

**Files:**
- Modify: `docs/architecture/decisions/ADR-075-series-foundation.md` (scope note, ~line 19–23)
- Modify: `docs/architecture/decisions/ADR-077-series-generation-context.md` (scope note, ~line 25–27)
- Modify: `docs/architecture/decisions/ADR-078-series-voice-hierarchy.md` (scope note, ~line 31–33)

**Interfaces:**
- Consumes: none (first task).
- Produces: retirement annotation pattern used by all later tasks: `**Spec 5 (Series Export) was retired 2026-08-14 as YAGNI** (PO decision; see `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §2)`.

- [ ] **Step 1: Edit ADR-075 scope note**

Replace (locate by the text, not the line number):

```markdown
> Series **Generation Context** (Spec 2), **Series Voice Hierarchy** (Spec 3 —
> closes the Voice-Teil of ADR-074's Review Trigger), **Cross-Novel Drift**
> (Spec 4), and **Series Export** (Spec 5) are **downstream program work**,
> flagged here but not designed here. This ADR defines the foundation those
> specs build on.
```

with:

```markdown
> Series **Generation Context** (Spec 2), **Series Voice Hierarchy** (Spec 3 —
> closes the Voice-Teil of ADR-074's Review Trigger), and **Cross-Novel Drift**
> (Spec 4) are **downstream program work** (all implemented),
> flagged here but not designed here. This ADR defines the foundation those
> specs build on. **Spec 5 (Series Export) was retired 2026-08-14 as YAGNI**
> (PO decision; see `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §2).
```

- [ ] **Step 2: Edit ADR-077 scope note**

Replace:

```markdown
> Out of scope here: Series Voice Hierarchy (Spec 3), Cross-Novel Drift
> (Spec 4), Series Export (Spec 5). Each is downstream program work flagged in
> ADR-075's program decomposition but not designed here.
```

with:

```markdown
> Out of scope here: Series Voice Hierarchy (Spec 3) and Cross-Novel Drift
> (Spec 4) — downstream program work (both implemented), flagged in
> ADR-075's program decomposition but not designed here. **Spec 5 (Series
> Export) was retired 2026-08-14 as YAGNI** (PO decision; see
> `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §2).
```

- [ ] **Step 3: Edit ADR-078 scope note**

Replace:

```markdown
> the `AuthorVoiceConsumer` Delta composition. Series **Cross-Novel Drift** (Spec 4)
> and **Series Export** (Spec 5) are **downstream program work**, flagged here but
> not designed here.
```

with:

```markdown
> the `AuthorVoiceConsumer` Delta composition. Series **Cross-Novel Drift** (Spec 4)
> is **downstream program work** (implemented), flagged here but
> not designed here. **Spec 5 (Series Export) was retired 2026-08-14 as YAGNI**
> (PO decision; see `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §2).
```

- [ ] **Step 4: Verify edits**

Run: `rg -n "Spec 5" docs/architecture/decisions/ADR-075-series-foundation.md docs/architecture/decisions/ADR-077-series-generation-context.md docs/architecture/decisions/ADR-078-series-voice-hierarchy.md`
Expected: exactly 3 hits, each containing "retired 2026-08-14 as YAGNI". No hit containing "downstream program work" adjacent to "Series Export".

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/decisions/ADR-075-series-foundation.md docs/architecture/decisions/ADR-077-series-generation-context.md docs/architecture/decisions/ADR-078-series-voice-hierarchy.md
git commit -m "$(cat <<'EOF'
docs(series): retire SERIES-005 (Series Export) as YAGNI — ADR scope notes

C0 of the post-export-followups program (design doc
docs/superpowers/specs/2026-08-14-post-export-followups-design.md §2,
commit 7e97008d). PO decision 2026-08-14: neither hypothesized export
mode solves a real user problem — Reihen-Manuskript is a niche edge
case (per-band export already exists via IO-001; beta readers and
publishers receive individual bands), Reihen-Bibel is
niche-of-niche for a local-first single-user tool. Both modes were
pre-IO-001 speculation (2026-07-28 spec notes), never validated
against a user problem.

Annotate the forward-looking scope notes of ADR-075, ADR-077, and
ADR-078: Spec 5 removed from the downstream-work lists and marked
retired; Specs 1-4 marked implemented. Historical decision text
otherwise preserved verbatim.

Verification: rg sweep — 3 hits, all carrying the retirement
annotation; no remaining "Series Export … downstream program work"
forward reference in these three files.

No production code. Series program formally complete with Specs 1-4.
EOF
)"
```

---

### Task 2: ADR-079 Retirement Annotations (scope note, sustainability check, review trigger)

**Files:**
- Modify: `docs/architecture/decisions/ADR-079-series-cross-novel-drift.md` (three locations: scope note ~line 30–31, sustainability check ~line 217–219, review-trigger checklist ~line 458–459)

**Interfaces:**
- Consumes: retirement annotation pattern from Task 1.
- Produces: ADR-079 review-trigger checklist item resolved N/A (referenced by the C2 drift-persistence slice later — its ADR-079 amendment builds on this).

- [ ] **Step 1: Edit ADR-079 scope note**

Replace:

```markdown
> with the **current-band-vs-series** read-scope. Series **Export** (Spec 5) is **downstream
> program work**, flagged here but not designed here.
```

with:

```markdown
> with the **current-band-vs-series** read-scope. Series **Export** (Spec 5) was **retired
> 2026-08-14 as YAGNI** (PO decision; see
> `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §2).
```

- [ ] **Step 2: Edit ADR-079 sustainability check**

Replace:

```markdown
1. **Correct in 3 months?** Yes — Spec 5 (Export) does not touch the drift surface; the
   current-band read-scope + stateless v1 are additive. A future full-series scan or
   persistence layer extends without undoing this work.
```

with:

```markdown
1. **Correct in 3 months?** Yes — Spec 5 (Export) was retired (2026-08-14, YAGNI) and does
   not touch the drift surface; the current-band read-scope + stateless v1 are additive. A
   future full-series scan or persistence layer extends without undoing this work.
```

- [ ] **Step 3: Resolve the review-trigger checklist item as N/A**

Replace:

```markdown
- [ ] When **Spec 5 (Series Export)** is implemented — verify the drift/consistency results
      (once persisted) can feed an export-quality report if desired.
```

with:

```markdown
- [x] ~~When **Spec 5 (Series Export)** is implemented — verify the drift/consistency results
      (once persisted) can feed an export-quality report if desired.~~
      **N/A — Spec 5 retired 2026-08-14 as YAGNI** (PO decision; see
      `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §2).
```

- [ ] **Step 4: Verify edits**

Run: `rg -n "Spec 5" docs/architecture/decisions/ADR-079-series-cross-novel-drift.md`
Expected: exactly 3 hits (scope note, sustainability check, review-trigger), each containing "retired" or "N/A". No unchecked checklist item referencing Spec 5.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/decisions/ADR-079-series-cross-novel-drift.md
git commit -m "$(cat <<'EOF'
docs(series): retire SERIES-005 — ADR-079 scope, sustainability, review-trigger

C0 continuation (design doc §2, commit 7e97008d). Three annotations
in ADR-079:

1. Scope note: "Series Export (Spec 5) is downstream program work"
   replaced with the retirement note (PO decision 2026-08-14, YAGNI).
2. Sustainability check answer 1: corrected to record that Spec 5 was
   retired rather than treating it as future adjacent work.
3. Review-trigger checklist: the open item "When Spec 5 (Series
   Export) is implemented — verify the drift/consistency results can
   feed an export-quality report" resolved as N/A (checked +
   strikethrough + retirement reference), because the precondition
   (Spec 5 being built) will never occur.

Rationale (from the approved design): both export modes were
pre-IO-001 speculation never validated against a user problem; the
Series program is formally complete with Specs 1-4.

Verification: rg sweep — 3 hits, all annotated; no unchecked Spec 5
checklist item remains.

No production code.
EOF
)"
```

---

### Task 3: Series Feature-Spec Position Paragraphs (SERIES-001, SERIES-002, SERIES-003)

**Files:**
- Modify: `docs/features/series/SERIES-001-foundation.md` (position paragraph, ~line 71–73)
- Modify: `docs/features/series/SERIES-002-generation-context.md` (position paragraph, ~line 69–71)
- Modify: `docs/features/series/SERIES-003-voice-hierarchy.md` (position paragraph, ~line 77–79)

**Interfaces:**
- Consumes: retirement annotation pattern from Task 1.
- Produces: none consumed downstream.

- [ ] **Step 1: Edit SERIES-001 position paragraph**

Replace:

```markdown
This is the foundation spec (Spec 1 of 5) for the Series program. Later specs add
Series Generation Context (Spec 2), Series Voice Hierarchy (Spec 3), Cross-Novel
Drift (Spec 4), and Series Export (Spec 5).
```

with:

```markdown
This is the foundation spec (Spec 1 of 5) for the Series program. Later specs add
Series Generation Context (Spec 2), Series Voice Hierarchy (Spec 3), and Cross-Novel
Drift (Spec 4). Spec 5 (Series Export) was retired 2026-08-14 as YAGNI (PO decision);
the Series program is complete with Specs 1–4.
```

- [ ] **Step 2: Edit SERIES-002 position paragraph**

Replace:

```markdown
This is Spec 2 of 5 in the Series program. Spec 1 (Foundation) is implemented;
Spec 3 (Voice Hierarchy), Spec 4 (Cross-Novel Drift), and Spec 5 (Export)
remain downstream.
```

with:

```markdown
This is Spec 2 of 5 in the Series program. Spec 1 (Foundation) is implemented;
Spec 3 (Voice Hierarchy) and Spec 4 (Cross-Novel Drift) are implemented.
Spec 5 (Export) was retired 2026-08-14 as YAGNI (PO decision); the Series
program is complete with Specs 1–4.
```

- [ ] **Step 3: Edit SERIES-003 position paragraph**

Replace:

```markdown
This is Spec 3 of 5 in the Series program. Spec 1 (Foundation) and Spec 2
(Generation Context) are implemented; Spec 4 (Cross-Novel Drift) and Spec 5
(Export) remain downstream.
```

with:

```markdown
This is Spec 3 of 5 in the Series program. Spec 1 (Foundation) and Spec 2
(Generation Context) are implemented; Spec 4 (Cross-Novel Drift) is implemented.
Spec 5 (Export) was retired 2026-08-14 as YAGNI (PO decision); the Series
program is complete with Specs 1–4.
```

- [ ] **Step 4: Verify edits**

Run: `rg -n "remain downstream|remains downstream" docs/features/series/SERIES-001-foundation.md docs/features/series/SERIES-002-generation-context.md docs/features/series/SERIES-003-voice-hierarchy.md`
Expected: 0 hits.

- [ ] **Step 5: Commit**

```bash
git add docs/features/series/SERIES-001-foundation.md docs/features/series/SERIES-002-generation-context.md docs/features/series/SERIES-003-voice-hierarchy.md
git commit -m "$(cat <<'EOF'
docs(series): retire SERIES-005 — feature-spec position paragraphs 1-3

C0 continuation (design doc §2, commit 7e97008d). The program-position
paragraphs of SERIES-001 (Foundation), SERIES-002 (Generation
Context), and SERIES-003 (Voice Hierarchy) no longer list Spec 5
(Export) as remaining downstream; each now records the retirement
(PO decision 2026-08-14, YAGNI) and the Series program's formal
completion with Specs 1-4.

Verification: rg sweep — 0 "remain(s) downstream" hits in the three
files; each file carries the retirement sentence.

No production code.
EOF
)"
```

---

### Task 4: SERIES-004 + Cross-Spec Notes Annotation

**Files:**
- Modify: `docs/features/series/SERIES-004-cross-novel-drift.md` (two locations: position paragraph ~line 87–88, status-history tail ~line 213–214)
- Modify: `docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md` (five locations: header lines ~12 and ~14–15, Spec-5 section banner ~162, YAGNI-table rows ~234 and ~236, changelog append after row ~268)

**Interfaces:**
- Consumes: retirement annotation pattern from Task 1.
- Produces: none consumed downstream (the changelog row appended here is the program's decision record in the living notes file).

- [ ] **Step 1: Edit SERIES-004 position paragraph**

Replace:

```markdown
This is Spec 4 of 5 in the Series program. Specs 1–3 are implemented; Spec 5
(Export) remains downstream.
```

with:

```markdown
This is Spec 4 of 5 in the Series program. Specs 1–3 are implemented.
Spec 5 (Export) was retired 2026-08-14 as YAGNI (PO decision); the Series
program is complete with Specs 1–4.
```

- [ ] **Step 2: Edit SERIES-004 status-history tail**

Replace:

```markdown
  one signal via the repository contract). Status → `stable`. The Series
  program Spec 1–4 is complete; Spec 5 (Export) is downstream.
```

with:

```markdown
  one signal via the repository contract). Status → `stable`. The Series
  program Spec 1–4 is complete; Spec 5 (Export) was retired 2026-08-14 as
  YAGNI (PO decision).
```

- [ ] **Step 3: Update spec-notes header**

Replace:

```markdown
> **Created:** 2026-07-28
> **Last updated:** 2026-08-06 (Specs 1–4 COMPLETE; Spec 5 deferred as a separate feature)
>
> **Program status:** Specs 1–4 COMPLETE (ADR-075 / ADR-077 / ADR-078 / ADR-079 — all ✅
> Implemented). Spec 5 (Series Export) is deferred as a separate feature.
```

with:

```markdown
> **Created:** 2026-07-28
> **Last updated:** 2026-08-14 (Specs 1–4 COMPLETE; **Spec 5 RETIRED as YAGNI** — PO decision; Series program formally complete)
>
> **Program status:** Specs 1–4 COMPLETE (ADR-075 / ADR-077 / ADR-078 / ADR-079 — all ✅
> Implemented). Spec 5 (Series Export) was RETIRED 2026-08-14 as YAGNI (PO decision) —
> the Series program is formally complete. No Spec 5 brainstorming cycle will occur.
```

- [ ] **Step 4: Add retirement banner to the Spec-5 notes section**

Insert immediately after the line `## Notes for Spec 5 — Series Export` (leave one blank line before and after the banner):

```markdown
> **⚠ RETIRED 2026-08-14 (YAGNI, PO decision):** Spec 5 will not be built.
> The notes below are preserved as the historical brainstorming record.
> See `2026-08-14-post-export-followups-design.md` §2 for the retirement rationale.
```

Do NOT modify or delete the existing notes under that heading.

- [ ] **Step 5: Update the two Spec-5 target rows in the YAGNI table**

Replace:

```markdown
| **Series cover image upload** | Spec 5 (Export) | Cosmetic; not Foundation |
```

with:

```markdown
| **Series cover image upload** | No Spec (retired with Spec 5, 2026-08-14) | Cosmetic; no validated user problem |
```

Replace:

```markdown
| **Series-Export** (Manuscript, Bibel) | Spec 5 | Out of Foundation scope |
```

with:

```markdown
| **Series-Export** (Manuscript, Bibel) | RETIRED with Spec 5 (2026-08-14, YAGNI) | No real user problem for a local-first single-user tool; see design doc §2 |
```

All other table rows stay untouched (including the dated historical rows above them).

- [ ] **Step 6: Append the retirement decision row to the changelog table**

After the row dated `2026-08-06` (the last row of the decision-log table; locate it by its leading text `| 2026-08-06 | Spec 4 = Series Cross-Novel Drift (ADR-079)`), append this new row:

```markdown
| 2026-08-14 | Spec 5 (Series Export) RETIRED as YAGNI — PO decision: Reihen-Manuskript is a niche edge case (per-band export already exists via IO-001; beta readers and publishers receive individual bands), Reihen-Bibel is niche-of-niche for a local-first single-user tool; Series program formally complete with Specs 1–4 | Both hypothesized export modes were pre-IO-001 speculation, never validated against a user problem | Program closure (docs pass C0; see `2026-08-14-post-export-followups-design.md` §2) |
```

Do NOT modify the existing 2026-08-06 row (its trailing column still reads "Spec 5 (Export) remains deferred as a separate feature" — that is the historical record and stays).

- [ ] **Step 7: Verify edits**

Run: `rg -n "Spec 5" docs/features/series/SERIES-004-cross-novel-drift.md docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md`
Expected: every hit is either (a) a retirement annotation ("RETIRED"/"retired"/"No Spec (retired"), (b) the historical 2026-08-06 changelog row (untouched, ends with "remains deferred as a separate feature"), or (c) the preserved brainstorming notes under the retired-section banner. Zero hits claiming Spec 5 is future work outside category (b).

- [ ] **Step 8: Commit**

```bash
git add docs/features/series/SERIES-004-cross-novel-drift.md docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md
git commit -m "$(cat <<'EOF'
docs(series): retire SERIES-005 — SERIES-004 spec + cross-spec notes

C0 continuation (design doc §2, commit 7e97008d).

SERIES-004: position paragraph and status-history tail no longer
list Spec 5 (Export) as downstream; both record the retirement
(PO decision 2026-08-14, YAGNI) and program completion.

Cross-spec notes (2026-07-28-series-cross-spec-notes.md):
- Header "Last updated"/"Program status" now record the retirement
  and state that no Spec 5 brainstorming cycle will occur.
- The "Notes for Spec 5 — Series Export" section carries a RETIRED
  banner; the brainstorming notes below it are preserved verbatim as
  the historical record.
- YAGNI table: the two Spec-5-target rows (series cover image
  upload, Series-Export) retargeted to "retired with Spec 5".
- Decision-log changelog: new 2026-08-14 row records the retirement
  decision with rationale. The existing dated rows (incl. the
  2026-08-06 row whose trailing column says "Spec 5 ... remains
  deferred") are historical records and remain untouched.

Verification: rg sweep per plan Task 4 Step 7 — all hits are
annotations, the preserved notes, or the historical changelog row.

No production code.
EOF
)"
```

---

### Task 5: Feature INDEX + CURRENT_STATE

**Files:**
- Modify: `docs/features/INDEX.md` (two locations: Series-section note ~line 113–115, footer line beginning `> Last updated: 2026-08-14 — IO-001`)
- Modify: `docs/_shared/CURRENT_STATE.md` (insert one new date entry above the `Date: 2026-08-14 (IO-001 follow-ups **merged** …)` entry)

**Interfaces:**
- Consumes: retirement annotation pattern from Task 1.
- Produces: CURRENT_STATE entry describing the approved program (C0–B) — the anchor future sessions read first.

- [ ] **Step 1: Edit the INDEX Series-section note**

Replace:

```markdown
> commit `ede62081` before the #145 squash-merge. **The Series program Spec 1–4
> is complete; Spec 5 (Export) is the downstream next step.**
```

with:

```markdown
> commit `ede62081` before the #145 squash-merge. **The Series program Spec 1–4
> is complete and formally closed; Spec 5 (Export) was retired 2026-08-14 as YAGNI
> (PO decision — see `../superpowers/specs/2026-08-14-post-export-followups-design.md` §2).**
```

- [ ] **Step 2: Prepend the new footer "Last updated" segment**

Locate the footer line that begins:

```markdown
> Last updated: 2026-08-14 — IO-001 (Manuscript Export Pipeline) → `stable` (
```

Replace only the head `> Last updated: 2026-08-14 — IO-001 (Manuscript Export Pipeline)` with:

```markdown
> Last updated: 2026-08-15 — SERIES-005 (Series Export) retired as YAGNI (PO decision 2026-08-14; Series program formally complete with Specs 1–4; docs-consistency pass C0 of the post-export-followups program). Prior 2026-08-14 — IO-001 (Manuscript Export Pipeline)
```

The remainder of that (single) footer line — everything after `(Manuscript Export Pipeline)` — stays byte-identical. Do not reflow or rewrap it.

- [ ] **Step 3: Insert the CURRENT_STATE date entry**

Insert the following entry as the new first entry of the `## Last Updated` list (above the entry starting `Date: 2026-08-14 (IO-001 follow-ups **merged**`):

```markdown
Date: 2026-08-15 (Post-Export-Follow-ups program approved — **SERIES-005 (Series Export) formally RETIRED as YAGNI** (PO decision 2026-08-14: Reihen-Manuskript = niche edge case, per-band export already sufficient via IO-001; Reihen-Bibel = niche-of-niche for a local-first single-user tool; both modes were pre-IO-001 speculation, never user-problem-validated). **Series program formally complete with Specs 1–4.** Design doc: [2026-08-14-post-export-followups-design.md](superpowers/specs/2026-08-14-post-export-followups-design.md), commit `7e97008d`. Program scope, execution order C0→C5→C1→C2→C3→C4→B: **C5** = token-budget governance (new ADR-082: series-history 16k / writing-total 32k defaults into the SET-005 cascade, model-boundary capping `min(configured, window − reserve)`, min() principle — no auto-scaling, 1M windows only via explicit user config; closes CR-08 P0 "model-boundary/tier-budget adoption"). **C1** = context_window_size slider (1–10) with live token preview against effective post-C5 budgets. **C2** = SERIES-004 Slice 6 drift persistence (full payload, latest-wins, stale flag via input fingerprint, `GET …/consistency/{novel_id}`, Alembic 0040, ADR-079 amendment). **C3** = DOCX export via `--reference-doc` manuscript format + golden test on unzipped `document.xml`. **C4** = coverage-baseline reconciliation (case-by-case, no blanket lowering). **B** = I-Copy-001 formality register per existing Q-015 spec. C0 (this entry's commit): retirement docs pass — ADR-075/077/078/079 annotated (incl. ADR-079 review-trigger N/A), SERIES-001–004 position paragraphs, feature INDEX + cross-spec notes; historical changelog rows and dated entries preserved verbatim. Implementation of C5 onward NOT yet started — plans follow per item.)
```

- [ ] **Step 4: Verify edits**

Run: `rg -n "downstream next step" docs/features/INDEX.md`
Expected: 0 hits.

Run: `rg -n "Last updated: 2026-08-15" docs/features/INDEX.md docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md`
Expected: 1 hit (INDEX footer). Note: the spec-notes header intentionally says `Last updated: 2026-08-14` (the decision date), not 08-15.

- [ ] **Step 5: Commit**

```bash
git add docs/features/INDEX.md docs/_shared/CURRENT_STATE.md
git commit -m "$(cat <<'EOF'
docs(series): retire SERIES-005 — feature INDEX + CURRENT_STATE program entry

C0 completion (design doc §2, commit 7e97008d).

Feature INDEX: the Series-section note now declares the program
formally closed (Spec 5 retired 2026-08-14 as YAGNI, PO decision)
instead of naming Spec 5 "the downstream next step". Footer gains a
new 2026-08-15 head segment; the prior "Last updated" chain is
preserved byte-identical as history.

CURRENT_STATE: new 2026-08-15 entry records (a) the SERIES-005
retirement decision + rationale, (b) Series program completion with
Specs 1-4, (c) the approved post-export-followups program scope and
execution order C0->C5->C1->C2->C3->C4->B with the binding decisions
per item (16k/32k token defaults + min() principle + model-boundary
capping; slider 1-10 with live preview; drift persistence
latest-wins + stale fingerprint + Alembic 0040; DOCX reference.docx
+ document.xml golden test; case-by-case coverage reconciliation;
I-Copy-001 per Q-015), and (d) that implementation beyond C0 has
NOT started — per-item plans follow.

Verification: rg sweeps per plan Task 5 Step 4 — "downstream next
step" 0 hits; exactly 1 "Last updated: 2026-08-15" hit.

No production code.
EOF
)"
```

---

### Task 6: Verification Sweep (gate, no edits)

**Files:**
- None (read-only verification).

**Interfaces:**
- Consumes: all edits from Tasks 1–5.
- Produces: the C0 gate evidence (recorded in the execution report; no commit).

- [ ] **Step 1: Global Spec-5 sweep**

Run: `rg -n "Spec 5|SERIES-005" docs/`

Classify every hit into exactly one category — all hits must fall into (a)–(d), otherwise STOP and report:

- (a) **Retirement annotations** (contain "retired"/"RETIRED"/"N/A"/"No Spec (retired")
- (b) **Historical records** (dated CURRENT_STATE entries ≤ 2026-08-14, the spec-notes 2026-08-06 changelog row, INDEX footer "Prior …" chain segments)
- (c) **Program documents** (`2026-08-14-post-export-followups-design.md`, this plan file, memory-adjacent notes under `docs/superpowers/`)
- (d) **Preserved brainstorming notes** under the RETIRED banner in the cross-spec notes

- [ ] **Step 2: Forward-reference zero-check**

Run: `rg -n "Spec 5.*(downstream|next step|remain|deferred as a separate feature|will be)" docs/ --glob '!docs/superpowers/plans/2026-08-15-c0-series-005-retirement.md' --glob '!docs/superpowers/specs/2026-08-14-post-export-followups-design.md'`

Expected: only category-(b) historical hits (CURRENT_STATE dated entries, the 2026-08-06 changelog row, INDEX footer Prior-chain). Any hit in a live/forward-looking section = FAIL → fix root cause before proceeding.

- [ ] **Step 3: Repo checks**

Run: `just check-ssot`
Expected: PASS (same status as before the pass; if it was already failing on unrelated grounds, report the delta — do not fix unrelated issues here).

Run: `git log --oneline -6`
Expected: the five C0 commits from Tasks 1–5 on top of `7e97008d`.

- [ ] **Step 4: Report (no commit)**

Report the sweep classifications (hit counts per category), the check-ssot result, and the commit list. C0 is done; the program continues with C5 (Architecture session → ADR-082 → C5 plan).

---

## Plan Self-Review (already executed)

1. **Spec coverage:** design doc §2 lists four work targets — INDEX.md (Task 5), spec-notes (Task 4), ADR-075/077/078/079 (Tasks 1–2), review-trigger N/A (Task 2). Series feature files added per "no dangling references" goal (Tasks 3–4). CURRENT_STATE entry = program anchor (Task 5). Verification gate = Task 6. ✓
2. **Placeholder scan:** every edit step carries literal old/new strings; every commit step carries a full message body. No TBD/TODO. ✓
3. **Type consistency:** the retirement annotation reference string is identical across all tasks; task file lists match the `git add` commands. ✓
4. **Historical-record invariant** (global constraint) is enforced structurally: Tasks 4/5 only prepend/append to historical artifacts, never edit their interior. ✓
