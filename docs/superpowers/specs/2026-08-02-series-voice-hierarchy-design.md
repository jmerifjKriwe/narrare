# Series Voice Hierarchy — Spec 3 Design

> **Status:** Draft — awaiting user review
> **Date:** 2026-08-02
> **Predecessor:** Spec 1 (Series Foundation, ADR-075), Spec 2 (Generation Context, ADR-077)
> **Successor ADR:** ADR-078-series-voice-hierarchy (to be created)
> **Closes:** ADR-074 Review Trigger (fully — Storage by ADR-075, Voice by ADR-078)

---

## 1. Context

Spec 1 created `SeriesSettings.author_voice` (empty, forward-compat). Spec 2 injected series history at generation time. Spec 3 fills the series voice and defines how it interacts with novel-level voice during generation.

ADR-074 explicitly deferred the voice resolution model to "the Series feature." Spec 3 closes this question.

## 2. Design Decisions

| # | Decision | Choice |
|---|----------|--------|
| D1 | Voice resolution model | **Delta** — series voice as foundation, novel voice additive, per-novel opt-out |
| D2 | Series voice source | **Auto-profile from one band + manual override** (same pattern as BandSummary in Spec 2) |
| D3 | Opt-out mechanism | `ProjectSettings.use_series_voice: bool = True` (per-novel toggle) |
| D4 | Prompt integration | **Extend `{{author_voice}}`** (no new variable; content changes based on series membership) |

### 2.1 Why Delta (not Override, Blend, or Cascade)

- **Override** loses series consistency when a novel has its own profile
- **Blend** is ill-defined for LLM prompts (what does "70% formal + 30% colloquial" mean as text?)
- **Cascade** triggers the Cascade-Fallback-Kritik (forced cascade is harmful)
- **Delta** is additive, natural for LLMs, and respects opt-out. The prompt says "Series voice is X. Additionally, this novel has Y." — the LLM processes both organically.

### 2.2 Why No New Agent

`AuthorVoiceAgent` (existing, ANAL-007) profiles a novel's voice from its chapters. For series voice, we run the same agent on one selected band. No new agent needed — just a new service method that stores the result in `SeriesSettings.author_voice`.

## 3. Architecture

### 3.1 Voice Resolution Logic (Core — AuthorVoiceConsumer extension)

```python
async def assemble(novel_id, series_id=None):
    novel_voice = get ProjectSettings.author_voice for novel_id

    if series_id:
        series_voice = get SeriesSettings.author_voice for series_id
        use_series = get ProjectSettings.use_series_voice for novel_id

        if series_voice and use_series and novel_voice:
            return f"Series voice:\n{series_voice}\n\nNovel nuances:\n{novel_voice}"
        elif series_voice and use_series:
            return f"Series voice:\n{series_voice}"

    # Fallback: novel voice only (unchanged)
    if novel_voice:
        return f"Author voice:\n{novel_voice}"

    return ""  # Empty → graceful degradation
```

### 3.2 Opt-out Mechanism

New column: `project_settings.use_series_voice BOOLEAN NOT NULL DEFAULT TRUE`

- Default True: all series novels use series voice as base
- Set False: novel ignores series voice, uses only its own voice
- Managed via Novel Settings UI toggle

### 3.3 No New Prompt Variable

`{{author_voice}}` content changes based on context:
- **Standalone:** "Author voice: [novel profile]" (unchanged)
- **Series + Novel voice:** "Series voice: [series]\n\nNovel nuances: [novel]"
- **Series only (no novel voice):** "Series voice: [series]"
- **Opt-out:** "Author voice: [novel profile]" (series skipped)
- **No profiles:** "" (empty)

## 4. Backend

### 4.1 SeriesVoiceService

```python
class SeriesVoiceService:
    async def profile_from_novel(self, series_id, novel_id) -> dict: ...
    async def get(self, series_id) -> dict | None: ...
    async def update_override(self, series_id, override: dict) -> None: ...
    async def clear_override(self, series_id) -> None: ...
```

- `profile_from_novel`: verify novel in series → fetch chapters → run AuthorVoiceAgent → store in SeriesSettings.author_voice
- Reuses existing `AuthorVoiceAgent` — no new agent

### 4.2 API Endpoints

```
POST   /api/v1/series/{id}/voice/profile        ← Body: {novel_id}
GET    /api/v1/series/{id}/voice
PATCH  /api/v1/series/{id}/voice                 ← Manual override
DELETE /api/v1/series/{id}/voice/override         ← Clear override
PATCH  /api/v1/novels/{id}/settings               ← Extended: accept use_series_voice
```

### 4.3 Migration `0039_series_voice`

- Add `use_series_voice BOOLEAN NOT NULL DEFAULT TRUE` to `project_settings`

## 5. Frontend

### 5.1 Voice Tab (SeriesWorkspace)

Replace disabled placeholder with functional Voice tab:
- "Profile from Band..." button (dropdown selects band → POST)
- Voice profile display (metrics + descriptives)
- Override editor
- Status: auto-profiled / override active / empty

### 5.2 Novel-Level Opt-out

Toggle in Novel Settings: "Use series voice as base" (default on)

### 5.3 i18n

`series.voice.*` namespace in `studio.json` (en/de/fr)

## 6. Testing

- **Core:** AuthorVoiceConsumer — Delta format, opt-out, standalone unchanged, empty graceful
- **Backend:** SeriesVoiceService — profile, override, ownership; API endpoints
- **Frontend:** Voice tab component, opt-out toggle
- **Regression:** ANAL-007/008/009/WRITE-010 voice-lane tests green; standalone generation unchanged

## 7. Doc Gate

| Artifact | What |
|----------|------|
| ADR-078 | Series Voice Hierarchy: Delta model, auto-profile, opt-out |
| SERIES-003 | Feature spec |
| GLOSSARY | Series Voice, Voice Delta, Voice Opt-out |
| CURRENT_STATE | Spec 3 entry |
| ADR-074 | **Review Trigger FULLY CLOSED** |
| Cross-Spec Notes | Spec 3 complete |

## 8. YAGNI

- Voice aggregation across multiple bands → future
- Cross-novel voice drift → Spec 4
- Author-level base voice → YAGNI (ADR-074 rejected)
- Weighted blend model → rejected (ill-defined for LLM)

## 9. Success Criteria

- [ ] AuthorVoiceConsumer produces Delta format for series novels
- [ ] Opt-out works (novel ignores series voice when toggled off)
- [ ] Standalone generation unchanged (regression)
- [ ] Series voice profilable from any band
- [ ] Manual override functional
- [ ] Voice tab in SeriesWorkspace active
- [ ] Novel-level opt-out toggle
- [ ] All voice-lane regression tests green
- [ ] ADR-078 + SERIES-003 written
- [ ] ADR-074 Review Trigger fully closed
