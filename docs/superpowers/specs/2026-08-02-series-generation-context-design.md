# Series Generation Context — Spec 2 Design

> **Status:** Draft — awaiting user review
> **Date:** 2026-08-02
> **Authors:** Coordinator (brainstorming synthesis)
> **Brainstorming session:** 2026-08-02 (4 clarifying questions + 4 design sections)
> **Predecessor:** Spec 1 (Series Foundation) — PR #145, ADR-075
> **Companion:** `docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md` §„Notes for Spec 2"
> **Successor ADR:** ADR-076-series-generation-context (to be created)

---

## 1. Context

### 1.1 What Spec 2 Solves

Spec 1 delivered the Series Foundation: entity, KB scope model (Canon + Overlay), CRUD, navigation, UI. But **writing in a series novel is identical to writing a standalone** — the generation pipeline has no awareness of prior bands.

Spec 2 closes this gap: when generating text for Band N, the system injects **series history context** — what happened in prior bands, what the world state was, what the rules are — so generation is consistent across the series.

### 1.2 What Spec 1 Already Provides

| Capability | Source | Available? |
|------------|--------|------------|
| `KBRepository.find_merged_for_novel(novel_id)` | Spec 1 Slice 2 Task 2.2 | ✅ Merges Canon + Overlay |
| `KBRepository.find_canon_for_series(series_id)` | Spec 1 Slice 2 Task 2.2 | ✅ All Canon entries |
| `Novel.series_id` + `series_position` | Spec 1 Slice 1 Task 1.3 | ✅ Series membership |
| WIKI-001 per-novel entity summaries | Existing (ADR-022) | ✅ Entity states per novel |
| Chapter summaries (ChapterSummaryAgent) | Existing | ✅ Per-chapter summaries |
| TokenBudgetManager (tier-based budget) | Existing (ADR-025) | ✅ Budget allocation |

### 1.3 What's New in Spec 2

1. **BandSummaryAgent** — aggregates chapter summaries into a novel-level band summary (full + short)
2. **SeriesHistoryTier** — new context tier that injects band summaries + wiki entity states
3. **KB-Redirect** — for series novels, KB context comes from `find_merged_for_novel()` instead of per-novel
4. **`{{series_history}}` prompt variable** — governed template slot for the new tier
5. **Series Settings** — configurable context window size (how many bands to include)

---

## 2. Design Decisions

| # | Decision | Choice |
|---|----------|--------|
| D1 | What to inject | KB-Redirect + Band-Summaries + Wiki-Summaries (all three) |
| D2 | Band-Summary source | Auto-generated from chapter summaries + optional author override |
| D3 | How many bands | Recency-window with configurable count (default 3); older bands = one-sentence summary |
| D4 | Generation trigger | Triple: auto on novel-completion + manual button + lazy fallback |
| D5 | Pipeline integration | New "Series History" context tier (Approach 1) with own token budget + `{{series_history}}` variable |

### 2.1 Why All Three Context Types (D1)

- **KB-Redirect** provides the stable foundation (Magiesystem, world rules, canonical character bios)
- **Band-Summaries** provide the plot context ("what happened in Band 3?")
- **Wiki-Summaries** provide the entity-state context ("Harry was 15, dealing with PTSD, formed Dumbledore's Army")

Without all three, the generation either lacks factual grounding (no KB) or narrative continuity (no summaries).

### 2.2 Why Auto-Generated + Override (D2)

- Auto-generation from existing chapter summaries means zero author effort
- Override allows quality control for authors who want curated summaries
- Read logic: `override or full_summary or lazy_generate`

### 2.3 Why Recency-Window (D3)

- Full summaries for all bands would blow the context window at >5 bands
- Only N-1 misses long-term character arcs
- Recency-window (default 3) balances detail and token budget; configurable for complex series
- Older bands get one-sentence summaries (always available, minimal token cost)

---

## 3. Architecture

### 3.1 New Components

**`BandSummary` Model (new table `band_summaries`):**
```sql
novel_id: UUID UNIQUE FK→novels ON DELETE CASCADE (1:1)
full_summary: TEXT          -- auto-generated, multiple paragraphs
short_summary: TEXT         -- auto-generated, one sentence
override: TEXT | None       -- author-curated override (nullable)
generated_at: TIMESTAMPTZ   -- last auto-generation timestamp
```

Separate table (RULE-06: Novel model not overloaded).

**`BandSummaryAgent` (`core/agents/band_summary_agent.py`):**
- Pydantic-AI Agent, consumes `ChapterSummary` entries of a novel
- Output: `BandSummaryOutput(full_summary: str, short_summary: str)`
- `LLMIntent.SUMMARIZE` + new `context_mode = "band_summary"` + governed EN template
- 1 LLM-Call per band summary

**`SeriesHistoryTier` (`core/context/series_history.py`):**
```python
class SeriesHistoryTier:
    async def assemble(
        self, novel_id: UUID, series_id: UUID,
        window_size: int, token_budget: int,
    ) -> str:
        # 1. Fetch novels 1..N-1 by series_position
        # 2. Last `window_size` bands: full_summary (or override)
        # 3. Older bands: short_summary only
        # 4. Fetch Wiki entity summaries for Band N-1
        # 5. Format as "Previously in this series:" text block
        # 6. Truncate to token_budget
```

**KB-Redirect (pipeline modification):**
```python
if novel.series_id is not None:
    kb_entries = await kb_repo.find_merged_for_novel(novel_id)
else:
    kb_entries = await kb_repo.find_for_novel(novel_id)  # unchanged
```

### 3.2 Context Tier Structure

```
Generation Pipeline for Band N:
  Tier 1: System/Meta/Capabilities          (existing)
  Tier 2: KB Context                        (REDIRECT for series novels)
  Tier 3: Chapter History (Band N)          (existing)
  Tier 4: Wiki Context (Band N)             (existing)
  Tier 5: SERIES HISTORY (NEW)              ← Band-Summaries + Wiki from prior bands
  Tier 6: User Input / Instructions         (existing)
```

### 3.3 Prompt Integration

New governed prompt variable `{{series_history}}` (SYSTEM_VARS per RULE-22):
- Contains: formatted band summaries + wiki entity states
- Template slot: „Previously in this series:" + band-by-band listing
- Empty for standalones (renders nothing → graceful degradation per RULE-11)

### 3.4 Settings

`series_settings.context_window_size: INTEGER NOT NULL DEFAULT 3`

Configurable via Series Settings UI (slider 1–10 or "All").

### 3.5 Dependency Direction (RULE-07)

```
apps/writing/services → core/context/series_history → core/context/budget
                                ↓
                        core/agents/band_summary_agent → core/llm/gateway
                        apps/api/narrare/kb/repository (find_merged_for_novel from Spec 1)
```

---

## 4. Backend

### 4.1 BandSummaryService

```python
# apps/api/narrare/series/band_summary_service.py
class BandSummaryService:
    async def generate(self, novel_id: UUID) -> BandSummary: ...
    async def get_or_generate(self, novel_id: UUID) -> BandSummary: ...  # lazy fallback
    async def update_override(self, novel_id: UUID, override: str | None) -> BandSummary: ...
```

### 4.2 Auto-Trigger on Status Change

When series status transitions to `completed` → enqueue TaskIQ background task:
`generate_band_summary_task(novel_id)` for each novel in the series.

File: `apps/api/narrare/series/tasks.py`.

### 4.3 API Endpoints

```
POST   /api/v1/series/{id}/novels/{novel_id}/band-summary           ← Manual (re)generate
GET    /api/v1/series/{id}/novels/{novel_id}/band-summary           ← Fetch existing
PATCH  /api/v1/series/{id}/novels/{novel_id}/band-summary           ← Set override
DELETE /api/v1/series/{id}/novels/{novel_id}/band-summary/override   ← Clear override
```

### 4.4 Migration `0038_band_summaries`

1. Create `band_summaries` table
2. Add `context_window_size INTEGER NOT NULL DEFAULT 3` to `series_settings`
3. Full upgrade + downgrade (RULE-14)

### 4.5 RULE-13

`BandSummaryAgent` needs only `run()` (batch job, no streaming). Inherits both methods from `NarrareAgent`.

---

## 5. Frontend

### 5.1 Series Settings — Context Window

Slider (1–10) in `SeriesSettings.tsx`. Saves `context_window_size` via `PATCH /series/{id}/settings`.

### 5.2 Band Summary Card (in BändeList)

Per band row:
- **Show:** expandable panel with full_summary (read-only for auto, editable for override)
- **Regenerate:** triggers POST endpoint (loading state)
- **Override:** textarea for manual summary; "Clear Override" reverts to auto

### 5.3 Lazy Generation Indicator

Brief progress banner when generation triggers lazy summary creation. Non-blocking.

### 5.4 No Separate Series-History Viewer

Series history is injected at generation time, not displayed as a separate UI view. Users see the sources (band summaries) and the control (window slider).

### 5.5 Hooks

```typescript
useBandSummary(seriesId, novelId)
useGenerateBandSummary(seriesId, novelId)
useUpdateBandSummaryOverride(seriesId, novelId)
useClearBandSummaryOverride(seriesId, novelId)
```

### 5.6 i18n (en/de/fr)

New keys in `studio.json`: `series.bandSummary.*`, `series.settings.contextWindow.*`.

---

## 6. Testing

### 6.1 Core Tests
- `BandSummaryAgent` — TestModel: verify output structure
- `SeriesHistoryTier` — recency-window logic, token truncation, override preference, standalone graceful degradation
- KB-Redirect — series novel → merged, standalone → per-novel

### 6.2 Backend Tests
- `BandSummaryService` — generate, get_or_generate (lazy), update_override
- API endpoints — status codes, auth
- Migration `0038` — upgrade + downgrade roundtrip
- Auto-trigger — TaskIQ task enqueued on status→completed

### 6.3 Frontend Tests
- Band Summary Card — show/regenerate/override, loading states
- Context window slider — value change, save
- Hooks — standard TanStack Query mock tests

### 6.4 Regression (Critical)
- **Standalone generation unchanged** — existing writing tests green
- **Voice-lane** — ANAL-008/WRITE-010/ANAL-009 green
- **Existing context tiers** — budget redistribution doesn't degrade quality

### 6.5 Coverage
Core 90%+, Backend 85%+, Frontend 80%+, Migration 100%.

---

## 7. Doc Gate

| Artifact | What |
|----------|------|
| ADR-076 (new) | Architecture decision: Series-History-Tier, BandSummaryAgent, Recency-Window, Triple-Trigger |
| SERIES-002 (new) | Feature spec: Series Generation Context |
| GLOSSARY | Band Summary, Series History, Context Window |
| CURRENT_STATE | Spec 2 implementation entry |
| Cross-Spec Notes | Update: Spec 2 complete; Spec 3 (Voice) next |
| ADR-075 Review Trigger | Verify `find_merged_for_novel` correctly used |

---

## 8. YAGNI — What's NOT in Spec 2

- **Series Voice Hierarchy** → Spec 3
- **Cross-Novel Drift** → Spec 4
- **Series Export** → Spec 5
- **Token-level cost estimation** for series context → future
- **User-selectable per-band context weight** → future (default recency is sufficient)
- **Manual chapter-selection for band summary** → future (auto from all chapters)

---

## 9. Success Criteria

- [ ] BandSummaryAgent generates full + short summaries from chapter summaries
- [ ] SeriesHistoryTier assembles recency-windowed context with token budget
- [ ] KB-Redirect active for series novels, unchanged for standalones
- [ ] `{{series_history}}` governed prompt variable registered + wired
- [ ] Auto-trigger on series completion + manual button + lazy fallback
- [ ] Context window slider in Series Settings (configurable, default 3)
- [ ] Band Summary card in BändeList with show/regenerate/override
- [ ] All regression tests green (standalone generation + voice-lane)
- [ ] ADR-076 + SERIES-002 + GLOSSARY + CURRENT_STATE written
- [ ] `just check` green
