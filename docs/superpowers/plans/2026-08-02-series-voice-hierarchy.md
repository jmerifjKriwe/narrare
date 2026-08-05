# Series Voice Hierarchy — Spec 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement Series Voice Hierarchy — Delta model (series voice as foundation + novel voice additive), auto-profile from one band, per-novel opt-out, full UI.

**Spec source:** `docs/superpowers/specs/2026-08-02-series-voice-hierarchy-design.md`

## Global Constraints

- Python 3.14+, `from __future__ import annotations`
- RULE-02/02b: prompts only in `core/prompts/`; no inline f-string prompts
- RULE-03: contracts before implementation
- RULE-04/05/06/07: modularize, module boundaries, one responsibility per file, one-way deps
- RULE-11: graceful degradation (standalone → no series voice, no crash)
- RULE-14: model change needs migration
- RULE-22: no new prompt variable — extend existing `{{author_voice}}`
- TDD: failing test first (ADR-014)
- Pre-commit hooks: NEVER `--no-verify`
- i18n: en/de/fr
- **CRITICAL regression:** standalone generation + voice-lane tests (ANAL-007/008/009/WRITE-010) must stay green

---

## Task 1: Migration 0039 — `use_series_voice` column

**Files:** `project_settings` model (modify), Alembic `0039`, test

- [ ] Add `use_series_voice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)` to `ProjectSettings`
- [ ] Write Alembic `0039_series_voice`: add column to `project_settings`
- [ ] Test: column exists, defaults True
- [ ] Commit: `feat(api/settings): add use_series_voice column + migration 0039`

---

## Task 2: SeriesVoiceService + repository (Backend)

**Files:** `series_voice_contracts.py`, `series_voice_repository.py`, `series_voice_service.py`, `dependencies.py` (modify), test

- [ ] Contracts: `SeriesVoiceServiceProtocol` (profile_from_novel, get, update_override, clear_override)
- [ ] Repository: read/write `SeriesSettings.author_voice` (reuse existing `SeriesRepository.update_settings`)
- [ ] Service: `profile_from_novel` → verify novel in series → fetch chapters → run existing `AuthorVoiceAgent` → store in SeriesSettings; `get`, `update_override`, `clear_override`
- [ ] DI factory: `get_series_voice_service`
- [ ] Tests (Fake-based ADR-030)
- [ ] Commit: `feat(api/series): add SeriesVoiceService + repository`

**Important:** Reuse existing `AuthorVoiceAgent` — NO new agent. The service orchestrates: fetch chapters → run agent → store result.

---

## Task 3: API endpoints + novel settings extension

**Files:** `router_voice.py`, `router.py` or `router_novels.py` (modify for use_series_voice), `main.py` (wire), test

```
POST   /api/v1/series/{id}/voice/profile         ← Body: {novel_id}
GET    /api/v1/series/{id}/voice
PATCH  /api/v1/series/{id}/voice                  ← Override (body: {author_voice: {...}})
DELETE /api/v1/series/{id}/voice/override
```

- [ ] Also extend existing novel settings PATCH to accept `use_series_voice`
- [ ] Tests: status codes, auth, ownership
- [ ] Commit: `feat(api/series): add Series Voice API endpoints`

---

## Task 4: AuthorVoiceConsumer extension (Core) — Delta model

**Files:** `AuthorVoiceConsumer` (existing — modify), test

**This is the critical integration task.** The consumer currently renders novel voice into `{{author_voice}}`. Spec 3 extends it:

```
if novel.series_id and series has voice and use_series_voice=True:
    if novel also has voice:
        "Series voice: [series profile]\n\nNovel nuances: [novel profile]"
    else:
        "Series voice: [series profile]"
elif novel has voice:
    "Author voice: [novel profile]"  (unchanged)
else:
    ""  (empty — graceful)
```

- [ ] Find `AuthorVoiceConsumer` (search in `core/ai_invocation/enrichers/` or `core/profiles/`)
- [ ] Read how it currently fetches + renders novel voice
- [ ] Extend: also fetch series voice + use_series_voice flag
- [ ] Implement Delta format
- [ ] **Regression tests:** standalone unchanged, opt-out = novel only, series+novel = Delta, empty = graceful
- [ ] **CRITICAL:** Run voice-lane tests: `uv run pytest tests/unit/api/analysis/test_author_voice*.py tests/unit/api/analysis/test_character_voice*.py tests/unit/api/writing/test_voice_check*.py tests/unit/api/analysis/test_voice_drift*.py -v`
- [ ] Commit: `feat(core): extend AuthorVoiceConsumer with Delta model for series voice`

---

## Task 5: Frontend — Voice tab + opt-out toggle

**Files:** Voice tab component (replace placeholder), hooks, novel settings toggle, tests

- [ ] Hooks: `useSeriesVoice`, `useProfileSeriesVoice`, `useUpdateSeriesVoiceOverride`, `useClearSeriesVoiceOverride`
- [ ] Replace `/series/[id]/voice/page.tsx` placeholder with functional Voice tab:
  - "Profile from Band..." dropdown + button
  - Voice profile display (metrics + descriptives)
  - Override editor
  - Status indicators
- [ ] Novel-level opt-out toggle (in Novel Settings): "Use series voice as base"
- [ ] Component tests
- [ ] Commit: `feat(web/series): activate Voice tab + novel opt-out toggle`

---

## Task 6: i18n (en/de/fr)

**Files:** `studio.json` (3 locales)

- [ ] Add `series.voice.*` keys: title, profile, profileFrom, status.autoProfiled, status.overrideActive, status.empty, override, clearOverride, showProfile
- [ ] Add `novel.settings.useSeriesVoice.*` keys: label, description
- [ ] Verify parity
- [ ] Commit: `feat(web/i18n): add series voice namespace keys`

---

## Task 7: Doc Gate

**Files:** ADR-078, SERIES-003, GLOSSARY, CURRENT_STATE, ADR-074 (fully close), cross-spec notes

- [ ] ADR-078 (mirror ADR-075/077 structure): Delta model, auto-profile, opt-out
- [ ] SERIES-003 feature spec
- [ ] GLOSSARY: Series Voice, Voice Delta, Voice Opt-out
- [ ] CURRENT_STATE: Spec 3 entry
- [ ] ADR-074 Review Trigger: mark FULLY CLOSED (both Storage + Voice)
- [ ] Cross-spec notes: Spec 3 complete
- [ ] Commit: `docs(series): Spec 3 Doc Gate — ADR-078, SERIES-003. ADR-074 fully closed.`

---

## Execution Order

```
Task 1 (Migration) → Task 2 (Service) → Task 3 (API) → Task 4 (Consumer — CRITICAL)
                                                              ↓
                                          Task 5 (Frontend) → Task 6 (i18n) → Task 7 (Doc Gate)
```

Tasks 1-4 are backend/core sequential. Tasks 5-6 depend on Task 3+4. Task 7 after all.
