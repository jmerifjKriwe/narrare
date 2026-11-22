# Settings AI-Regeln & Prompts W8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The settings capability's AI-Regeln surface (providers, models, per-task assignment with output profiles) and the prompts override editor with preview and live test — on the existing backend plus the two decided builds — as W8 of the frontend rebuild.

**Architecture:** Same shape as W6 scaled up: a Stitch round produces the hub chrome and both W8 authorities (owner gate); three PRs under PR-für-PR — Opener (the seven findings, driver-kind, drift), AI-Regeln (its backend + surface), Prompts (preview + live test + surface + ledger); the settings e2e directory grows, prompts gets its own with the kernel expectation growing in the same commit.

**Tech Stack:** React + TanStack Router/Query, Tailwind on the shell tokens, i18n catalogs (de/en/fr), Vitest, pytest, Playwright E2E; FastAPI + async SQLAlchemy + Alembic for the two backend builds.

**Spec:** `docs/superpowers/specs/2026-11-22-settings-ai-rules-prompts-w8-design.md` — the plan argues from it; executors read both.

## Global Constraints

- Standing rules (CONSTRAINTS.md); **PR für PR** (one PR green + threads resolved before the next starts); Lane A end to end; SDD ledger at `.superpowers/sdd/2026-11-22-settings-ai-prompts-w8/progress.md` in the main checkout, branch `feat/settings-ai-rules` checked out there.
- Seats rev. 7: implementer `zai-coding-plan/glm-5.3-flash`, reviewer `zai-coding-plan/glm-5.3` (until qwencloud returns 2026-12-13); reviewer fallback when z.ai's window is exhausted: `opencode/beam-free` (check `openchamber_usage`, not the error text).
- Stitch alone designs; the owner approves the round before porting starts.
- i18n: three catalogs, sorted parity, du-tone (fr tu).
- Absent-vs-carried-null everywhere; only dirtied fields ride a save; the assignment's profile column has **no** two-state semantics — absent and null both mean `balanced`.
- Output-profile vocabulary and targets (kernel-owned): `quick=1024, balanced=4096, long_texts=12288, comprehensive=32768`; resolution caps at a **stored** ceiling only (`min(profile, ceiling)`); unknown ceiling stands uncapped and is shown as is; `custom` bounded to a known ceiling at save.
- No key material beyond the one create response; masks `sk-…xxxx` everywhere else.
- No WP2b slider in any shape; the allocator stays kernel-owned.
- E2E: per-suite DB, de-DE contexts, hand-made contexts repeat `locale de-DE`; the kernel expectation grows `prompts` in the SAME commit as the e2e directory.
- The phantom-dir trap: after any branch switch, remove leftover capability `e2e/__pycache__` dirs the target branch doesn't track.

## Review Focus

1. **The key returns exactly once** — every read after create answers the mask (`sk-…xxxx`), the create response is the only carrier; pins on the wire (Task 9).
2. **The resolved output number is honest** — never above a stored ceiling, uncapped-when-unknown shown as is, absent/null assignment = `balanced`; pins in kernel resolution tests and the Aufgaben face (Tasks 8, 9).
3. **The live test cannot lie or leak** — an unsaved draft passes the render sandbox before any provider call; the streamed answer and the draft are never persisted; the audit row lands under the key's task; rate limit refuses the second immediate call (Task 11).
4. **No dead door in any interim** — PR2's hub chrome carries Allgemein + KI-Regeln only (no prompts item until its route exists), the pointer door routes to BookSettings, nothing disabled without its note (Tasks 9, 12).
5. **The 422 faces the drafts draw** — every refusal reason the states reference names arrives on the surface with its exact copy family; the save gate's refusal reaches the editor face (Task 12).

---

### Task 1: Stitch round — the hub chrome and both W8 authorities (gate — coordinator + Stitch + owner, no porting)

The round draws the shared settings chrome (section nav/cards) across **three** authorities: `settings-allgemein-2` gains only the chrome (content byte-stable), `settings-ai-rules-2` gains chrome, the BookSettings pointer door and the output-profile placement (Aufgaben), `ai-prompts-overrides` + `ai-prompts-states-reference` gain the app's exact tokens and the hub door. Archive over the existing files. Owner approves all before Task 2's porting starts (Tasks 2–7 need no draft and may run while the round is open).

### PR 1 — the opener (Tasks 2–7, one PR, each finding its own commit)

### Task 2: #933 — the locale race (PR)

**Files:** Modify `app/capabilities/settings/web/profileForm.tsx` (or SettingsPage.tsx — where the save assembles its body), `app/capabilities/writing/web/` GoalSetter; Test: the existing suites beside both.

**Interfaces:** the click-time fresh-cache read `queryClient.getQueryData(["settings", "read"])` at save time in both surfaces; the carried locale is the freshest known truth, never the rendered stalemate, never `null` over the GoalSetter outage gate. `Closes #933`.

### Task 3: The service/repository pins — #733, #734, #745, #750, #739 (PR)

Four test seams and a docstring, five commits: repository-level tests for `ProviderRepository.ordered/update` (`Closes #733`); the update services' copy list derived from the schema or pinned every-patchable-column-survives-a-patch, both services (`Closes #734`); the `_last_failure` projection's selected columns pinned (`Closes #745`); the delete-first/erase-second 503 path pinned — raise from `erase_key`, expect 503, row still listed (`Closes #750`); the presets module docstring names its refresh cadence (`Closes #739`).

### Task 4: #749 — drop the redundant index (PR)

**Files:** Modify `app/kernel/db/migrations/` (new revision) beside the composite index.

The single-column `ix_llm_calls_user_id` dies in its own revision (schema change rides the wave; `Closes #749`). The revision policy from the spec's constraints governs.

### Task 5: Driver kind — the read and the card's new basis (PR)

**Files:** Modify `app/capabilities/settings/router.py`, `schemas.py`, `service.py` (or tasks_service), `app/capabilities/settings/web/SettingsPage.tsx` + i18n catalogs; Test: settings API tests + the SettingsPage suite + the e2e leg that pins the offline card.

**Interfaces:** `GET /api/settings/driver` → `{kind}` — `"fake"` while every assignable task's serving tier is the fake adapter, else `"configured"`. The offline card reads this field instead of inferring across the task cascade; it stands only on `kind: "fake"`; hide-on-configured and hide-on-unanswered stay.

### Task 6: The drift fix — post-W7 truth (PR)

`ROADMAP.md` ("Where it stands", Phase 0/1) and `docs/features/INDEX.md` (settings rows) to the truth W7 left: the Allgemein surface is live, planning is closed, settings is half-done. Post-W8 truth is Task 13's.

### Task 7: PR 1 gate

`just verify` green on the touched suites; the PR ready; threads resolved; merge before anything in PR 2 starts.

### PR 2 — AI-Regeln (Tasks 8–10)

### Task 8: Output profiles — the backend build (PR)

**Files:** Modify `app/kernel/llm/` (vocabulary constants + resolution), `app/capabilities/settings/schemas.py`, `service.py`/`models_service.py`, the assignment PUT and tasks read paths, a migration defaulting `balanced`; Test: kernel resolution tests + settings service/API tests.

**Interfaces:** kernel-owned `OUTPUT_PROFILES = {"quick": 1024, "balanced": 4096, "long_texts": 12288, "comprehensive": 32768}`; assignment carries `output_profile` (absent/null = `balanced`, `custom` carries the number, bounded to a known ceiling at save); resolution `min(profile, ceiling)` at the LLM boundary, unknown ceiling uncapped; `GET /api/settings/tasks` answers profile name + resolved output per task.

### Task 9: The AI-Regeln surface (PR)

**Files:** Create `app/capabilities/settings/web/ai-rules/` (route `/settings/ai-regeln`, the three sections per the approved draft); Modify the settings hub chrome (Allgemein page gains chrome only), `web/lib/query.ts` seams (`useProviders`, `usePresets`, `useModels`, `useAssignments`, `useTasks`, `useDriver` — read the existing seams first), `web/components/IconRail.tsx`/`TopBar.tsx` only if the draft moves their doors; Test: the page suite + settings e2e legs (provider create with the key-once moment, model test faces, assignment with profile, the pointer door, the resolved number).

**Interfaces:** the sections consume only the endpoints the spec names; the pointer door routes to BookSettings (`Closes` nothing — it is the ruling-1 record); hub chrome in this PR carries Allgemein + KI-Regeln, no prompts item (no dead door).

### Task 10: PR 2 gate

`just verify` green; the settings capability's E2E green; PR ready, threads resolved, merge.

### PR 3 — Prompts (Tasks 11–14)

### Task 11: Preview + live test — the endpoints (PR)

**Files:** Modify `app/capabilities/prompts/router.py`, `schemas.py`, `service.py`; Create the context-assembly reuse per key (the capabilities' existing seams — writing continuation, chat, knowledge extraction/consistency); Modify `app/kernel/llm/` audit path if the task-key audit needs the seam named; Test: prompts API tests incl. SSE.

**Interfaces:** `GET /api/prompts/{key}/preview?novel_id=…` with optional body content (absent = saved effective) — sample scope, the save gate's sandbox, rendered text + variable provenance + diagnostics, no model call. `POST /api/prompts/{key}/live-test` — SSE after the chat/writing precedent; body carries the editor draft (absent = saved effective) which passes the sandbox before any provider call; rides the key's task assignment and the capability's **real** context assembly; kind `fake` answers locally with its honest mark; provider/secret-gated (named 502/503 faces); per-user in-memory rate limit; audited under the key's task; the streamed answer and the draft are never persisted. If an assembly reuse proves disproportionate, the fallback lands as a disclosed ledger row, never silently.

### Task 12: The prompts surface (PR)

**Files:** Create `app/capabilities/prompts/web/` (routes.tsx, PromptsPage.tsx, editor, i18n/{de,en,fr}.json), the hub chrome's third item; Create `app/capabilities/prompts/e2e/`; Modify the kernel expectation (SAME commit); Test: page suite + prompts e2e legs (list with override marks and novel filter, editor scope chips, diff, a 422 refusal face, preview, live test against the fake provider, chat.ask global-only).

**Interfaces:** consumes only the spec's endpoints; the states reference's refusal faces arrive with their exact copy family; the live-test warning precedes the call.

### Task 13: Gap ledger + index + post-W8 truth (PR)

`docs/design/stitch/gaps/2026-11-22-settings-ai-rules.md` (the round's retirements and omissions); the W8 index issue (`follow-up-index`) + the `docs/superpowers/follow-ups.md` row; surviving findings become child issues before merge; `ROADMAP.md` + `docs/features/INDEX.md` to post-W8 truth (settings and prompts live, Phase 1's settings/prompts items close).

### Task 14: Wave gate

`just verify`; the whole-branch review; the PR ready for the owner. PR für PR held across all three.
