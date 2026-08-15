# ADR-078 — Series Voice Hierarchy (SERIES-003 — Spec 3: Delta Model + Opt-out)

> **Status:** ✅ Implemented (implemented 2026-08-05 across Core → Backend → Frontend
> in 6 task slices; coordinator commit pending — see
> `.superpowers/sdd/2026-07-29-series-foundation/spec3-task-*-report.md`. Originally
> Accepted 2026-08-05 — the design spec
> (`docs/superpowers/specs/2026-08-02-series-voice-hierarchy-design.md`) was finalised
> after a brainstorming session and the coordinator directed implementation to proceed.)
> **Date:** 2026-08-05
> **Deciders:** Architecture Specialist; User (approved the Delta model + opt-out design
> synthesised from the brainstorming session)
> **Supersedes:** —
> **Related:**
> ADR-074 (Author Voice Storage — the **predecessor** whose Review Trigger Voice-Teil
> this ADR closes: storage was closed by ADR-075, the voice resolution model is closed
> here),
> ADR-075 (Series Foundation — added the empty `SeriesSettings.author_voice` sibling
> home this ADR populates; its Review Trigger Spec-3 item is closed here),
> ADR-077 (Series Generation Context — Spec 2; the series-history + KB-Redirect tier
> this ADR's voice tier sits alongside at generation time),
> ADR-069 (`AdaptiveSettings` JSONB pattern — the persistence shape
> `SeriesSettings.author_voice` mirrors),
> ADR-055/057 (descriptive/metric boundary — preserved by construction in the Delta
> renderer),
> CONSTRAINTS.md RULE-02/02b/03/04/05/06/07/11/14/17/22,
> CR-04 (cross-feature coherence — the voice consumer is shared data)

> **Scope of this ADR:** the **Series Voice Hierarchy** — the voice resolution model
> for a novel that belongs to a series, the auto-profile-from-band source, the
> per-novel opt-out, the `{{author_voice}}` extension (no new prompt variable), and
> the `AuthorVoiceConsumer` Delta composition. Series **Cross-Novel Drift** (Spec 4)
> is **downstream program work** (implemented), flagged here but
> not designed here. **Spec 5 (Series Export) was retired 2026-08-14 as YAGNI**
> (PO decision; see `docs/superpowers/specs/2026-08-14-post-export-followups-design.md` §2).

---

## Context

### Why this ADR exists

ADR-074 deliberately scoped author-voice storage at the **novel** level and carried
the Series voice question as a Review Trigger:

> *"When the Series / Reihe feature is designed — revisit the voice resolution model
> …; add the sibling `SeriesSettings.author_voice` home …"* — ADR-074 Review Trigger

ADR-075 (Spec 1) added the sibling `SeriesSettings.author_voice` JSONB column
**empty** (forward-compat) and closed the **storage** portion of that trigger. The
**Voice-Teil** — the actual resolution model (override / blend / cascade / delta),
the population of the empty column, and the per-novel policy — remained open for
Spec 3. **This ADR is Spec 3.** It closes the Voice-Teil of ADR-074's Review Trigger
and the Spec-3 item of ADR-075's Review Trigger.

### Verified state (grounded, not assumed — per architectural-discipline §7)

| Concern | State | Location |
|---------|-------|----------|
| `SeriesSettings.author_voice` column | EXISTS — added empty in Spec 1 (ADR-075 / migration `0037`). **Populated by this ADR.** | `apps/api/narrare/series/models.py`, `packages/core/narrare_core/series/schemas.py` |
| Novel-level `ProjectSettings.author_voice` | EXISTS — ADR-074; the novel-scoped profile the Delta model treats as the additive layer. | `apps/api/narrare/settings/models.py` |
| `AuthorVoiceProfile` + `AuthorMetrics` | EXISTS — ADR-074; voice-generic `VoiceAnalysis`/`VoiceMetrics` reused. THE profile shape both the novel and the series voice share. | `packages/core/narrare_core/profiles/author_voice.py` |
| `AuthorVoiceAgent` (hybrid pipeline) | EXISTS — ANAL-007; the governed agent this ADR **reuses** (no new agent). | `packages/core/narrare_core/agents/author_voice_agent.py`, `apps/api/narrare/analysis/author_voice_service.py` |
| `render_author_voice_for_generation` | EXISTS — the descriptive-only renderer (ADR-074 binding: metrics never reach generation). This ADR composes it twice (once per profile) rather than duplicating it. | `packages/core/narrare_core/profiles/author_voice.py` |
| `{{author_voice}}` generation variable | EXISTS — ADR-074; a governed SYSTEM_VAR. This ADR **extends its content**, no new variable. | `packages/core/narrare_core/prompts/variable_registry.py` |
| `AuthorVoiceConsumer` | EXISTS — ADR-074; the generation consumer that renders the descriptive group. This ADR extends its `assemble()` to read series voice + opt-out. | `packages/core/narrare_core/profiles/author_voice_consumer.py` |
| Per-novel opt-out flag | **DID NOT EXIST before this ADR** — `ProjectSettings.use_series_voice` added (migration `0039`). | `apps/api/narrare/settings/models.py`, migration `0039_series_voice` |
| `Volume` ≠ `Series` | Confirmed (ADR-074 / ADR-075) — Volume is intra-novel; Series is inter-novel. | — |

### Program-level position

This is **Spec 3 of 5** in the Series program:

| # | Spec | Status |
|---|------|--------|
| 1 | Series Foundation + KB Evolution (ADR-075) | ✅ Implemented |
| 2 | Series Generation Context (ADR-077) | ✅ Implemented |
| **3** | **Series Voice Hierarchy (this ADR)** | **✅ Implemented** |
| 4 | Series Cross-Novel Drift | Downstream |
| 5 | Series Export | Downstream |

---

## Decision Drivers

- **RULE-02/02b** — No prompt assembly in services; no new prompt variable. The
  Delta composition lives in a pure Core renderer; the `{{author_voice}}` variable
  is extended, not replaced.
- **RULE-03** — `SeriesVoiceServiceProtocol` (Core contract) MUST exist before the
  service. The Delta renderer is a pure function with a typed contract.
- **RULE-04/06** — Modularise; one responsibility per file. The voice service,
  contracts, schemas, router, and the Delta renderer each get their own file.
- **RULE-05/07** — Core owns the Delta renderer (`profiles/author_voice.py`) and
  the consumer extension; Backend owns the service + migration; no `core/`→`apps/`
  imports; dependency direction `router → service → repository → DB`.
- **RULE-11** — Graceful degradation: a standalone novel, an opted-out novel, a
  series with no voice, or a novel with no profile all degrade to the legacy
  novel-only render (or empty). No crash, no silent prompt regression.
- **RULE-14** — The `ProjectSettings.use_series_voice` column lands with its
  Alembic migration (`0039_series_voice`) in the same task (a model change without
  a migration is a build failure).
- **RULE-17** — Frontend/back-end type parity: the TS `SeriesVoiceProfile` mirror
  preserves snake_case; `use_series_voice` is a boolean on both sides.
- **RULE-22 / CR-04** — The voice consumer is shared data (read by generation).
  The Delta model is defined together with its consumer impact; the descriptive/
  metric boundary (ADR-055/057) is preserved by construction.
- **ADR-074** — The novel-level home remains the primary scope (no forced
  cascade); the series voice is an additive sibling, exactly as ADR-074's
  Forward-compatibility analysis specified.
- **architectural-discipline §1/§4/§7** — Root-cause solution; no workarounds;
  "documented ≠ implemented" — the migration + modules + renderer + tests must
  actually land.

---

## Options Considered

### Decision 1 — Voice resolution model

| Option | Model | Verdict |
|--------|-------|---------|
| **Override** | novel voice replaces series voice (or vice-versa) | **Rejected** — loses series consistency when a novel has its own profile. |
| **Blend** | weighted combination (e.g. "70% formal + 30% colloquial") | **Rejected** — ill-defined for LLM prompts (what does a percentage of a prose style mean as text?). |
| **Cascade** | series → novel fallback chain (forced) | **Rejected** — triggers the Cascade-Fallback-Kritik documented in ADR-074: a standalone written in a deliberately different voice would inherit the author's "usual" patterns — the opposite of what the writer wants. Forced cascade is harmful. |
| **Delta** *(CHOSEN)* | series voice as foundation, novel voice additive, per-novel opt-out | **Chosen** — additive, natural for LLMs, respects opt-out. The prompt says *"Series voice is X. Additionally, this novel has Y."* — the LLM processes both organically. |

### Decision 2 — Series voice source

| Option | Source | Verdict |
|--------|--------|---------|
| **Manual only** | the author writes the series voice by hand | **Rejected** — high friction; most authors will not hand-author a structured voice profile. |
| **Aggregate all bands** | profile every band and merge | **Rejected (YAGNI)** — Spec 4 (Cross-Novel Drift) is the right home for cross-band voice analysis; aggregating now is speculative. |
| **Auto-profile from one band + manual override** *(CHOSEN)* | run the existing `AuthorVoiceAgent` on one selected band; the author can override | **Chosen** — same pattern as `BandSummary` in Spec 2 (ADR-077). Reuses the existing agent; one click to profile, one editor to override. |

### Decision 3 — Opt-out mechanism

| Option | Mechanism | Verdict |
|--------|-----------|---------|
| **Series-global** | a series is either "voice-on" or "voice-off" for all its novels | **Rejected** — too coarse; a series may have one experimental band that should not inherit the series voice. |
| **Per-novel toggle** *(CHOSEN)* | `ProjectSettings.use_series_voice: bool = True` | **Chosen** — default True (every series novel inherits the series voice as base); set False to make a specific novel ignore the series voice and use only its own. Matches the user's domain observation ("standalones vary, series share voice" — but a series author may still want one band to deviate). |

### Decision 4 — Prompt integration

| Option | Surface | Verdict |
|--------|---------|---------|
| **New variable `{{series_voice}}`** | a second generation variable alongside `{{author_voice}}` | **Rejected** — fragments the voice surface; the generation consumer would have to know to render both and the model would see two disconnected voice blocks. |
| **Extend `{{author_voice}}`** *(CHOSEN)* | one variable; its content changes based on context | **Chosen** — one voice surface, composed by the consumer. The model sees a single, coherent voice block whose framing adapts: standalone / series+novel / series-only / opt-out / empty. No new prompt-surface registration, no new route, no manifest change (RULE-22). |

---

## Decision

**Delta + Auto-profile-from-band + Per-novel opt-out + Extend `{{author_voice}}`.**

- **Resolution model — Delta.** The series voice is the **foundation**; the novel's
  own voice is **additive**. The pure Core renderer
  `render_author_voice_delta()` composes the existing descriptive-only renderer
  once per profile and emits:
  - **Series + Novel voice** → `"Series voice:\n{series}\n\nNovel nuances:\n{novel}"`
  - **Series only (no novel voice)** → `"Series voice:\n{series}"`
  - **Standalone / opt-out / no series voice** → novel-only render (byte-identical
    to the legacy renderer — backward-compatibility guarantee)
  - **No profiles** → `""` (graceful degradation)
- **Source — auto-profile from one band + manual override.** `SeriesVoiceService`
  runs the existing `AuthorVoiceAgent` pipeline over one selected band's full
  chapter prose and stores the assembled `AuthorVoiceProfile` as
  `SeriesSettings.author_voice`. The author can override (PATCH) or clear
  (DELETE) it. **No new agent** (RULE-01b).
- **Opt-out — `ProjectSettings.use_series_voice: bool = True`.** A new NOT NULL
  column (migration `0039`, server_default `true` so existing rows backfill).
  Default True = every series novel inherits the series voice; False = the novel
  ignores the series voice and uses only its own profile.
- **Prompt surface — extend `{{author_voice}}`.** No new variable, no new route,
  no manifest change. The `AuthorVoiceConsumer.assemble()` reads the novel's
  series membership + opt-out flag + both profiles, delegates to the pure Delta
  renderer, and returns the composed string.

---

## Rationale

The Delta model is the architecturally honest answer to "how do two voice profiles
combine in an LLM prompt?" Voice is **prose-level descriptive text**, not a vector —
it cannot be meaningfully blended by weight (Decision 1 — Blend rejected). The LLM
already understands additive framing ("here is the baseline; here is what's
different in this case"), so the Delta composes naturally without inventing a new
modality. This mirrors how a human series editor thinks: "the series sounds like X;
this book leans a bit more Y."

Auto-profile-from-band (Decision 2) is the **proportionality** choice: it reuses
the existing `AuthorVoiceAgent` (no new agent, no new governed template, no new
prompt-surface registration) and mirrors the proven `BandSummary` pattern from
Spec 2. One band's prose is a sufficient signal for the series' foundational voice;
cross-band aggregation is genuinely Spec 4's concern (drift), not Spec 3's
(foundation).

The per-novel opt-out (Decision 3) is what distinguishes Delta from Cascade.
Cascade (rejected) *forces* the series voice onto every band; Delta *offers* it,
defaulting on but allowing a novel to opt out. This respects the ADR-074
Cascade-Fallback-Kritik: an experimental band is not silently overwritten by the
series' usual patterns.

Extending `{{author_voice}}` (Decision 4) keeps one coherent voice surface. The
generation consumer already renders the descriptive group; the Delta composition
is a pure function over two profiles, so the consumer's contract is unchanged in
shape — only its input widened (series profile + opt-out flag).

### Sustainability check

1. **Correct in 3 months?** Yes — every later spec (Drift, Export) extends an
   additive foundation; none requires undoing Spec-3 work. The Delta renderer is
   pure and tested; the opt-out is a boolean.
2. **Hard-to-undo coupling?** Minimal — one additive column (`use_series_voice`)
   with a server_default, one pure renderer, one service that reuses an existing
   agent. A standalone novel sees no series voice (byte-identical to legacy).
3. **Simplest correct solution?** Yes — no new agent, no new prompt variable, no
   new route in the prompt-surface manifest. The cost is one column + one renderer
   + one service.
4. **Design intent clear?** Yes — `render_author_voice_delta`,
   `SeriesVoiceService`, `series_voice_contracts.py`, `router_voice.py` each name
   their single responsibility.

---

## Consequences

**Positive:**

- **Closes ADR-074's Review Trigger Voice-Teil** (FULLY CLOSED: storage by
  ADR-075, voice resolution model by this ADR) and **ADR-075's Spec-3 Review
  Trigger item**.
- **One coherent voice surface.** `{{author_voice}}` adapts its framing to
  context; no second variable to register, route, or document.
- **No new agent.** Reuses `AuthorVoiceAgent` (RULE-01b) — the governed template,
  the evidence attribution, and the descriptive/metric boundary are inherited
  unchanged.
- **Additive, backward-compatible migration.** `use_series_voice` is NOT NULL
  with `server_default=true`; existing rows backfill to True (the Delta default).
  Standalone novels are byte-identical to the legacy renderer.
- **Per-novel control.** The opt-out respects the "one experimental band"
  use-case without forcing a series-global policy.
- **Descriptive/metric boundary preserved by construction.** The Delta renderer
  composes the descriptive-only renderer; neither `voice_metrics` nor
  `author_metrics` from either profile can reach the output (ADR-055/057).

**Negative / Tradeoffs:**

- One Alembic migration (RULE-14) — accepted, standard cost, mirrors `0033`/`0038`.
- The `POST …/voice/profile` endpoint is **synchronous** (one blocking LLM call),
  not SSE like the novel-level author-voice endpoint. This matches the
  band-summary precedent and the task design; a progressive-feedback SSE variant
  can be added later (the underlying pipeline is stream-capable).
- **Provenance ambiguity:** auto-profile and manual override share the single
  `SeriesSettings.author_voice` column. The frontend status badge
  (`autoProfiled` vs `overrideActive`) is therefore optimistic on reload — any
  non-null voice reads as `autoProfiled` until a PATCH transiently flips it. A
  persisted provenance flag would require a backend schema change; out of scope
  for Spec 3 (documented in `SeriesVoicePanel`).
- `feature_id` attribution for the profiling call reuses
  `analysis_author_voice` (the invocation evidence literally runs that pipeline).
  A small future refactor could parameterise `feature_id`.

**Constraints introduced:**

- The Delta composition MUST go through `render_author_voice_delta` (the pure
  renderer) — the analogue of ADR-050's "no SSOT bypass". Services must not
  hand-compose the `"Series voice:\n…"` string.
- A series novel's generation consumer MUST consult `use_series_voice` before
  reading the series profile — the opt-out is binding, not advisory.
- The Delta renderer MUST preserve the descriptive/metric boundary: it composes
  the descriptive-only renderer and never touches the metric groups.

---

## CR-04 Cross-Feature Impact (coherence)

The voice consumer is **shared data** — written by the series-voice profiling
service AND the novel-level author-voice service, read by generation. This ADR
requires coherence end-to-end, not feature-local:

- **Producer (series voice).** `SeriesVoiceService.profile_from_novel()` runs the
  existing `AuthorVoiceAgent` pipeline (reusing the factored module-level helpers
  from `author_voice_service.py` — steps 1–6 verbatim; only the storage target
  differs) and writes `SeriesSettings.author_voice` via
  `SeriesRepository.update_settings` (RULE-07: no raw column access).
- **Producer (novel voice).** The existing `AuthorVoiceService.analyze()` writes
  `ProjectSettings.author_voice` — unchanged by this ADR.
- **Consumer (generation).** `AuthorVoiceConsumer.assemble()` reads the novel's
  series membership + `use_series_voice` flag + both profiles, delegates to the
  pure `render_author_voice_delta()`, and returns the composed `{{author_voice}}`
  string. The descriptive/metric boundary is preserved by construction.

This is the CR-04 lesson (architectural-discipline §7): producer + consumer are
defined together. Because the Delta renderer is a **pure composition** over the
existing descriptive-only renderer, the cross-feature surface is **additive** —
no existing consumer sees a series voice unless the novel is in a series, opted-in,
and the series has a profile — but the composition contract is fixed **here**, so
the generation consumer cannot accidentally render metrics or ignore the opt-out.

---

## Retrofit-Plan

> Implementation is complete (6 task slices). This section records what was built
> and where, per architectural-discipline §7 (documented = implemented).

### 1. Inventory of affected paths

**Core (implemented)** — `packages/core/narrare_core/profiles/author_voice.py`:
- `render_author_voice_delta(novel_profile, series_profile, *, use_series_voice=True,
  series_id=None)` — the pure Delta renderer. Composes
  `render_author_voice_for_generation` once per profile; byte-identical to legacy
  for standalone/opt-out.

**Core (implemented)** — `packages/core/narrare_core/profiles/author_voice_consumer.py`:
- `AuthorVoiceConsumer.assemble()` extended: reads `series_id` + `use_series_voice`
  + both profiles, delegates to `render_author_voice_delta`. The consumer
  signature widens (opt-out flag + series profile); the output contract
  (descriptive-only string) is unchanged.

**Backend (implemented)** — `apps/api/narrare/series/`:
- `series_voice_contracts.py` — `SeriesVoiceServiceProtocol` (RULE-03; 147 lines).
- `series_voice_service.py` — `SeriesVoiceService` (292 lines, < 300 limit):
  `profile_from_novel` / `get` / `update_override` / `clear_override`. Ownership
  verified internally (anti-enumeration C1, mirrors `SeriesService`).
- `series_voice_schemas.py` — request/response DTOs (81 lines; split from
  `schemas.py` which was at 196/200 — RULE-04).
- `router_voice.py` — thin router, 4 endpoints (97 lines, < 150 limit).
- `dependencies_voice.py` — `get_series_voice_service` DI factory.

**Backend (implemented)** — `apps/api/narrare/settings/`:
- `models.py` — `use_series_voice: Mapped[bool]` (NOT NULL, `server_default=true`).
- `schemas.py` — `use_series_voice` on `UpdateProjectSettingsRequest` +
  `ProjectSettingsResponse` (the opt-out toggle).

**Backend (implemented)** — `apps/api/narrare/_app/main.py`:
- `series_voice_router` wired.

**Alembic (implemented)** — `apps/api/alembic/versions/0039_series_voice.py`:
- atomic `upgrade()` + `downgrade()` (RULE-14). `down_revision = 0038_band_summaries`.

**Frontend (implemented)** — `packages/web/`:
- `types/series.ts` — `SeriesVoiceProfile`, `SeriesVoice`, `SeriesVoiceState`,
  `SeriesVoiceOverrideRequest` (snake_case, RULE-17 parity; descriptive/metric
  boundary documented in-situ — metrics loose-typed, never rendered).
- `types/settings.ts` — `use_series_voice: boolean`.
- `lib/api/series.ts` — 4 API methods; `lib/hooks/seriesKeys.ts` — `voice(id)`.
- `lib/hooks/useSeriesVoice.ts` — `useSeriesVoice`, `useProfileSeriesVoice`,
  `useUpdateSeriesVoiceOverride`, `useClearSeriesVoiceOverride`.
- `components/series/SeriesVoicePanel.tsx` (132) +
  `SeriesVoiceProfileView.tsx` (112, read-only descriptive display) +
  `SeriesVoiceOverrideEditor.tsx` (141, JSON-textarea + local validation) +
  `SeriesVoiceOptOutCard.tsx` (88, self-hides for standalones).
- `app/series/[id]/voice/page.tsx` — Voice tab activated (placeholder removed;
  `SeriesTabNav.tsx` un-disabled).
- `components/studio/settings/_components/useStructureChangeGuard.ts` — RULE-04
  extraction from `NovelDetailsTab` (was 200 lines; opt-out card would have
  pushed it over).

**i18n (implemented)** — `packages/i18n/messages/{en,de,fr}/studio.json`:
- `series.voice.*` namespace (title, 3 statuses, profileFrom, profile, override,
  clearOverride, showProfile, loading, fields.*, …).
- `novel.settings.useSeriesVoice.{label,description}` (new `novel` top-level
  namespace).

### 2. Migration steps (6 vertical slices — each independently shippable)

1. **Slice 1 — Data Layer (Task 1):** `use_series_voice` column + migration `0039`
   + integration tests. Column is inert until Slice 4 consumes it.
2. **Slice 2 — Backend Service (Task 2):** `SeriesVoiceService` + contracts +
   schemas + DI. Reuses the factored `AuthorVoiceAgent` pipeline helpers.
3. **Slice 3 — Backend API (Task 3):** `router_voice.py` (4 endpoints) + the
   opt-out toggle on the project-settings PATCH.
4. **Slice 4 — Core Delta (Task 4):** `render_author_voice_delta` pure renderer +
   `AuthorVoiceConsumer` extension (the critical integration step).
5. **Slice 5 — Frontend Voice Tab (Task 5):** Voice tab activated + opt-out card +
   hooks (TDD: RED → GREEN per component).
6. **Slice 6 — i18n (Task 6):** `series.voice.*` + `novel.settings.useSeriesVoice.*`
   (en/de/fr parity).

### 3. Breaking-change assessment

- **Schema change is additive + NOT NULL with server_default** → backward
  compatible. Existing rows backfill to `True` (the Delta default); standalone
  novels are unaffected (no series → flag never read).
- **`{{author_voice}}` content is byte-identical for standalone novels** → no
  generation regression. The Delta framing appears ONLY when a series voice is
  present and opted into.
- **No new prompt variable / route / manifest entry** → no prompt-surface
  governance change.
- **No new agent** → no new agent-registration / evidence-attribution path.

**Net: fully backward compatible (additive column + pure renderer + opt-in Delta).**

### 4. Test update plan (landed)

- **Core:** `render_author_voice_delta` — Delta format, series-only, opt-out,
  standalone byte-identical, empty graceful; descriptive/metric boundary
  structural (metrics never composed).
- **Backend (Task 1):** 5 integration tests — column exists, NOT NULL, ORM
  default True, server_default backfill True, opt-out accepts False.
- **Backend (Tasks 2–3):** 9 service tests (profile/get/override/clear +
  ownership 403 + no-chapters 422) + 12 router tests + settings regression. Full
  `tests/unit/api/series/` (228) + settings/author-voice pipeline (258) green.
- **Frontend (Tasks 5–6):** 31 new tests (6 `useSeriesVoice` + 5
  `useStructureChangeGuard` + 6 `SeriesVoicePanel` + 5 `SeriesVoiceOverrideEditor`
  + 4 `SeriesVoiceProfileView` + 5 `SeriesVoiceOptOutCard`) + regression.
- **Regression:** standalone generation unchanged (the byte-identical guarantee);
  voice-lane tests (ANAL-007/008/009/WRITE-010) green.

---

## Risks Surfaced for Coordinator/User Decision

These are NOT blockers for this ADR; they are acknowledged and mitigated:

1. **`POST …/voice/profile` is synchronous.** One blocking LLM call (same cost as
   the novel-level author-voice endpoint; rate-limited via `AI_ANALYSIS_LIMITER`).
   Mitigated by the band-summary precedent (also synchronous). Low risk.
2. **Provenance ambiguity (auto-profile vs override).** The single
   `author_voice` column cannot distinguish how it was produced. Mitigated by the
   frontend documenting the optimistic badge; a persisted flag is a future
   schema change. Low risk.
3. **`feature_id` attribution reuses `analysis_author_voice`.** Acceptable (it
   runs that pipeline); a parameterisation refactor is a small future task. Low
   risk.
4. **Series voice drift across bands.** A series voice profiled from band 1 may
   not match band 5's actual prose. **This is deliberately Spec 4's concern**
   (Cross-Novel Drift), not Spec 3's. The author can re-profile from any band at
   any time. Low risk for Spec 3.

No decision required a user call beyond approving the design spec.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-02/02b | ✅ | No prompt assembly in services; the Delta composition is a pure Core renderer; `{{author_voice}}` is extended (no new variable, no new route, no manifest change). The profiling call reuses the governed `author_voice` Mode-1 template via the existing pipeline helpers. |
| RULE-03 | ✅ | `SeriesVoiceServiceProtocol` (`series_voice_contracts.py`) defined before the service; the Delta renderer is a typed pure function with a docstring contract. |
| RULE-04 | ✅ | Modularised: `series_voice_{contracts,service,schemas}.py` + `router_voice.py` + `dependencies_voice.py` each own one responsibility; `series_voice_schemas.py` split because `schemas.py` was at 196/200; `useStructureChangeGuard` extracted from `NovelDetailsTab` to stay under 200. |
| RULE-05/06 | ✅ | Core owns the Delta renderer + consumer extension; Backend owns the service + migration + router; one responsibility per file; the series-voice domain owns its own contracts/service/router. |
| RULE-07 | ✅ | `router → service → repository → DB`; `SeriesRepository.update_settings` (no raw column access); Core renderer has no `apps/` imports. |
| RULE-11 | ✅ | Standalone/opt-out/no-series-voice/no-novel-voice → legacy novel-only render (byte-identical) or empty; no crash, no silent prompt regression; ownership errors are 403 (anti-enumeration), no-chapters is 422 (fail fast). |
| RULE-14 | ✅ | The `use_series_voice` column lands with migration `0039_series_voice` (atomic upgrade + downgrade, server_default for backfill) in the same task as the model change. |
| RULE-17 | ✅ | TS `SeriesVoiceProfile` mirror preserves snake_case; `use_series_voice` is boolean on both sides. |
| RULE-22 / CR-04 | ✅ | Cross-feature coherence: producer + consumer defined together; the Delta renderer is a pure composition over the existing descriptive-only renderer (boundary preserved by construction); the opt-out is binding; standalone generation is byte-identical (regression-tested). |

---

## Review Trigger

- [x] **Spec 3 implemented (2026-08-05)** — Delta model + auto-profile + opt-out
      landed across Core → Backend → Frontend (6 task slices). Coordinator commit
      pending. This item closes the Spec-3 trigger.
- [ ] When **Spec 4 (Cross-Novel Drift)** is implemented — verify the series-voice
      profile is treated as one signal among bands (not a fixed baseline) and that
      drift detection reads `SeriesSettings.author_voice` via the repository
      contract (no raw column access — the ADR-050 "no SSOT bypass" analogue).
- [ ] If the **provenance ambiguity** (auto-profile vs override) becomes a UX
      problem — add a persisted provenance flag on `SeriesSettings` (additive
      schema change).
- [ ] If **progressive feedback** is wanted on profiling — add an SSE variant of
      `POST …/voice/profile` (the underlying pipeline is stream-capable via the
      agent).
- [ ] If **`feature_id` attribution** needs to distinguish series-voice profiling
      from novel-voice profiling in evidence — parameterise
      `resolve_author_voice_prompt`'s `feature_id`.

---

## Cross-References

- **ADR-074** — Author Voice Storage (the predecessor; this ADR closes the
  Voice-Teil of its Review Trigger — FULLY CLOSED: storage by ADR-075, voice model
  by this ADR).
- **ADR-075** — Series Foundation (added the empty `SeriesSettings.author_voice`
  sibling home this ADR populates; this ADR closes its Spec-3 Review Trigger item).
- **ADR-077** — Series Generation Context (Spec 2; the series-history + KB-Redirect
  tier this voice tier sits alongside at generation time).
- **ADR-069** — `AdaptiveSettings` JSONB (the persistence shape
  `SeriesSettings.author_voice` mirrors).
- **ADR-055 / ADR-057** — descriptive/metric boundary (preserved by construction
  in the Delta renderer).
- `docs/superpowers/specs/2026-08-02-series-voice-hierarchy-design.md` — the design
  spec this ADR is based on.
- `docs/features/series/SERIES-003-voice-hierarchy.md` — the user-facing feature spec.
