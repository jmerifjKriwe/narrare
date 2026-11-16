# Frontend Rebuild — W3 (Bücherregal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The full library shelf at `/` — ported 1:1 from the five archived shelf drafts, replacing the W2 landing as the set-up home surface — with EVERYTHING REAL: status, series, archive and activity tracking in the backend, duplicate/export/search/filter working, and the new-book flow as the owner-picked minimal dialog.

**Architecture:** The writing capability owns `/` (its capability.yaml path, restored); the setup capability keeps `/setup/*` and gains the welcome surface at `/setup` (pre-setup `/` redirects there). The shelf reads the existing novels list (server-side word_count), the new activity aggregate, and the cover system at size `shelf` (144×200; hero cards `hero`). New backend: series table, status/archived_at/volume columns, a daily word-count tracking table fed by chapter create/update/delete diffs, and a duplicate endpoint.

**Tech Stack:** unchanged — FastAPI + SQLAlchemy async + Alembic, Vite + React + TanStack Router + Tailwind v4 tokens, vitest, pytest + Playwright.

**Spec:** `docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md` (program). Drafts (read-first authority): `docs/design/stitch/screens/library/{shelf,shelf-dark,shelf-empty,shelf-states,shelf-filter-open,landing-atelier}.html` + the new-book dialog `Neues Buch anlegen — Der schnelle Weg (Dialog)` (Stitch resource `44b3da2d06bd4b64a7a04af664be09a4` — export rides the wave-start zip). Cover authority: `web/lib/cover/` + `cover-system.html`.

## Owner decisions binding this wave (2026-11-15)

- The shelf REPLACES the landing at `/` (landing's content becomes the shelf's one-book state).
- New book = the DIALOG variant (title, genre pills, target words; typology/AI-role/canon inherit from the atelier defaults with the drafted note; the full wizard stays one-shot).
- EVERYTHING REAL: status, series, archive, activity tracking (streak, goal progress, weekly average, sparkline) are backend-real in this wave — honest neutral renders only where data legitimately doesn't exist yet (activity fills as chapters change; the workspace wave multiplies it).

## Global Constraints

- No deferred findings, any severity — fixed in the task's loop (wave rule since W2).
- Stitch alone designs; drafts are the 1:1 authority; deviations through named-gap rounds; honest values only (no invented numbers — the drafts' populated states are MOCK; the port renders real data in the drafted geometry, with the shelf-states draft governing loading/error/many-books/long-title states).
- Rule 5: en/de/fr catalogs, sorted, same keys, du-tone. Rule 2: the writing capability's E2E suite ships this wave. Rule 4: every new user-owned row carries user_id.
- Models rev. 6: implementer/UI `qwencloud/qwen4-max-preview`, reviewer `zai-coding-plan/glm-5.3`, named per dispatch.
- Conventional commits: `feat(writing)`/`feat(setup)` with real `User-visible:` lines; backend/tooling hidden types; `Assisted-by` trailer everywhere.
- The pre-push/verify gates run the now-two e2e suites (setup + writing).

## Review Focus

1. **Route handover** — `/` is the shelf post-setup, redirects pre-setup to `/setup` (welcome); no capability imports another (composition only through the generated table); the setup E2E's expectations update for the welcome's new home. Pinned by both suites.
2. **Activity derivation** — the tracking table's diffs are written by the chapter write path (create/update/delete), and the aggregate (streak, weekly average, goal progress, sparkline points) derives from it — no double counting, no negative days, per-run isolated. Pinned by backend tests + an E2E that writes chapters through the API and sees the banner move.
3. **Honest values on real data** — every rendered figure traces to a row (word_count, target_words, chapter counts, updated_at) or a documented neutral; the drafts' mock numbers never ship. Reviewer diff-checks figures against API output.
4. **Destructive/irreversible actions** — archive (reversible toggle), duplicate (new novel + chapters copy), export (existing engine): confirm states per the drafted menu, honest busy/error handling. Pinned by E2E + vitest.
5. **Catalog whole** — writing capability catalogs NEW; parity across all three; the shared catalog only grows what the shell truly renders. Pinned by the parity gates + whole review.

---

### Task 1: Wave-start archive refresh (precondition: owner's fresh Stitch export at `docs/design/stitch_narrare.zip`)

- Extract the new-book dialog draft (`..._dialog_...` folder — identify by content: „Atelier-Einstellungen" note + „Anlegen") into `screens/library/new-book-dialog.{html,webp}`; README row; delete zip. Sanity markers before placing (three fields, the inheritance note, no wizard stepper).

### Task 2: Backend — series, status, archive columns + models (TDD)

**Files:** `app/kernel/contracts/novel.py` (+ `series.py` if cleaner), migration `db-revision`, `app/capabilities/writing/{schemas,service,repository}.py`, tests.
**Interfaces (produces):** `Series(id, user_id, title, created_at)`; `Novel.status: str|None` (vocabulary `draft|revision|final` — validated at the service boundary; the UI pill maps `draft`→„Entwurf" etc.), `Novel.series_id: UUID|None`, `Novel.series_volume: int|None`, `Novel.archived_at: datetime|None`. `NovelRead` grows `status`, `series_title`, `series_volume`, `archived_at`, `chapter_count`; `NovelUpdate` accepts the settable fields (status validated; archived_at as bool-clearable timestamp). List supports `include_archived` (default: archived books out of the main grid).

### Task 3: Backend — duplicate endpoint (TDD)

- `POST /api/writing/novels/{id}/duplicate` → new novel (title `„<Titel> (Kopie)"`, same genre/target/settings/status-not-archived, series link copied, volume NULL) + full chapter copy (titles, bodies, positions) in one transaction; response is the new `NovelRead`. Tests: content equality, position preservation, user scoping (404 on foreign), archive NOT copied.

### Task 4: Backend — activity tracking + aggregate (TDD)

**Files:** `DailyWords(novel_id, date, words)` table (user-owned via novel), write-path hooks in the writing service's chapter create/update/delete (diff of whitespace-word counts), `GET /api/writing/activity?days=30` → `{ points: [{date, words}], streak_days, weekly_average, today_words }` derived across the user's novels (atelier-level, as the drafted banner).
- Diffs computed from the OLD body before the update lands; deletes count negative; same-day upserts accumulate. Tests: create→update→delete sequences net correctly; streak over consecutive days incl. today/yesterday boundary; the aggregate never counts another user's rows.

### Task 5: Frontend — route handover

- writing's `web/routes.tsx`: `homeRoute` at `/` → ShelfPage (placeholder first); `beforeLoad` (or the page's status query) redirects incomplete instances to `/setup`. Setup's routes: welcome moves to `/setup` (the gate at `/` is removed; `/setup` renders Welcome pre-setup, redirects to `/` when already set up — the inverse gate); wizard steps unchanged under `/setup/*`. capability.yaml paths corrected (writing `/`, setup `/setup`) + regenerate. Both E2E suites' expectations updated. Catalogs untouched where possible (copy moves are mechanical).

### Task 6: Shelf page port (1:1 from `shelf.html`, states from `shelf-states`, empty from `shelf-empty`)

- Hero card (the latest-edited novel: cover at `hero` size, title/genre/chapters/words `48.342 / 65.000`-shaped from REAL `word_count`/`target_words` — target absent → the honest neutral bar label from the landing), grid of the rest (`shelf` covers, genre pill, chapter count, tabular word figures, status pill from `status`, last-edited from `updated_at`), primary actions `+ Neues Buch anlegen` (→ Task 9's dialog) and import (disabled, gap row carries). Loading/error/many-books/long-title states per `shelf-states`. Dark via tokens (draft `shelf-dark` reference).

### Task 7: Search + filter popover port (from `shelf` + `shelf-filter-open`)

- Client-side over the loaded list (single user): title/genre/figure search (titles + genres + figures — the W2 gap row „search matches titles only" resolves here), filter popover with genre facets (derived from real genres), status facet, `Archiv einbeziehen` toggle (drives `include_archived`). All real, all drafted geometry.

### Task 8: Quick menu port (duplicate / export / archive)

- The drafted per-book menu: Duplizieren (Task 3, busy + honest error), Exportieren (existing export flow — read the API's export result handling from pre-W0 history if the UI shape is needed; download the artifact), Archivieren (toggle with drafted confirm wording; unarchive from the archive view). i18n + vitest for each action's busy/error/confirm states.

### Task 9: New-book dialog port (from the picked Stitch draft, Task 1's archive pair)

- Modal over the scrimmed shelf, live cover preview (`wizard` size), three fields (title required — validation language from step 1's established pattern; five genre pills multi-select joined ", " with the 80-char cap; target words default 65000 with format category), the inheritance note verbatim, `Anlegen` → `POST /api/writing/novels` → optimistic grid insert with refetch, `Abbrechen`. The dialog's answers do NOT write wizard settings (inheritance is the note's truth — settings stay the atelier's).

### Task 10: Activity banner + streak port

- The drafted banner: goal progress (atelier target = active novel's target? Pin: the hero novel's target_words — disclose), weekly average, sparkline (30 points from the aggregate), streak chip; all from `GET /api/writing/activity`; honest neutral states when the table is empty („Der erste Schreibtag beginnt mit dem ersten Kapitel"-class copy — drafted tone, no invented values).

### Task 11: i18n catalogs + gap-doc updates

- Writing capability catalogs (en/de/fr, sorted, parity, du-tone) for everything above; shared catalog only for shell chrome if truly shared. Gap doc `2026-11-14-welcome-setup.md` rows that THIS wave makes real close from the commits (`Closes` lines where rows map); a W3 gap doc opens with the wave's own rows (status setter UI → workspace wave, series editing UI → planning/workspace wave, import door → import wave, wizard-settings-per-book → workspace wave).

### Task 12: Writing E2E suite (rule 2)

- `app/capabilities/writing/e2e/`: shelf renders real data (seeded via API), search/filter facets, duplicate (content equality on the grid), export (artifact lands), archive toggle + archive view, new-book dialog end-to-end (create → grid grows → word stand neutral), activity moves after API-written chapters (banner + streak), pre-setup `/` → `/setup` welcome redirect, dark-mode shelf face. de-DE contexts; two workers max; per-suite DB.

### Task 13: Wave gate + PR

- `just verify` green (both suites), gap doc complete, findings all fixed; push, PR (plain title, e.g. "Rebuild the library shelf from the Stitch drafts, with real activity tracking"), body links spec/plan/decisions/closed rows.
