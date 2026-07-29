# Series-Feature — Cross-Spec Notes

> **Purpose:** Living notes captured during the Spec 1 brainstorming cycle
> (`Reihe/Series Foundation + KB Evolution`) that are **out of scope for Spec 1**
> but **load-bearing for Specs 2–5**. Each later spec must read this file before
> starting its own brainstorming cycle.
>
> **Maintained by:** Coordinator (during Spec 1 brainstorming), then handed off
> to the relevant Spec owner.
>
> **Created:** 2026-07-28
> **Last updated:** 2026-07-29 (Doc-Gate-Deferrals komplett in YAGNI-Tabelle dokumentiert)

---

## Series Feature — Program-Level Decomposition

The Series feature is decomposed into 5 sequenzielle Specs. **Each Spec is
implemented before the next Spec's brainstorming begins** (no „irgendwann später"):
Spec N → Implement → Spec N+1 → Implement → …

| # | Spec | Enthält | Vorbedingung |
|---|------|---------|--------------|
| **1** | Series Foundation + KB Evolution | `Series`-Entity, `Novel.series_id`, KB Series-Canon+Novel-Overlay-Modell, CRUD, Navigation, UI | — (current brainstorming cycle) |
| 2 | Series Generation Context | Reihen-Kontext für Band N (Summaries, Welt-Status, state-at-(N−1) Read-Merge) | Spec 1 implementiert |
| 3 | Series Voice Hierarchy | Override/Blend/Cascade für Reihen-Basisstimme + Roman-Nuancen | Spec 1 implementiert (schließt ADR-074 Review Trigger) |
| 4 | Series Cross-Novel Drift | ANAL-009 series-scope-Erweiterung (Drift über Bänder hinweg) | Spec 1+2+3 |
| 5 | Series Export | Reihen-Manuskript / Reihen-Bibel / Einzeltitel | Spec 1 |

---

## Keystone Decision (decided in Spec 1, binds all later Specs)

**KB strategy: Option C — Hybrid Series-Canon + Novel-Overlay.**

- KB entries carry an explicit scope: **Series-Scoped** (canon, shared across
  all novels in the series) vs **Novel-Scoped** (overlay, valid only in one novel).
- Series-Scoped entries model stable facts (Magiesystem, setting, world rules,
  canonical character bio). Novel-Scoped entries model evolving state
  (Harry Potter in Book 4 ≠ Book 1).
- Read semantics: Series-Base + Novel-Overlay merged at read time (overlay
  wins where present).
- This decision BINDS Specs 2–5 because every consumer (Generation, Voice,
  Drift, Export) reads KB through this lens.

### Why Option C (and not A or B)

- Heterogeneity of KB entity types: `system/concept/setting` rarely evolve
  (Option A would duplicate them); `character/faction` evolve heavily
  (Option B would force a snapshot mechanism on every entry).
- Option C is the **only** model that respects both profiles naturally.
- Per-fact (not per-entity-type) decision about scope: every entry can be
  Series- or Novel-scoped; entity-type-based defaults are a UX policy, not
  a schema constraint.

---

## Notes for Spec 2 — Series Generation Context

### Context to inject when generating Band N

1. **Series-Canon** (all Series-Scoped KB entries): Magiesystem, world rules,
   canonical character bios, foundational artifacts.
2. **Latest-known-state for each Novel-Scoped entry at end of Band N−1**:
   - Read the Novel-Overlay of Band (N−1).
   - If absent, fall back to last earlier band that has an overlay.
   - This is the „state of the world as the new book begins".
3. **Trajectory (optional, for arc-sensitive generation):** arc-summary across
   bands 1..N−1 for pivotal characters. (Likely user-toggle per generation run.)

### Open questions for Spec 2 brainstorming

- **Band-summary source:** Chapter-summary aggregation (WIKI-001) per novel,
  or explicit „Band-N-Summary" field on Novel?前者 simpler, letzterer curated.
- **World-Status snapshot:** explicit „Status am Ende von Band N"-Feld (gepflegt)
  vs. automatisch aus KB+Chapter-Summaries abgeleitet?
- **Token budget:** Series-Canon kann groß werden (Perry-Rhodan-Fall).
  Braucht Priority/Recency-Ranking bei Context-Assembly (ähnlich
  bestehendem KB-Context-Ranking in `core/context/`).
- **What happens at Band 1 of a new series:** Series-Canon leer (wenn neue
  Reihe) vs. alles aus „Band 1" als Canon-Quelle (wenn Reihe aus Standalone
  entsteht). Schließen muss mit Spec-1-Migrations-Policy konsistent sein.

### Code hints (existing infrastructure Spec 2 will reuse)

- `apps/api/narrare/kb/_context_provider.py` (ADR-067) — already consolidates
  KB-context assembly; Spec 2 extends this for series-scope merge.
- `packages/core/narrare_core/context/` — context-assembly pipeline.
- `apps/api/narrare/wiki/` (WIKI-001) — chapter summaries are already
  available; novel-level summary likely needs aggregation.

---

## Notes for Spec 3 — Series Voice Hierarchy

### ADR-074 Review Trigger (this Spec closes it)

> ADR-074 §Review Trigger: „When the Series / Reihe feature is designed —
> revisit the voice resolution model (novel-only vs novel+series blend);
> add the sibling `SeriesSettings.author_voice` home; confirm this ADR's
> novel-level home remains the primary scope (no forced cascade)."

### The Cascade-Fallback-Kritik (carried from Voice-Brainstorming)

> A standalone novel written in a deliberately different voice would fall back
> to the author's „base voice" and inject the author's *usual* patterns into
> an experimental book — the opposite of what the writer wants.

**Carries to Series:** within a series, the question is sharper.
- Option A — **Override:** Novel-voice wins completely. Series-voice is
  fallback for novels without their own profile.
- Option B — **Blend:** weighted combination (e.g. 70% series base + 30% novel nuance).
- Option C — **Cascade:** Series-voice as base, novel-voice as delta-style override.

The Voice-Brainstorming's criticism applies to **forced** cascade. A Series
**opt-in** base voice is fine — but it must not silently inject into novels
whose author explicitly profiled a different voice.

### Storage hint (already promised by ADR-074)

Add a sibling `SeriesSettings.author_voice` JSONB column on the new `Series`
entity (mirrors `ProjectSettings.author_voice`). No migration of existing
novel-level data required — additive.

### Open questions for Spec 3 brainstorming

- Override vs Blend vs Cascade default
- Per-novel opt-out from series voice
- UI: where does user manage Series-voice vs Novel-voice? (Series-Editor
  from Spec 1 likely needs a Voice tab.)
- ANAL-007 (Author Voice Profiling) currently profiles per-novel; needs
  series-scope profiling variant.

---

## Notes for Spec 4 — Series Cross-Novel Drift

### ANAL-009 series-scope extension

Current drift is novel-internal (within-band consistency over time).
Series-scope drift adds:
- **Character arc drift across bands:** does Harry in Band 4 still „make sense"
  given Harry in Bands 1–3? (Detect contradictions in state, voice, motivation.)
- **Voice drift across bands:** reuse `author_metric_distances` primitive
  (ADR-057) at series scope.
- **Canon contradiction:** Band 5 introduces a fact that contradicts
  Series-Canon (e.g. character's age wrong, magic rule broken).

### Open questions for Spec 4 brainstorming

- Read-scope for drift: full-series scan vs current-band-vs-prior-band
- Canonical-contradiction detection needs formal Series-Canon-as-truth model
  (depends on Spec 1's scope-policy implementation)
- Performance: drift on a 50-novel series is expensive — caching strategy
- UI: separate Series-Drift view vs extension of existing per-novel ANAL-009 panel

---

## Notes for Spec 5 — Series Export

### Export modes (likely)

- **Einzeltitel:** unchanged (current export per novel).
- **Reihen-Manuskript:** all novels concatenated with band-divider frontmatter.
- **Reihen-Bibel:** Series-Canon KB export (all Series-Scoped entries),
  grouped by entity type — useful for handing off to publisher/agent.

### Open questions for Spec 5 brainstorming

- Format: PDF/EPUB/Markdown for each mode?
- Series-Bibel layout: by entity type? By band-introduction order?
- Should Series-Canon export include „state at end of band N" overlays for
  each character (the „time-lapse view")?

---

## Resolved Questions (Spec 1 Brainstorming — all 6 answered 2026-07-28)

- [x] **Q1 — KB strategy:** Option C (Hybrid Series-Canon + Novel-Overlay).
      Reason: heterogeneity of KB entity types (Magiesystem ≠ Charakter);
      respects both stable and evolving facts.
- [x] **Q2 — Scope-policy for new entries:** Policy (iii) — entity-type-based
      default with override. `system/concept/setting/location/object/timeline →
      Series-Canon`; `character/faction → Novel-Overlay`. User can always
      override via scope toggle.
- [x] **Q3 — Migration policy for „join series":** Policy (α) — adaptive
      based on Canon state. If Series-Canon is empty at join time (new series
      from standalone), apply Policy-(iii) heuristics to existing entries.
      If Series-Canon is non-empty, all joining novel's entries default to
      Novel-Overlay. **Preview required before apply** (joins are
      semi-destructive, hard to undo).
- [x] **Q4 — Series data model:** Confirmed schema (id, user_id, title,
      subtitle, description, genre, writing_language [optional], status,
      planned_novel_count, timestamps). Status enum in Narrare vocabulary:
      `draft | active | completed`. `SeriesSettings.author_voice` JSONB column
      created in Spec 1 (empty — forward-compat for Spec 3, closes ADR-074
      Review Trigger). Each novel retains its own identity (title, author,
      optional new `Novel.subtitle` field added in Spec 1).
- [x] **Q5 — Navigation/Dashboard:** N2 — Series as First-Class Workspace.
      Dashboard shows Series cards + Standalone cards. Klick auf Reihe →
      Series-Workspace (Tabs: Bände, Series-Canon KB, Voice [Placeholder für
      Spec 3], Settings). Klick auf Roman → Editor (wie bisher). Series-Canon
      KB hat eine dedicated Heimat (Tab im Workspace) — nicht in Roman
      eingebettet.
- [x] **Q6 — Multi-series membership:** Single-Series in Spec 1. `Novel.series_id`
      is single nullable FK (no join table). Crossover is YAGNI; migration path
      to join table is known if real demand emerges.

### Visual artifacts

- `_scratch/series-mockups/` — 4 HTML mockups + index for navigation/scope UI
  (N1 vs. N2 comparison, Series-Workspace detail, KB scope-marking UI).
  Open `_scratch/series-mockups/index.html` in browser to view.
  **Note:** `_scratch/` is gitignored; mockups are session-artifacts only.

---

## YAGNI — What's Deferred from Spec 1 (transparency per user request)

The following features are **deliberately out of scope for Spec 1** to keep
the Foundation focused. They are tracked here transparently so they don't
get lost. Each item lists its target Spec.

| Feature | Target | Rationale for deferral |
|---------|--------|------------------------|
| **Conflict detection** (Canon says X, Overlay says Y → warn user) | Spec 2+ | Needs diff-logic across scope boundaries; complex; not critical for Foundation |
| **Series stats endpoint** (Reihen-Fortschritt, Wortzahl, etc.) | Spec 2 | Nice-to-have; not load-bearing for Foundation |
| **Drag-sort for novel order** | Spec 2 (initial: up/down buttons suffice) | Polish; not Foundation-critical |
| **Batch promote/demote** (multi-select entries, bulk scope change) | Spec 2 | Per-Entry is sufficient for Foundation |
| **Series search/filter in Dashboard** | Spec 2 | Premature optimisation |
| **Series cover image upload** | Spec 5 (Export) | Cosmetic; not Foundation |
| **Series-Voice tab functional** | Spec 3 | Disabled-placeholder in Spec 1; Spec 3 fills (closes ADR-074 Review Trigger) |
| **Series-Export** (Manuscript, Bibel) | Spec 5 | Out of Foundation scope |
| **Generation-Context for Band N** (state-at-(N−1) read-merge) | Spec 2 | Needs the Foundation to exist first |
| **Cross-Novel-Drift** (ANAL-009 series-scope extension) | Spec 4 | Needs Spec 1+2+3 |
| **Multi-Series-Membership / Crossover** | No Spec (YAGNI) | Migration path to join-table known if real demand emerges |
| **Optional Docs** (`docs/reference/directory-structure.md` update, `CHANGELOG.md` entry, `docs/development/orchestrator.md` Series-Notes) | Later Specs (when natural) | Not DoD-critical for Spec 1; will be picked up by later Specs when those docs are touched for other reasons. YAGNI to do them now without concrete trigger. |
| **Series-Stats-UI** (Fortschrittsanzeige, Bände-Completion-Visualisierung) | Spec 2 | Depends on stats endpoint |

### Reversal cost awareness

Each deferred item is **additive** when it lands — none requires undoing
Spec 1 work. The Foundation (Series entity, KB scope-discriminator, N2
Workspace) is designed to host all later additions without restructuring.

---

## Decisions Log (chronological)

| Date | Decision | Rationale | Affects |
|------|----------|-----------|---------|
| 2026-07-28 | Decompose Series into 5 sequenzielle Specs (Spec→Impl→Spec→Impl) | Too large for single spec; user explicitly wants sequenzielle Kadenz, not „irgendwann später" | All Specs |
| 2026-07-28 | KB strategy = Option C (Hybrid Series-Canon + Novel-Overlay) | Heterogeneity of KB entity types (Magiesystem ≠ Charakter); respects both stable and evolving facts | All Specs |
| 2026-07-28 | Spec 1 includes UI (not just backend) | User wants Reihe benutzbar nach Spec 1 | Spec 1 only |
| 2026-07-28 | Scope-policy for new entries = Policy (iii) — entity-type-based default with override | Uses free domain knowledge (Magiesystem rarely evolves, character almost always); minimises manual work while staying safe | Spec 1 |
| 2026-07-28 | Migration policy for join = Policy (α) — adaptive on Canon state | Two scenarios (new-series-from-standalone vs add-to-existing) are semantically different; policy adapts automatically | Spec 1 |
| 2026-07-28 | Series data model confirmed; status enum `draft\|active\|completed`; `SeriesSettings.author_voice` created in Spec 1 (empty); `Novel.subtitle` added | Narrare-vokabular; forward-compat for Spec 3 without migration; consistent Novel identity | Spec 1 (data model) |
| 2026-07-28 | Navigation = N2 (Series-Workspace, first-class) | Specs 2–5 all need a Heimat for series-level UI; Series-Canon KB needs dedicated editor; mental clarity „working on series" vs „working on novel" | Spec 1 (UI) |
| 2026-07-28 | Multi-series membership = Single-Series in Spec 1 (no Crossover) | YAGNI; migration path to join-table is known if real demand emerges | Spec 1 (data model) |
| 2026-07-29 | Schema = Option 2A + STI (Single `kb_entries` table with scope discriminator at DB level + discriminated `SeriesKBEntry` / `NovelKBEntry` Pydantic types in Core) | 2B (two tables) rejected: real benefits (type safety) but UNION-read-path + cross-table-relationships + ~15-module blast radius outweigh benefits. 2A+STI gets 2B's type-safety without 2B's main costs. | Spec 1 (data model, Core types) |
| 2026-07-29 | Phasing = 5 vertical slices (Data Foundation → KB Scope → Series CRUD + Join → Frontend Dashboard + Workspace → KB Scope UI) | Each slice is independently reviewable + deployable; matches Narrane's Core → Backend → Frontend → Platform pattern; lets dependencies flow naturally | Spec 1 (implementation order) |
| 2026-07-29 | YAGNI list documented transparently in this file | User request: deferred items must be tracked, not silently dropped. Each deferred feature has a target Spec and rationale. | All Specs |

---

## Cross-References

- `docs/architecture/decisions/ADR-074-author-voice-storage.md` — §„Volume ≠
  Series" (definitive), §„Series / Reihe is the NEXT major platform-level
  feature" (impact table), §„Forward-compatibility" (Series-Voice storage
  promise), §„Review Trigger" (Spec 3 closes).
- `docs/features/writing/WRITE-011-volume-management.md` — Volume definition
  (intra-novel chapter grouping; definitively ≠ Series).
- `apps/api/narrare/volumes/models.py:19` — `Volume.novel_id` ForeignKey
  evidence for Volume ≠ Series.
- `apps/api/narrare/novels/models.py` — current Novel model (where
  `series_id` FK would land).
- `apps/api/narrare/kb/models.py` — current KB model (no evolution, no series
  scope; `UniqueConstraint("novel_id", "slug")`).
- `docs/architecture/decisions/INDEX.md` — ADR-074 is latest; **next ADR for
  Series Foundation = ADR-075**.
