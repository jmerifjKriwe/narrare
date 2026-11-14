# Frontend Rebuild — W2 (Welcome + Setup Assistant) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the welcome screen, the four-step setup assistant and the post-setup landing 1:1 from the archived Stitch drafts, with the real backend (settings columns and cover system already on this branch) and the setup capability's new E2E suite.

**Architecture:** The setup capability owns every route while the instance is unconfigured (`/` welcome, `/setup/*` wizard) and the landing at `/` once setup completed. The wizard posts one `POST /api/setup` call at the end (step 4), posting the accumulated answers; the response's provisioning facts render step 4's checklist and the landing. The cover preview uses the existing `web/lib/cover` system at size `wizard` (224×300).

**Tech Stack:** unchanged — Vite + React + TanStack Router + Tailwind v4 tokens, vitest, pytest + Playwright, `just` gates.

**Spec:** `docs/superpowers/specs/2026-11-13-frontend-rebuild-design.md` (program), `docs/design/stitch/screens/library/` (the ten W1 pairs + `cover-system.html`), `docs/superpowers/plans/2026-11-14-procedural-book-cover.md` (cover authority). The plan argues from them; executors read both.

## Global Constraints

- **No deferred findings, not even minors** (owner, 2026-11-14): every review finding is fixed inside its task's loop before the next task starts. Follow-up issues exist only for future-wave triggers (work this wave genuinely does not own); each names its trigger.
- Stitch alone designs: the drafts under `docs/design/stitch/screens/library/` are the 1:1 porting basis (`welcome-atelier`, `setup-step1-basis-vorlage`, `setup-step2-dramaturgie-struktur`, `setup-step3-ki-regeln-tonalitaet`, `setup-step4-bereitstellung-start`, `landing-atelier`, `setup-states-reference`, plus the dark variants and `cover-system`). No locally invented UI. Deviations go through a named-gap Stitch round before porting.
- Rule 5: user-visible text in en/de/fr catalogs, sorted, same keys; German is **du**-tone. Parameterized copy uses ICU; plural categories where the copy needs them.
- Honest values only: no invented numbers anywhere. The word target exists only on the blank path; step 4's facts come from the API response; the landing's progress bar carries the drafted honest label ("word count starts with the first writing"), not a percentage.
- Backend contract (already on the branch, binding): `POST /api/setup` accepts `novel_title` (required; the demo path sends the demo's title), `demo`, `genre` (single string, ≤80 — the pill multi-select joins with ", "), `target_words` (≥1), `author_typology` (`plotter|pantser|plantser`), `dramatic_form` (registry key: `three-act|heros-journey|save-the-cat|five-act|seven-point`), `ai_role` (`archivar|coautor|lektor|sparring`), `canon_strictness` (1–5). Demo semantics: the archive's title/genre/chapters win; the four settings bind onto the imported novel.
- The wizard's five form options are setup's own catalog copy (ids = the registry keys); no generated structures dependency (planning is UI-less until its wave).
- Agent models rev. 6: implementer/UI `qwencloud/qwen4-max-preview`, reviewer `zai-coding-plan/glm-5.3`, named in every dispatch.
- Commits: user-visible ports are `feat(setup)`/`feat(web)` with a real `User-visible:` line; infrastructure stays hidden (`chore`, `test`, `refactor`). Every commit: `git commit --trailer 'Assisted-by: OpenCode (<model>)'`. Rule 2: this wave ships the setup E2E suite.
- Folded in, not deferred (fix and close in this wave's tasks): #842 (generator raise + setup yaml comments), #843+#847 (i18n test floor, ICU pins), #845 (resolver dead code + sentinel), #846 (TESTING.md pointer), #849 (`shell.paletteOpen`), #850 (404 copy), #852+#853 (archive refresh — needs the owner's fresh Stitch export, the wave's precondition).

## Review Focus

1. **i18n parity and du-tone** — every key in all three catalogs, sorted; German copy never addresses the reader as Sie. Pinned by the vitest parity gates and the reviewer reading the German catalog diff.
2. **Demo semantics in the UI** — demo chosen: title/genre inputs disabled with the drafted lock note; POST carries the demo slug; the novel row keeps the archive identity and carries the four settings. Pinned by the E2E demo-path test asserting the landing's hero and (via the API) the persisted settings.
3. **Routing truth** — `/` renders welcome while `GET /api/setup/status` is incomplete, the landing once complete; the four wizard steps are addressable and survive refresh. Pinned by the E2E returning-visit test.
4. **Honest values** — no invented numbers: the reviewer diffs every rendered figure against either the drafts' honest labels or the API response fields. The gap doc records every disabled control.
5. **Cover integration** — the step-1 preview is `BookCover` at size `wizard`, updating live on title input, deterministic for identical input. Pinned by a vitest on the wiring (the cover system's own gates cover the component).

---

### Task 1: Archive refresh (precondition: owner's fresh Stitch export at `docs/design/stitch_narrare.zip`)

**Files:** `docs/design/stitch/screens/library/setup-step2-dramaturgie-struktur.{html,webp}`, `docs/design/stitch/README.md`

**Interfaces:** Produces the five-form step-2 draft (Save the Cat included) the Task 6 port reads.

- [ ] Replace the step-2 pair from the export (folder `projekt_setup_dramaturgie_struktur_korrigiert_narrare` unless the export names the edited screen differently — identify by content: contains „Save the Cat", lacks „12 Entitäten"); HTML verbatim, WebP q82 native.
- [ ] README: update the row's label/height; reword the two-era width sentence per #853 (one rule: native export size per era). Remove the zip.
- [ ] Verify: pair consistent (both five-form), README rows/links exact, nothing else changed.
- [ ] Commit `chore(docs): the step-2 draft gains its fifth form` — closes #852 and #853 (`Closes #852, closes #853` in the body).

### Task 2: SetupResult provisioning facts

**Files:** Modify `app/capabilities/setup/schemas.py`, `app/capabilities/setup/service.py`; test `app/capabilities/setup/tests/test_setup.py` (or wherever the service tests live — locate first).

**Interfaces:** Produces `SetupResult { novel_id, novel_title, genre, target_words, author_typology, dramatic_form, ai_role, canon_strictness, chapters }` — `chapters` is the count the import/creation produced (blank path: 0; demo path: the archive's chapter count), `genre` the effective genre (demo's own on the demo path).

- [ ] Failing service test: blank path returns chapters 0 and the passed settings; demo path returns the demo's chapters and its genre, the user's settings bound.
- [ ] Implement (service collects the facts it already has; no new queries).
- [ ] Run `just test-file <path>`; regenerate (`just generate` — the OpenAPI/typed client change) and commit `chore(setup): the setup result carries the provisioning facts` with the regen.

### Task 3: Routes — welcome gate and wizard steps

**Files:** Modify `app/capabilities/setup/web/routes.tsx`; create `app/capabilities/setup/web/useSetupStatus.ts` (+ test).

**Interfaces:** Produces routes `/` (status-gated: welcome vs landing), `/setup` (step 1, alias of `/setup/basis`), `/setup/structure`, `/setup/ai-rules`, `/setup/provisioning`. `useSetupStatus()` wraps `GET /api/setup/status` in a query (staleTime: once per load is enough) and exposes `{ complete, isLoading }`.

- [ ] Route table with lazy pages (placeholder components for now — the port tasks fill them); `/setup` redirects to `/setup/basis`; `/` renders welcome or landing per status (loading state honest: nothing invented, a bare suspension).
- [ ] Unit test (vitest): the gate's three states.
- [ ] `just check`, `just generate` clean; commit `chore(setup): the wizard owns its four addressable steps`.

### Task 4: Welcome page port

**Files:** Create `app/capabilities/setup/web/WelcomePage.tsx` (+ wiring test), i18n keys under `app/capabilities/setup/web/i18n/`.

**Interfaces:** Consumes `demos` from `@shell/lib/generated/demos`, `useTranslation`, the settings locale endpoint for the DE/EN/FR switcher. Produces the three entries: wizard start (→ `/setup/basis`), demo world (→ `/setup/basis` with the demo preselected — via search param `?demo=<slug>` the step-1 page reads), import (disabled + gap-doc entry).

- [ ] Port `welcome-atelier` 1:1 (hero, three cards, trust bar, quote); du-tone; the switcher writes locale through the existing settings API.
- [ ] Vitest: entries render, demo cards carry the three real demos, import button disabled with an honest note.
- [ ] Commit `feat(setup): the welcome screen returns in the drafts' voice` with a real `User-visible:` line.

### Task 5: Wizard step 1 — basis and template

**Files:** Create `app/capabilities/setup/web/steps/BasisStep.tsx` (+ test), shared `app/capabilities/setup/web/wizardState.ts` (+ test).

**Interfaces:** Produces `wizardState` — the accumulated answers `{ title, genrePills: string[], targetWords, typology, form, aiRole, canon, demo: string | null }` held in search-param-backed state (refresh-safe, no server writes until step 4). Consumes `BookCover` (size `wizard`).

- [ ] Port `setup-step1-basis-vorlage` 1:1: Tabula Rasa form (title field with live cover preview, five genre pills, target words), the three real demo cards (title/genre/blurb/chapters only — no stat chips), the selected-basis banner, the binding lock state from `setup-states-reference` panel 2, validation from panel 1 (empty title on blank path: error line + disabled continue).
- [ ] Genre pills join to the single string on submit (", "); demo preselection via `?demo=`; disabled title/genre with the drafted lock note when a demo is chosen.
- [ ] Vitest: live preview updates on title input; validation state; demo binding disables title/genre; continue enabled iff (demo chosen) or (title non-empty).
- [ ] Commit `feat(setup): step one asks how the work begins`.

### Task 6: Wizard step 2 — structure

**Files:** Create `app/capabilities/setup/web/steps/StructureStep.tsx` (+ test).

**Interfaces:** Consumes `wizardState`. Produces the five form options as setup catalog copy (ids are the registry keys) and the three typologies.

- [ ] Port `setup-step2-dramaturgie-struktur` (five-form version) 1:1: typology cards (plotter/pantser/plantser), five form cards (three-act with the „in Dead Signal vorkonfiguriert" hint only when the dead-signal demo is the basis — neutral otherwise), basis banner, honest status line from the corrected draft.
- [ ] Vitest: five forms render; typology+form selections persist in wizard state; back to step 1 keeps state.
- [ ] Commit `feat(setup): step two takes the work's dramaturgy`.

### Task 7: Wizard step 3 — AI partner and canon

**Files:** Create `app/capabilities/setup/web/steps/AiRulesStep.tsx` (+ test).

**Interfaces:** Consumes `wizardState`. Produces the four roles (ids `archivar|lektor|coautor|sparring` mapped to the drafted cards) and the five-stop canon slider (1–5, labeled per the draft).

- [ ] Port `setup-step3-ki-regeln-tonalitaet` 1:1 (four role cards with their meta lines, canon slider, the honest audit card — no entity examples).
- [ ] Vitest: role and canon selection persist; slider is keyboard-operable (a11y — the draft's control is a slider, not a visual bar).
- [ ] Commit `feat(setup): step three sets the partner's leash`.

### Task 8: Step 4 and the landing

**Files:** Create `app/capabilities/setup/web/steps/ProvisioningStep.tsx`, `app/capabilities/setup/web/LandingPage.tsx` (+ tests); modify `web/routes/__root.tsx` (404 copy, #850), `web/lib/i18n` fixture if the palette key falls (Task 9 owns the catalogs — this task only consumes).

**Interfaces:** Consumes `wizardState`, `client.POST("/api/setup", …)`, `SetupResult`. Produces the POST (one call, idempotence by the 409 path: a completed instance routes to the landing, never re-posts), the provisioning checklist from the response facts, the failure card (states-reference panel 4: retry re-posts, back returns to step 1 with state intact), and the landing at `/` (hero with `BookCover` at `hero` size, honest progress label, the two „neues beginnen" doors — wizard start and the three demo titles — the three coming-soon doors disabled with the drafted note, trust bar, quote).

- [ ] Port `setup-step4-bereitstellung-start` and `landing-atelier` 1:1; loading state from states-reference panel 3 during the POST.
- [ ] `__root` 404: `shell.notFoundBody` truthful for the interim (the way home is the landing — name it plainly); `nav.back` target is `/`.
- [ ] Vitest: checklist renders exactly the response's facts (chapters count, form label, role label); failure card retry path; landing doors.
- [ ] Commit `feat(setup): the wizard binds the book and the shelf welcomes you back` — closes #850 in the body.

### Task 9: Catalogs, test floor, gap doc (folds #843, #847, #849)

**Files:** `app/capabilities/setup/web/i18n/{en,de,fr}.json`, `i18n/{en,de,fr}.json`, `web/lib/i18n.test.ts`; create `docs/design/stitch/gaps/2026-11-14-welcome-setup.md`.

**Interfaces:** Produces the wave's gap doc (every disabled control and missing backend: element, draft value, interim render, trigger, follow-up issue) and the revived i18n test floor.

- [ ] Complete all three catalogs for the ported copy (sorted, same keys, du-tone, ICU where parameterized — at minimum the step counters and the chapters count).
- [ ] Revive the vacuous tests (#843): the overlay test asserts on real overlay-bearing copy or is deleted with a named reason in the report; the placeholder-name drift is renamed; the fallback-surface pin (catalog-worded 404/error) gets a real vitest again.
- [ ] Restore the ICU pins (#847): apostrophe-before-placeholder quoting and the link-count split, asserted on the new parameterized copy.
- [ ] `shell.paletteOpen` (#849): no palette in this wave — drop the key and pin parameterized rendering on live wizard copy.
- [ ] Gap doc entries: import button (trigger: the import wave), the three landing coming-soon doors (trigger: their waves), step-4's „Entitäten-Graph öffnen" secondary (no knowledge UI yet — disabled, trigger: knowledge wave).
- [ ] `just test-frontend` green; commit `feat(setup): the wizard speaks three catalogs and keeps honest books` + `chore(docs): the wave's gap ledger` (two commits).

### Task 10: Generator and resolver fold-ins (#842, #845, #846)

**Files:** `scripts/generate_capabilities.py`, `app/capabilities/setup/capability.yaml`, `scripts/affected.py`, `app/kernel/tests/test_affected.py`, `TESTING.md`.

- [ ] #842: with setup's real title key in its catalogs, restore the `facts()` raise for web-owning capabilities (unresolvable title key stops generation) and make `setup/capability.yaml`'s comments true again; regenerate; the INDEX row for setup returns.
- [ ] #845: `sorted(known) or None` → `sorted(known)` in both branches; the suiteless-interim sentinel test is rewritten for the suite-exists world (setup's suite exists from Task 11 — order this task after Task 11's first green run, or adjust: the sentinel asserts setup's suite is discovered).
- [ ] #846: TESTING.md's data-and-fixtures bullet names the setup conftest again.
- [ ] `just test-file app/kernel/tests/test_affected.py` green; `just generate` clean; commit `chore(gates): the generator and resolver rearm as the first suite returns`.

### Task 11: Setup E2E suite

**Files:** Create `app/capabilities/setup/e2e/conftest.py`, `app/capabilities/setup/e2e/test_setup_e2e.py`.

**Interfaces:** Consumes the real stack (per-suite database, ports via the kernel stack; locale contexts repeat `de-DE` per the repo's E2E convention). Produces the wave's rule-2 gate.

- [ ] Specs: (a) welcome renders with the three real demos, import disabled; (b) blank path: title/genre/target/typology/form/role/canon → provisioning checklist shows the facts → landing hero shows the novel; the persisted novel row carries all four settings (assert via API or DB); (c) demo path: demo card → title/genre locked → POST → landing hero shows the demo's own title/genre, settings bound; (d) validation: empty title blocks continue with the drafted message; (e) returning visit: `/` shows the landing; deep-link `/setup/provisioning` mid-wizard keeps state.
- [ ] `just test-e2e setup` green; `just verify` read green end to end.
- [ ] Commit `test(setup): the wizard drives the real stack end to end`.

### Task 12: Wave gate and PR

- [ ] `just verify` (all legs read); the wave's findings all fixed (none parked — the no-deferral rule); the gap doc complete.
- [ ] Push, open the PR: plain-language title (e.g. "Rebuild the welcome screen and setup assistant from the Stitch drafts"), body links spec, both plans, the closed issues (#842–#850 as applicable, #852, #853), and the gap doc.
