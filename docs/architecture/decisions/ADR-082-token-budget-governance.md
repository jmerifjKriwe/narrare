# ADR-082 — Token-Budget Governance: Cascade Integration + Model-Boundary Capping

> **Status:** ✅ Implemented (2026-08-15 — C5 slice Tasks 1a–3d; commits 4cf68e1d…ab03157c; all five Implementation Completeness Gate criteria review-verified)
> **Date:** 2026-08-15
> **Deciders:** Architecture Agent (draft), PO (approved all four open decision
> points 2026-08-15)
> **Decision authority:** PO approved all four decision points 2026-08-15
> (session record: `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §3
> + PO approval date 2026-08-15).
> **Implements:** Program item **C5** of the Post-Export Follow-ups program —
> `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §3
> (binding decisions D1–D6 of that doc are inputs here, not re-decided).
> **Closes:** the open CR-08 **P0** item "model-boundary/tier-budget adoption"
> (`docs/_shared/CURRENT_STATE.md` item 13).
> **Related:** ADR-071 (CoreSettings — cascade-integration pattern reference),
> ADR-045 (Runtime Adoption Enforcement / run-limit resolution precedent),
> ADR-025 (context package ownership), ADR-077 (series-history tier, SERIES-002),
> SET-005 (`docs/features/settings/SET-005-configurable-token-limits.md`),
> CR-08 remediation (`docs/features/remediation/cr-08-configuration-effect-drift.md`)

---

## PO Decision Record (2026-08-15)

The draft presented four open decision points to the PO. **PO decision
2026-08-15: all four approved as recommended** — decided as follows. The
decision substance is unchanged from the draft's recommendations; the mapped
Decisions below are therefore final as written.

| # | Open point (as presented) | PO decision 2026-08-15 (approved as recommended) |
|---|---------------------------|--------------------------------------------------|
| 1 | Key naming — `context_total_budget` vs. "writing-total" | **`context_total_budget`** — one key covering writing **and** analysis (Decision 1) |
| 2 | One knob for writing+analysis vs. a separate `analysis_total_budget` key | **One knob** — analysis shares `context_total_budget` (Decision 5; Axis 4 Option C) |
| 3 | Reserve derivation — `reserve = min(4_000 + effective_output_limit, window // 4)` | **Confirmed as policy**, including the 8k-model → 6,000 continuity property (Decision 4) |
| 4 | Sub-budget semantics — series vs. standalone tier base | **Guarded carve-out**: `series_history = min(configured, 50 % × effective_total)`; tiers allocate over `effective_total − series_history` for series novels, over the full `effective_total` for standalones — deliberate asymmetry (Decision 6; Axis 3 Option C) |

---

## Context

### The defect class

Runtime **input-context token budgets** live as code constants, bypassing the
SET-005 configuration cascade and ignoring the configured model's context
window. Probed evidence (file:line, 2026-08-15):

| # | Constant | Location | Problem |
|---|----------|----------|---------|
| 1 | `token_budget: int = 512` | `packages/core/narrare_core/context/series_history.py:165` (`SeriesHistoryTier.assemble` default) | Hardcoded; inconsistent with its own feature — the default recency window (3 full band summaries ≈ 1,200+ tokens) cannot fit; band 2 truncates, band 3+ silently drops |
| 2 | `_DEFAULT_TOKEN_BUDGET: int = 512` | `apps/api/narrare/series/series_history_provider.py:48` | Mirror of #1; the **only** value ever used in production — `apps/api/narrare/writing/_helpers.py:180` calls `assemble_series_history(novel_id)` with no budget → 512 applies |
| 3 | `DEFAULT_TOTAL_BUDGET: int = 6000` | `packages/core/narrare_core/context/budget.py:59` (`TokenBudgetManager`) | Writing 5-tier total hardcoded; `apps/api/narrare/writing/deps_pipeline.py:54` constructs `WritingContextAssembler(tier_overrides=…)` **without** `total_budget` → the 6000 class default silently applies on every writing path |
| 4 | `DEFAULT_TOTAL_BUDGET: int = 6000` | `packages/core/narrare_core/analysis/budget.py:33` (`AnalysisBudgetManager`) | Same class; sole consumer `apps/api/narrare/analysis/beta_reader_service.py:80` constructs `AnalysisContextAssembler()` with no budget → 6000 applies; the content tier (50 %) truncates at **3,000 tokens ≈ 2,300 words** — most chapters (3–5k words) are silently cut |

**Root cause (2× Why):**
1. *Symptom:* series history delivers ~1 band instead of the promised 3; writing/analysis contexts silently drop information.
2. *Why are the limits wrong?* They were authored as conservative code constants (pre-SET-005) and never adopted into the cascade when SET-005 was built — SET-005's cascade covers **output** limits, tier **percentages**, and consistency caps, but never the **input-context totals**.
3. *Why does that starve contexts?* Budgets are ceilings, not consumption mandates — but ceilings set far below content availability act as silent truncation. Modern model windows (128k…1M) make 512/6000 unjustifiable (design doc D6).

**Model-boundary gap (CR-08 P0):** output tokens are already model-boundary-capped
(`narrare_core/llm/run_limits.py:74–81`: `effective = min(requested, provider_max)`),
and suitability checks compare `required_input_tokens + minimum_floor` against
`context_window` (`narrare_core/llm/model_suitability.py:179`). But **input-context
budgets are never capped against the window** — an 8k-context local model fed a
6,500-token context plus ~1.7k system prompt plus output exceeds its window and
produces broken/failed requests. This is the "model-boundary/tier-budget adoption"
P0 item CURRENT_STATE lists as remaining.

### Empirical findings (probes, not doc-reasoning)

**F1 — Context-window data exists today.** Three independent, already-wired sources:

- `narrare_core/llm/model_listing.py:42` — `ModelCatalogEntry.context_window: int | None`, populated per provider from models.dev / Ollama `/api/tags` `details.context_length` / Anthropic `inputTokenLimit` / etc. (lines 250–371). Used by the setup UI.
- `narrare_core/llm/cost_rates.py:240` — `get_model_limits(provider, model_id) -> ModelLimits(context, output)`, models.dev-backed with a 24 h local cache (`~/.narrare/cache/models_cache.json`), stale-cache fallback, and typed offline status (`model_calibration.py:11–18`: `known_fresh / known_stale / unknown_model / offline_no_cache / invalid_metadata`).
- `apps/api/narrare/settings/token_limits/service.py:167` — `TokenLimitsService.get_model_limits` already delegates to the same accessor.

→ **No registry data-model extension is needed for D4.** The window source is
`get_model_limits` (calibration-wrapped). Gap handling (unknown model / offline
no cache) already has a typed vocabulary to reuse.

**F2 — The cascade shape (where the two budgets land).** SET-005 resolves
User-DB → Project-DB → Operator-Env → Code-defaults
(`apps/api/narrare/settings/token_limits/service.py:66–121`) into
`TokenLimitOverrides` (`…/token_limits/contracts.py:49`), stored as a **JSONB
`overrides` dict** (`…/token_limits/models.py:43,59` — new keys need **no DB
migration**; only the write-boundary allowlist `…/token_limits/_validators.py:23`
grows). The operator-env layer is `apps/api/narrare/_app/settings_model.py`
(`NARRARE_*` Fields, applied in `service.py:190–208`). Core-side defaults follow
the "derive from Core" precedent (`contracts.py:24`: `DEFAULT_TOKEN_PROFILE` is
imported from Core so backend and Core cannot drift).

**F3 — Sub-budget mechanics (D3).** `{{series_history}}` is assembled
**outside** the 5-tier system: the Backend provider builds the string
(`series_history_provider.py:120–124`) and passes it through the assembler
verbatim (`writing/context_assembler.py:145,331` — no tier accounting). The
5-tier percentages (30/20/25/15/10 base; mode variants) are user-configurable
via `tier_percentages` and must keep summing to 1.0 (validators, UI, FIND-012
`None`-sentinel semantics). Other pass-throughs (author/character voice,
`kb_relationships`, preferences, synopsis/style/logline) are likewise not
tier-budgeted today.

**F4 — Reserve components are measurable.** Auto-injected capability prompts
(ADR-026, every `NarrareAgent`): meta `en` 1,977 B, universal `en` 918 B
(`prompts/_bundled/meta|universal/en/system.md`; de slightly larger: 2,120 /
1,033 B); feature system prompt e.g. `writing/en/new_chapter/system.md`
3,568 B. Chars/4 (the codebase's own estimator, `series_history.py:50`):
≈ 494 + 230 + 892 ≈ **1,616 tok** system-side scaffolding; de ≈ 1,680.
Unbudgeted pass-through variables (F3) add empirically 0–2k; output tokens are
governed separately by `effective_output_limit` (default raw 4,096; balanced
preset 2,000 — `llm/token_profiles.py:48–53`).

**F5 — Analysis consumption (decision input for §3.3 of the design doc).**
Sole production consumer is the beta reader (`beta_reader_service.py:80`,
default budget). Content tier = 50 % × 6,000 = 3,000 tokens
(`analysis/assembler.py:112–114`) — `word × 1.3` counter
(`writing/_token_utils.py:15`) ⇒ ≈ 2,300 words before truncation. Analysis
inputs are whole chapters (same objects as writing's *immediate* tier), which
routinely exceed this. The defect is the same class as #3.

**F6 — Wiring points exist.** Every writing deps factory already resolves
limits per request (`deps_writing.py:78`, `deps_extend.py:60`,
`deps_rewrite.py:60`, `deps_coauthor.py:59`, `deps_style_variants.py:62`,
`summary_deps.py:70`, `router_sessions.py:112`) and threads
`tier_overrides` into `create_pipeline` (`deps_pipeline.py:24–54`). The
series-history call site is `_helpers.py:157–180`. Analysis wiring point is
`beta_reader_service.py:80`.

### Token-constant inventory (scope item 3)

Sweep: `rg 'token_budget|TOKEN_BUDGET|total_budget|TOTAL_BUDGET|context_window'`
over `packages/core` + `apps/api` (production code, 2026-08-15).

**(a) Lifted into the cascade / re-defaulted by this ADR — 4 constants:**

| Constant | Location | Disposition |
|----------|----------|-------------|
| `SeriesHistoryTier.assemble(token_budget=512)` default | `context/series_history.py:165` | → 16,000, sourced from new Core default constant; remains an explicit parameter (API passes the resolved value) |
| `_DEFAULT_TOKEN_BUDGET = 512` | `apps/api/…/series_history_provider.py:48` | → derived from the Core constant; production call site receives the resolved cascade value |
| `TokenBudgetManager.DEFAULT_TOTAL_BUDGET = 6000` | `context/budget.py:59` | → 32,000 + cascade key `context_total_budget` |
| `AnalysisBudgetManager.DEFAULT_TOTAL_BUDGET = 6000` | `analysis/budget.py:33` | → 32,000, shares `context_total_budget` (Decision 5) |

**(b) Legitimate Core-internal heuristics — stay (documented):** 8 constants

- `_CHARS_PER_TOKEN = 4`, `_MIN_TRUNCATE_TOKENS = 20` (`context/series_history.py:50,56`) — estimation/formatting heuristic, not a runtime limit (design doc §3.2.3 names this explicitly)
- `APPROX_TOKEN_FACTOR = 1.3` (`writing/_token_utils.py:15`) — estimator
- Writing tier-percentage tables incl. mode variants (`context/budget.py:69–99`) and analysis `_PERCENTAGES` (`analysis/budget.py:41`) — internal *distribution* defaults; the distribution is already cascade-overridable (`tier_percentages`); totals are the cascade concern
- `TOKEN_OUTPUT_ABSOLUTE_MAX`, `TOKEN_OUTPUT_UX_RECOMMENDED_MAX`, `PROFILE_OUTPUT_LIMITS`, `TOKEN_PROFILE_MINIMUM_OUTPUT_FLOORS`, `TOKEN_PROFILE_USAGE_LIMITS` (`llm/token_profiles.py`) — **output**-side profile vocabulary, governed by CR-08 P1; out of this ADR's input-budget scope
- `SUGGEST_MAX_TOKENS = 60` (`llm/run_limits.py:27`) — documented immutable UX-latency cap, deliberately not configurable
- `DEFAULT_CONTEXT_WINDOW` in `analysis/dialogue_parser.py` — characters of surrounding text for quote attribution, not a token limit despite the name

**(c) Already cascaded — verified, no change:** `max_chapter_tokens=2000`,
`max_kb_entries=100`, `max_selection_words=2000`, `ws_timeout=1800`,
`output_limit=4096` (`token_limits/contracts.py:58–97`); `context_window_size=3`
(`series_settings`, band **count** not tokens — C1's slider, different concern).

**(d) Data, not limits:** `setup/provider_service.py` catalog `context_window`
values and `model_listing.py` parsing — display/setup metadata; the D4 source
itself.

**Count: 4 lifted · 8 classified heuristic/stay · 5 verified cascaded · 2 new
constants introduced (below).**

---

## Decision Drivers

- **Binding design decisions D1–D6** (design doc §3.1): 16k series-history
  default; 32k writing-total default; 16k **within** 32k (not additive);
  `min(configured, window − reserve)` capping; **min() principle** (no
  auto-scaling up — cost footgun); budgets are ceilings, not mandates.
- **RULE-18b / ADR-045** — every configured value needs a
  source → resolver → runtime-consumer → enforcement-test chain.
- **RULE-07** — capping logic is pure arithmetic → Core; DB/env wiring → API.
- **RULE-03** — Protocol before implementation (new budget resolver module).
- **RULE-11** — unknown window must degrade gracefully (log + proceed), never
  block generation; mirrors `run_limits.py:80–81` `provider_max_unknown`.
- **RULE-14** — no DB migration expected (JSONB absorbs new keys); if one
  proves necessary, atomic up/down in the same task.
- **Local-first (ADR-029)** — 8k-window local models must get valid requests.

---

## Options Considered

### Axis 1 — Cascade surface for the two budgets

**Option A — new dedicated settings tables / router.** Rejected: invents a
parallel surface beside an existing stable one (SET-005 module, JSONB,
validators, three-layer resolver all exist); blast radius without benefit.

**Option B — CoreSettings (ADR-071) env-only fields.** Rejected as the *primary*
surface: CoreSettings is operator-env-only (no user/project layer); the design
doc requires SET-005 cascade semantics (D5: scaling up via *explicit user
configuration*). CoreSettings remains the pattern *reference*, not the vehicle.

**Option C — extend the existing SET-005 vocabulary (chosen).** Two new keys in
`TokenLimitOverrides` + validators + operator-env Fields. JSONB storage absorbs
them without migration; the whole resolver/UI/API machinery is reused; defaults
single-source from Core constants per the `DEFAULT_TOKEN_PROFILE` precedent.

### Axis 2 — Where capping lives

**Option A — API-layer capping inside `TokenLimitsService`.** Rejected: puts
model-window arithmetic (pure policy) into a DB-adjacent service; Core consumers
(CLI, tests) couldn't reuse it; contradicts the run-limits precedent where pure
resolution lives in Core (`llm/run_limits.py`).

**Option B — inside `TokenBudgetManager.allocate()`.** Rejected: the manager is
per-assembler and mode-aware; window capping is a cross-cutting, per-model
decision that must also bound series-history and analysis — embedding it there
couples allocation math to model metadata and would cap each consumer
inconsistently.

**Option C — a dedicated pure resolver in Core, injected with a window provider
(chosen).** Mirrors `DefaultRunLimitResolver` exactly: pure arithmetic over
inputs, `model_limits_provider` callable injectable (default
`get_model_limits`), fully unit-testable without I/O.

### Axis 3 — Sub-budget semantics for series-history (D3)

**Option A — make series-history a 6th tier of `TokenBudgetManager`.** Rejected:
the 5-tier vocabulary is a public SET-005 contract (stored user
`tier_percentages` sums, UI pie chart, validators, FIND-012 `None`-sentinel,
mode variants). A 6th key breaks every stored override and the UI contract.

**Option B — absolute carve-out: tier base = total − configured series-history
ceiling, unbounded share.** Rejected: degenerate on small windows (8k model →
effective total 6k → series-history ceiling min(16k, 6k) = 6k → tier base 0).

**Option C — guarded carve-out (chosen).** Series-history ceiling =
`min(configured, SERIES_HISTORY_MAX_SHARE × effective_total)` with
`SERIES_HISTORY_MAX_SHARE = 0.5`; the 5 tiers allocate over
`effective_total − series_history_ceiling` **when series history is in scope**
(series novel), over the full `effective_total` for standalone novels. The 50 %
guard structurally prevents the degenerate case (both sides always ≥ half) and
makes the defaults sit exactly at the guard boundary (16k = 50 % of 32k) —
consistent with the PO's chosen magnitudes.

### Axis 4 — Analysis budget (design doc §3.3 left open)

**Option A — keep 6,000.** Rejected: F5 shows the identical silent-truncation
defect (content tier cuts at ≈ 2,300 words); D6's rationale applies verbatim.

**Option B — separate `analysis_total_budget` cascade key.** Rejected: a second
knob with no user behind it; both assemblers consume the same kind of object
(whole chapters + KB + preferences); one mental model.

**Option C — analysis joins `context_total_budget` at 32,000 (chosen).** One
key, one capping path, same ceilings-not-mandates semantics. Evidence-based per
F5; the design doc delegated exactly this decision to this ADR.

---

## Decision

1. **Two new SET-005 cascade keys** (Option C, Axis 1):
   `context_total_budget: int = 32_000` and `series_history_budget: int = 16_000`
   on `TokenLimitOverrides`; added to `VALID_OVERRIDE_FIELDS`
   (`_validators.py:23`) with `ge=1_024`-style sanity bounds at the write
   boundary; operator-env Fields `NARRARE_CONTEXT_TOTAL_BUDGET` /
   `NARRARE_SERIES_HISTORY_BUDGET` in `settings_model.py`, applied in
   `_apply_env_layer`. **No DB migration** (JSONB). No new UI in C5 (design doc
   §11: expert-invisible; C1's slider preview is the visible surface). The
   existing token-limits PATCH API thereby becomes the user-configuration
   surface D5 requires.

2. **Core defaults, single-sourced:** `TokenBudgetManager.DEFAULT_TOTAL_BUDGET`
   6,000 → **32,000** (`context/budget.py`); new
   `DEFAULT_SERIES_HISTORY_BUDGET = 16_000` exported from
   `narrare_core/context/budget.py`; `AnalysisBudgetManager.DEFAULT_TOTAL_BUDGET`
   6,000 → **32,000** (references the same Core constant, not a third literal);
   `SeriesHistoryTier.assemble` default 512 → **16,000** (parameter stays
   explicit; API always passes the resolved value); provider
   `_DEFAULT_TOKEN_BUDGET` derives from the Core constant. API-side defaults
   import these constants (no drift possible, `DEFAULT_TOKEN_PROFILE`
   precedent).

3. **Model-boundary capping (D4) — pure resolver in Core (Option C, Axis 2):**
   new `narrare_core/context/budget_resolver.py` + Protocol in
   `narrare_core/context/contracts.py` (RULE-03 sketch below). Window source:
   `get_model_limit_calibration` (F1 — exists today, typed offline statuses).
   Arithmetic:

   ```
   reserve        = min(RESERVE_FIXED + effective_output_limit, window // 4)
   effective_total = min(configured_total, window − reserve)        if window known
                   = configured_total                                if unknown
   series_history  = min(configured_sh, floor(0.5 × effective_total))  # in-scope only
   tier_base       = effective_total − series_history_ceiling          # series novel
                   = effective_total                                   # standalone
   ```

   Unknown window (unknown model / offline no cache): **no capping**, proceed
   with configured value, log warning + `source="…:window_unknown"` tag —
   RULE-11, mirroring `provider_max_unknown`. Same rule applies per consumer
   (writing model window for writing; analysis model window for analysis).

   > **Clarification (2026-08-15, C5 plan):** the window source is `get_model_limits` (`narrare_core.llm.cost_rates`) — the `ModelLimits | None` wrapper mirroring `DefaultRunLimitResolver`, as the Contract Sketch and resolver Protocol specify; the `get_model_limit_calibration` naming above is superseded.

4. **Reserve definition (derivation, F4):** the reserve covers
   (i) auto-injected meta + universal capabilities (≈ 500 + 250 tok),
   (ii) the feature system prompt (≈ 900 tok),
   (iii) unbudgeted pass-through variables (voice blocks, relationships,
   preferences, synopsis/style/logline — F3; budgeted ≈ 1,350 tok),
   (iv) output headroom = the already-resolved `effective_output_limit`
   (dynamic: default 4,096; preset-dependent).
   Fixed component (i)+(ii)+(iii) ≈ 3,000 → **`RESERVE_FIXED = 4_000`**
   (headroom-rounded). Default total reserve ≈ 4,000 + 4,096 ≈ **8,100 tok**.
   The `window // 4` guard prevents small-window collapse: an 8k local model
   gets reserve 2,000 → effective total 6,000 (≈ today's working set, now
   actually window-valid — today's 6.5k context + system + output never fit an
   8k window). A 128k model: reserve 8,096 → cap 119,904 → full 32,000 applies.

5. **Analysis budget (Axis 4):** `AnalysisBudgetManager` total = resolved
   `context_total_budget` (default 32,000), capped by the **analysis** model's
   window via the same resolver. `beta_reader_service` wiring receives the
   resolved value (`beta_reader_service.py:80` construction point).

6. **Sub-budget semantics (D3, Axis 3 Option C):** series-history is a guarded
   carve-out, not a 6th tier. Tiers keep their 5-key percentage contract and
   mode variants untouched; they allocate over `tier_base`. Containment is
   structural: `series_history + tier ceilings ≤ effective_total` always holds;
   the 50 % guard makes defaults exact (16k of 32k) and small windows fair
   (8k model: ≤3k series-history, ≥3k tiers).

7. **Default break — intentional, migration-free:** 512→16k and 6000→32k are
   documented behavior breaks (design doc §3.3: regression tests deliberately
   rewritten). No Alembic migration: defaults are code constants; the JSONB
   override store cannot hold pre-existing keys for values that had no cascade
   key; stored overrides for *other* keys (tier percentages, output limits)
   apply unchanged on top of the new totals. Existing user `tier_percentages`
   now distribute 32k instead of 6k — intended (D6).

8. **CR-08 P0 closure mapping:** this ADR delivers the P0 "model-boundary/
   tier-budget adoption" remainder — tier budgets (a) enter the cascade
   (Decisions 1–2: storage → resolver → runtime consumer chain) and (b) adopt
   the model boundary (Decision 3: input-side capping, completing what
   `run_limits.py` did for the output side). RULE-18b evidence = per-value
   regression tests (Implementation checklist) + resolver unit tests.

9. **Estimator stance:** token *counting* stays heuristic (`chars/4`,
   `words × 1.3`). Budgets are ceilings with reserve headroom; estimator
   variance (±20–25 %) is absorbed by the reserve, not by a tiktoken dependency.
   Revisit only via Review Trigger.

---

## Rationale

1. **Symptom:** series history delivers a third of its promise; writing/analysis
   contexts truncate silently.
2. **Why fix via cascade + capping, not a constant bump?** A 2048-style bump
   (rejected mid-session, design doc §10) repeats the root-cause violation: the
   value would still bypass configuration and still ignore the model boundary.
3. **Why these magnitudes?** Ceilings don't consume — tiers fill by content
   availability (D6). 16k ≈ 13 full band summaries at realistic sizes; 32k
   absorbs a full chapter + KB + history without dropping information, and fits
   any 128k model with reserve (40k total commitment).
4. **Why min() and not auto-scaling?** Auto-upscaling against paid APIs is a
   cost footgun; the system cannot know a deployment is local/free (D5). The
   resolver only ever caps **down**.
5. **Why guarded carve-out?** D3 demands non-additivity; a 6th tier breaks the
   public 5-tier contract; an unguarded carve-out collapses on small windows.
   The 50 % guard is the simplest rule that is structurally non-additive,
   non-degenerate, and matches the chosen defaults exactly.

Simplest *correct* solution: two cascade keys, one pure resolver (~60 LOC
arithmetic), zero migrations, zero UI, existing wiring points.

---

## Consequences

**Positive:**

- Series history delivers its configured recency window by default; writing and
  analysis stop dropping information on typical content sizes.
- Every input budget is user/operator-configurable with the proven SET-005
  machinery; CR-08 P0 closes with RULE-18b evidence.
- 8k-window local models receive valid requests (capping + reserve) — first
  time input side is window-aware.
- C1's slider preview gets honest effective budgets to compute against
  (`min(configured, window − reserve)` results), as design §4 requires.

**Negative / Trade-offs:**

- **Intentional default break** — requests against paid APIs can grow ~5×
  input-side (6k→32k ceiling; actual growth bounded by content availability).
  Mitigated by D5 (explicit config to go higher) and by ceilings-not-mandates.
- **Estimator-based capping** — reserve absorbs counting variance, but exact
  token accounting is still approximate (accepted; tiktoken is a Review
  Trigger, not a dependency).
- **Series-history ceiling may cap below configuration on small windows**
  (8k model → 3k) — honest behavior, surfaced by C1's preview.
- **Standalone novels and series novels get different tier bases** (32k vs
  16k at defaults) — deliberate (nothing to carve when no series history
  exists); must be stated plainly in C1's preview copy.
- models.dev is the window source → offline-first-run with no cache means no
  capping until first fetch (logged, RULE-11; same exposure as existing
  pricing/calibration features).

**Constraints introduced / touched:** RULE-03 (new Protocol first), RULE-07
(resolver pure in Core, wiring in API), RULE-11 (unknown-window degradation),
RULE-18b (per-value regression chains), RULE-20 (no half-implementation: keys,
resolver, wiring, and tests land together).

---

## Contract Sketches (RULE-03 — full definitions at implementation kickoff)

> Home: `packages/core/narrare_core/context/contracts.py` (Protocol + result
> model) and `packages/core/narrare_core/context/budget_resolver.py`
> (implementation). Pure Core — no I/O; the window provider callable is
> injected (default `get_model_limits`), exactly as
> `DefaultRunLimitResolver` injects `model_limits_provider`
> (`llm/run_limits.py:55–60`).

```python
class EffectiveContextBudgets(BaseModel):
    """Resolved, model-boundary-capped input-context budgets (frozen)."""
    model_config = ConfigDict(frozen=True)

    context_total: int                # effective writing/analysis total (D2/D4)
    series_history: int               # effective series-history ceiling (D1/D3)
    writing_tier_base: int            # total − series_history (series novels) or total
    reserve_tokens: int | None        # reserve actually applied (None = window unknown)
    context_window: int | None        # window used for capping (None = unknown)
    source: str                       # provenance, e.g. "cascade:capped_to_window",
                                      # "cascade:window_unknown", "cascade:uncapped"


class ContextBudgetResolver(Protocol):
    """Resolve configured context budgets against the model boundary (D4)."""

    def resolve(
        self,
        *,
        configured_total: int,          # from TokenLimitsService (cascade)
        configured_series_history: int, # from TokenLimitsService (cascade)
        effective_output_limit: int,    # from ResolvedRunLimits / token_profiles
        series_in_scope: bool,          # novel is a series band (provider knows)
        provider_name: str,
        model_id: str,
    ) -> EffectiveContextBudgets: ...
```

Constants (Core, `context/budget.py`): `DEFAULT_TOTAL_BUDGET = 32_000`,
`DEFAULT_SERIES_HISTORY_BUDGET = 16_000`, `RESERVE_FIXED = 4_000`,
`SERIES_HISTORY_MAX_SHARE = 0.5`.

API wiring (indicative; finalized in the C5 implementation plan):
`token_limits/contracts.py` (+2 fields), `_validators.py` (+2 keys),
`_app/settings_model.py` (+2 Fields), `service.py::_apply_env_layer`,
`writing/deps_pipeline.py::create_pipeline` (+`total_budget` param),
`writing/_helpers.py::fetch_series_history` (+resolved ceiling),
`analysis/beta_reader_service.py` (+resolved total).

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | `ContextBudgetResolver` Protocol + `EffectiveContextBudgets` sketched here; defined in `context/contracts.py` before implementation. |
| RULE-04 | ✅ | Resolver is its own module (`budget_resolver.py`); budget arithmetic separated from allocation (`budget.py`) and wiring (deps). |
| RULE-05 | ✅ | Core owns policy (constants, resolver); API owns storage/env wiring. |
| RULE-06 | ✅ | Resolver file = one responsibility (resolution arithmetic); no router logic touched. |
| RULE-07 | ✅ | Pure Core resolver, zero `apps/` imports; window provider injected; DB/env wiring stays in `apps/api/narrare/settings/`. Dependency direction one-way. |
| RULE-09 | ✅ | Fully annotated Protocol + frozen Pydantic result model. |
| RULE-10 | ✅ | Resolver unit tests (capping arithmetic, unknown window, degenerate windows, containment) + rewritten default regressions + cascade resolution tests. |
| RULE-11 | ✅ | Unknown window → no capping, logged warning, source-tagged (mirrors `provider_max_unknown`). |
| RULE-14 | ✅ | No migration expected (JSONB absorbs keys). If one proves needed: atomic up/down in the same task. |
| RULE-18b | ✅ | Per-value chains: `context_total_budget` and `series_history_budget` each get storage → resolver → runtime-consumer → enforcement-test evidence (ADR-045 pattern). |
| RULE-20 | ✅ | Keys + resolver + all wiring points + tests land as one coherent slice; no "resolver later". |
| RULE-21 | ✅ | This ADR is the architecture review; deviations (new tier keys, auto-scaling, tiktoken) require re-review. |
| RULE-22 | ✅ | Reads only existing settings/model-metadata owners (TokenLimitsService, cost_rates); no source modification. |
| RULE-01b/02/02b/13 | N/A | No LLM client, prompt, or streaming concern — pure budget policy. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes — magnitudes are ceilings against content
   availability, not hardcoded consumption; the guard rails (50 % share,
   window//4 reserve scaling) prevent both degenerate configs and small-window
   collapse. Window data refreshes via the existing models.dev cache.
2. **Hard-to-undo coupling?** Low. Two JSONB keys (additive vocabulary, unknown
   keys already tolerated by the resolver); one pure resolver behind a Protocol
   (swap the window source = swap the injected callable); no UI to unwind.
3. **Simplest correct solution?** Yes — reuses SET-005 end-to-end; the
   rejected alternatives each either break public contracts (6th tier), create
   parallel surfaces (new tables), or repeat the root cause (constant bump /
   API-layer capping).
4. **Design intent clear?** Yes — D1–D6 mapped 1:1 to Decisions 1–6; reserve
   derivation from measured prompt sizes recorded; inventory dispositions
   explicit.

---

## Implementation Notes

- **Slice order (per implementation plan):** (1) Core constants + resolver +
  unit tests; (2) cascade keys (contracts/validators/env/service) + resolution
  tests; (3) wiring (deps_pipeline, _helpers, beta_reader) + rewritten default
  regressions. Contract files are authored first and marked untouchable for the
  remainder of the slice (RULE-03 discipline).
- **Tests deliberately rewritten** (design §3.3): every 512→16,000 and
  6,000→32,000 assertion; new resolver tests for: default no-cap case
  (128k window), 8k-window capping (6,000 total, ≤3,000 series-history),
  unknown-window passthrough + source tag, reserve = min(fixed+output, w//4)
  boundary, containment invariant (`series_history + tier_base == total`).
- **`check_architecture.py`:** no checker relaxation; the new module follows
  existing import-direction rules automatically.
- **C1 dependency:** the slider preview (design §4) consumes
  `EffectiveContextBudgets` verbatim — same resolver, no second computation
  path. Standalone-vs-series tier-base difference must be reflected in preview
  copy.
- **Docs at implementation time:** SET-005 feature spec (new keys + CR-08 P0
  closure note), CURRENT_STATE item 13 update, TECH_STACK unchanged (no new
  dependency).

**ADR Implementation Completeness Gate:** "✅ Implemented" requires: resolver +
tests green, both cascade keys end-to-end (storage → API → runtime consumer →
enforcement test), all four lifted constants re-defaulted with rewritten
regressions, inventory table above reflected in code comments where a constant
was classified heuristic/stay, CR-08 P0 closure recorded in CURRENT_STATE.

---

## Review Trigger

- [ ] When a **true token counter** (tiktoken or equivalent) is adopted —
      re-derive `RESERVE_FIXED` and the estimator stance (Decision 9).
- [ ] When **output presets** change materially (e.g. default output_limit
      moves far from 4,096) — reserve arithmetic auto-follows, but re-check
      small-window behavior.
- [ ] When a **6th context tier** or new pass-through variable class is added —
      re-measure reserve components (F4) and revisit the 50 % share guard.
- [ ] When **models.dev** becomes unavailable long-term or a bundled window
      dataset is considered — the injected provider callable is the swap seam.
- [ ] When **auto-scaling** is ever reconsidered — requires superseding D5
      (this ADR + design doc §3.1); not a configuration change but a policy
      reversal.
- [ ] When **multi-window model aliases** (per-intent windows) appear in the
      registry — resolver already takes provider+model per call; verify
      call sites pass the *effective* model per intent.
