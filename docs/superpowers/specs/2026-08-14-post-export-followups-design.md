# Post-Export Follow-ups Program — Design

> **Date:** 2026-08-14
> **Status:** Approved (PO sign-off 2026-08-14, all 8 design sections)
> **Origin:** Brainstorming session 2026-08-14 — "what is the next feature?"
> **Terminal state:** Each item below gets its own implementation plan via
> `writing-plans`; this doc is the binding design input.

---

## 1 · Context & Session Origin

The session opened with three candidate tracks:

- **A — SERIES-005 Series Export** (documented as the "downstream next step"
  of the Series program after Spec 1–4 went stable)
- **C — Deferred remnants** (SERIES-002 slider, SERIES-004 Slice 6,
  IO-001 DOCX, coverage baselines)
- **B — I-Copy-001 Formality Register** (fully specified via Q-015)

PO selected **A + C + B**. During clarifying questions, **A was retired**
(see §2 — the two hypothesized export modes solve no real user problem for a
local-first single-user tool). Mid-session, the token-budget investigation
around the SERIES-002 slider surfaced a genuine defect class (hardcoded
runtime token budgets bypassing the SET-005 configuration cascade), which
was promoted to a first-class work item (**C5**, the largest item of the
program).

**Final program scope: C0 → C5 → C1 → C2 → C3 → C4 → B** (seven items).

---

## 2 · C0 — SERIES-005 Retirement (Docs only)

Spec 5 (Series Export: Reihen-Manuskript + Reihen-Bibel) is **formally
retired as won't-do / YAGNI** (PO decision 2026-08-14).

**Rationale (from the session, recorded honestly):**

- *Reihen-Manuskript* (all bands concatenated into one document): a niche
  edge case. Beta readers and publishers receive individual bands; per-band
  export already exists via IO-001. Concatenation adds minimal value.
- *Reihen-Bibel* (Series-Canon KB export for publisher/agent handoff):
  niche-of-a-niche for a local-first single-user tool. The KB exists for AI
  context and the author's own reference; it needs no export artifact.

The modes were pre-IO-01 speculation ("likely", 2026-07-28 spec notes),
never validated against a user problem.

**Work:** documentation consistency pass only —

- `docs/features/INDEX.md` (Series section): Spec 5 marked retired/YAGNI;
  Series program declared **formally complete** (Specs 1–4).
- `docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md`: Spec-5
  notes annotated with the retirement decision.
- ADR-075 / ADR-077 / ADR-078 / ADR-079: "Spec 5 downstream" references
  annotated; ADR-079's review-trigger checklist item
  ("When Spec 5 is implemented — verify drift/consistency results…")
  resolved as **N/A (Spec 5 retired)**.

No code. One Docs task.

---

## 3 · C5 — Token-Budget Governance (new ADR-082)

The defect class behind the session's 512-token finding:

- `SeriesHistoryProvider._DEFAULT_TOKEN_BUDGET = 512` (apps/api) mirrors
  `SeriesHistoryTier(token_budget=512)` (core) — **hardcoded, not wired into
  any configuration surface** (no SET-005 cascade, no CoreSettings, no
  SeriesSettings).
- `TokenBudgetManager.DEFAULT_TOTAL_BUDGET = 6000` (writing context, class
  default) and `AnalysisBudgetManager` 6000 — same class of problem,
  conservative to the point of silently dropping information.
- The 512 default is **inconsistent with its own feature**: the default
  recency window (3 full band summaries ≈ 1200+ tokens) cannot fit into 512
  tokens. The default configuration structurally never delivers what it
  promises — ~1 full band survives, the second is truncated, the third is
  silently dropped.

**Root-cause rule violated:** runtime token limits must flow through the
configuration cascade (SET-005 storage → API → UI → Core;
ADR-071 CoreSettings pattern for Core env-var config), not live as code
constants. "Hardcoded" here means *bypassing the cascade*, not the existence
of a fallback default.

### 3.1 Binding decisions

| # | Decision | Value / Rule |
|---|----------|--------------|
| D1 | Series-history token budget default | **16 000** (replaces 512) |
| D2 | Writing-total token budget default | **32 000** (replaces 6000) |
| D3 | Sub-budget semantics | Series-history 16k is **within** the 32k writing total (a tier of it), **not additive** (total stays 32k, not 48k) |
| D4 | Model-boundary capping | Effective budget = `min(configured/default, model_context_window − reserve)`. Window size sourced from existing ModelRegistry data. Protects local-first deployments (e.g. 8k-context local models get valid requests, not truncated/broken ones) |
| D5 | Scaling policy — **min() principle** | Defaults are ceilings. Scaling up (e.g. exploiting 1M-token-window models) happens **only via explicit user configuration** (SET-005), never automatically. Rationale: auto-scaling against paid APIs is a cost footgun (~25% of 1M ≈ 250k tokens per generation call); local usage is free but the system cannot know that. |
| D6 | Rationale for magnitude | Budgets are **ceilings, not consumption mandates** — tiers fill by content availability. Low defaults saved nothing; they silently dropped information. Modern model windows (128k…1M) make the old values unjustifiable. |

### 3.2 Scope

1. **Cascade integration:** series-history budget + writing-total budget
   become configurable (SET-005 cascade / ADR-071 CoreSettings pattern)
   with the new defaults D1/D2.
2. **Model-boundary capping (D4):** budget resolver honors the configured
   model's context window with a reserve (system/meta/output headroom).
3. **Constant inventory:** all token-related constants in the codebase are
   inventoried and classified — either lifted into the cascade or documented
   as legitimate Core-internal heuristics (e.g. the 4-chars/token estimator
   stays; it is an estimation heuristic, not a runtime limit).
4. Closes the open CR-08 P0 item **"model-boundary/tier-budget adoption"**
   from CURRENT_STATE / SET-005.

### 3.3 Tests

- Budget-resolver unit tests (new defaults, capping arithmetic, reserve).
- Existing 512/6000-default regression tests are **deliberately rewritten**
   to the new values — a documented, intentional default break (behavior
   change is the point of the fix).
- Analysis-context budget (6000) is inventoried; whether it also moves to
   32k is decided in the ADR-082 architecture session with evidence about
   analysis-tier consumption (not pre-committed here).

### 3.4 Deliverables

ADR-082 (token-budget governance) + implementation slices. Architecture-
first: the ADR precedes any implementation (new module boundary: budget
resolver).

---

## 4 · C1 — Context-Window Slider (SERIES-002 remainder)

The `context_window_size` setting (DB `series_settings`, default 3) works
but is **not exposed**: no settings-API surface, no UI. Effectively pinned
to 3.

### 4.1 Binding decisions

| # | Decision |
|---|----------|
| Slider range | **1–10** |
| Placement | Series-Workspace → Settings tab; slider with value display + help text |
| API | PATCH via the **existing** series-settings endpoint (no new router) |
| Honesty requirement | **Live preview** computed from the series' *actual* summaries against the **effective budgets** (post-C5): pattern `"3 Bänder voll — ca. 440 / 16 000 Tokens; größeres Window wird vom Budget gekürzt"`. Exact copy/i18n in implementation plan. |

### 4.2 Rationale

The slider alone would be a lie by omission: the token budget silently
clips oversized windows. The preview makes the interaction of both limits
visible, using real data (live computation, no estimation). Range 1–10 is
safe precisely because the preview shows when larger values run into the
budget ceiling.

**Dependency: C5 first** — the preview must compute against the effective
(cascaded, capped) budgets, not the old hardcoded 512.

---

## 5 · C2 — Drift Persistence (SERIES-004 Slice 6)

The cross-novel drift check (canon contradictions + series-scope voice
drift) is stateless v1: results vanish when the panel closes; re-viewing
means re-paying LLM costs. Slice 6 persists results.

### 5.1 Binding decisions

| # | Decision | Detail |
|---|----------|--------|
| Stored payload | **Full result set** | Canon conflicts **and** voice drift as one JSON document — one fetch, one consistent snapshot |
| History model | **Latest-wins** | Exactly one record per novel; new run overwrites; `generated_at` timestamp. History/trajectory comparison is YAGNI (2–3× complexity: listing, cleanup, UI). |
| Staleness | **Stale flag via input fingerprint** | On save, store a hash over the band's chapter texts. `GET` recomputes the current hash and returns `stale: true/false`. Honest and cheap; the fingerprint pattern already exists in the codebase (evidence pipeline). |
| Retrieval | `GET …/consistency/{novel_id}` | The originally sketched shape from SERIES-004 deferral — unchanged. |

### 5.2 Scope

- Alembic migration **0040** (new table, RULE-14 atomic up/down).
- Results repository + service extension (store on run, fetch with stale
  computation).
- Frontend: load persisted snapshot instead of empty state when present.
- ADR-079 anticipated Slice 6 — documented as a **post-implementation
  amendment** to ADR-079, no new ADR.

---

## 6 · C3 — DOCX Export (IO-001 extension)

### 6.1 Binding decision

**Manuscript format via `--reference-doc`** — not pandoc's plain default,
not a configurable template system (YAGNI).

### 6.2 Scope

- One maintained `reference.docx` (Times 12 pt, 1.5 line spacing,
  first-line indent, centered chapter headings — the classic publishing
  manuscript format = the use case that justifies DOCX at all), stored in
  the export vendor area.
- New `PandocDocxRenderer` (RULE-08 renderer adapter, same seam as
  PDF/EPUB/MD).
- Format option in the existing export UI + i18n (en/de/fr).
- **Verification:** golden test on the unzipped `document.xml`
  (docx = zipped XML with timestamps → byte-diff impossible); analogous to
  the Golden-Pages procedure.
- IO-001 feature spec gains the DOCX format (was explicitly deferred as
  "feature-spec change, not engine decision"). **No new ADR** — ADR-081's
  engine decision applies unchanged.

---

## 7 · C4 — Coverage-Baseline Reconciliation (Platform pass)

After the 2026-08-10 CI fixes, 7 modules sit marginally below their
coverage baselines (e.g. `evidence/` 91.1% vs 99.0%) while remaining above
target thresholds (80%/95%); CI was green. This is bookkeeping drift, not a
user-facing defect.

**Work:** case-by-case reconciliation — either raise tests back up or
honestly adjust baselines, each with a stated reason. No blanket lowering.
No ADR. Platform slice with evidence.

---

## 8 · B — I-Copy-001 Formality Register (existing spec)

No redesign. The approved spec (Q-015 resolution:
[docs/features/i18n/I-Copy-001-formality-register.md]) is implemented 1:1:

- Sparse `formality/{de,fr}.json` overlay deep-merged over base messages in
  the next-intl loader (`lib/i18n/request.ts`) when cookie
  `NEXT_FORMALITY=formal`; `en` unchanged; zero call-site migration;
  next-intl untouched; cookie-only persistence (no backend/migration in v1).
- RULE-02 boundary verified (UI-copy-only; cannot reach `core/prompts/`).
- Effort profile: infrastructure ~1 day; the real cost is editorial
  (~150–300 formal DE/FR variants to author/review).

Deliberately last in the program (editorial, not architectural, risk).

---

## 9 · Execution Order & Rationale

**C0 → C5 → C1 → C2 → C3 → C4 → B**

- **C0 first:** pure docs; closes the Series program formally so nothing
  downstream references a phantom.
- **C5 before C1:** the slider preview computes against effective
  (cascaded + capped) budgets — C1 is dishonest until C5 lands.
- **C2, C3, C4** independent of each other (ordered by program logic:
  Series-remainder → IO-remainder → CI hygiene).
- **B last:** editorial-heavy, zero architectural risk.

Each item = its own implementation plan (via `writing-plans`) executed
task-by-task (via `subagent-driven-development`), with the standard
package-sizing cap per delegation (≤3 files / ≤250 LOC) and contract-first
discipline (RULE-03). Bug-fix-class work inside C5 is regression-first.

---

## 10 · Deviations from Initial Session Plan (honest record)

| Original (session start) | Actual (approved design) | Reason |
|---|---|---|
| A = SERIES-005 Series Export as the headline feature | **Retired** (C0 documents it); program recentered on C5 | PO judgment during clarifying questions: neither hypothesized export mode solves a real user problem ("ehrlich gesagt braucht man keins davon") |
| C = 4 fixed remnants (slider, drift persistence, DOCX, coverage) | 5 items — **C5 Token-Budget Governance added** | Session-uncovered defect: hardcoded runtime token budgets bypassing the SET-005 cascade (512 series-history / 6000 writing-total); PO escalated ("weltfremde und praxisferne Token-Vorgaben") and set the new magnitude (16k/32k, 1M-window awareness) |
| Series-history budget fix contemplated as a constant bump (2048 was proposed mid-session) | Rejected as insufficient; **cascade integration + model-boundary capping + min() principle** (D1–D6) | A constant bump would repeat the root-cause violation (bypassing the cascade); PO: "hardcoded ist eh untersagt" |
| Writing-total default candidates 32k vs 64k | **32k** (PO call, Q3a) | Safe fallback for unknown models; fits any 128k model with reserves |
| Auto-scaling policy candidate (budget grows with model window, ×0.25) | Rejected — **min() principle** (PO call, Q3b-i) | Auto-upscaling against paid APIs is a cost footgun; 1M windows remain fully usable via explicit SET-005 configuration |

## 11 · Out of Scope (YAGNI, explicit)

- **Reihen-Manuskript / Reihen-Bibel export** — retired (§2), not deferred.
- **Drift-history trajectory comparison** — latest-wins only (§5).
- **Configurable DOCX template system** — one reference.docx (§6).
- **Auto-scaling budgets to model windows** — min() principle (§3.1 D5).
- **Token-budget UI for the series-history budget** — stays
  expert-invisible; the slider preview makes its effect visible (§4).
- Anything from the D-list (WRITE-008, ANAL-011, IO-002, STATS-001/002, …)
  — separate future sessions.

---

## 12 · Per-Item Verification Summary

| Item | Gate |
|---|---|
| C0 | Doc-drift checker green; references resolve; no dangling "Spec 5 next" |
| C5 | Budget-resolver unit tests; rewritten default regressions; `just verify` |
| C1 | Slider + preview tests (live computation, honesty display); settings PATCH tests |
| C2 | Migration round-trip; latest-wins overwrite test; stale-flag flip test |
| C3 | Golden `document.xml` test; i18n keys en/de/fr; RULE-08 checker green |
| C4 | Coverage evidence per module; baselines match actuals or tests raised |
| B | Per existing I-Copy-001 spec DoD |

---

> Approved 2026-08-14 — PO sign-off on all sections ("ok" on §1–§8).
> Next step: `writing-plans` per item, starting with C0.
