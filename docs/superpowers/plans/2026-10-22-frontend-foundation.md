# Frontend Foundation Implementation Plan (spec §6, phases 1–2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the web-shell foundation — Query provider, top bar with skip-link, mechanical axe checks, and capability-owned `web/` folders composed by a generated route table — with every existing E2E selector unchanged and green throughout.

**Architecture:** Phase 1 hardens the shell without behaviour change (TanStack Query enters with its first real consumer, the root locale fetch). Phase 2 moves each capability's routes into `app/capabilities/<id>/web/`, extends `scripts/generate_capabilities.py` to emit a generated route table, and leaves `web/router.tsx` mounting only generated routes. Capabilities import the shell (one-way), never each other.

**Tech Stack:** Vite SPA · React 19 · TanStack Router (code-based, typed) · TanStack Query · Tailwind 4 tokens · pytest + Playwright E2E · axe-core.

**Spec:** `docs/superpowers/specs/2026-10-22-frontend-design.md` — the plan argues from it; executors read both.

**Scope:** spec §6 phases 1–2 only. Phases 3–6 (start page, workspace, writing depth, knowledge depth) get their own plans, one per phase pair, after this lands.

## Global Constraints

- English in code, comments, tests, commit messages. User-visible text only through the i18n catalogs `i18n/{en,de,fr}.json`; a missing key in any locale is a build error (all three files change together).
- A capability never imports another capability; capabilities import the shell via the `@shell/*` alias; the shell never imports capability code except the generated table.
- Generated files carry the `DO NOT EDIT` header naming their source, same style as `web/lib/generated/capabilities.ts`.
- No new scripts, gates, hooks or registries: the route table extends `scripts/generate_capabilities.py` (spec §3, governance budget).
- E2E = real UI, real API, real Postgres via the `stack` fixture; the only fake is the LLM/embeddings vendor at the boundary. No internal mocks.
- Existing E2E selectors (German labels like `Anlegen`, `Titel`) must keep passing unchanged; only `assert_accessible(page)` lines may be added to existing tests.
- No `--no-verify`, no force push. Conventional commits; `feat`/`fix` carry a real `User-visible:` line.
- Web deps via `pnpm --dir web add …`; the command surface stays the 21 `just` recipes.
- `Route` below means the TanStack Router route type from `@tanstack/react-router`.

## Review Focus

1. **Keyboard order after the top bar lands:** tabbing must reach the skip-link first and jump focus to `main` — pinned by the skip-link test in Task 2.
2. **Tailwind not scanning moved capability files** (utilities silently absent, page renders unstyled): pinned by the computed-style assertion in Task 4's chat E2E.
3. **Lazy route + Query provider remount losing user state on locale switch:** pinned by the chat conversation-persistence test in Task 4.
4. **axe helper passing vacuously when the script never loaded:** pinned by the fault-injection probe in Task 3 (helper must fail when axe did not run).
5. **Generated route table drift** (capability folder exists, table stale): pinned by the regenerate-and-diff-empty step in Task 6.

---

### Task 1: TanStack Query enters with its first consumer (root locale fetch)

**Files:**
- Modify: `web/package.json` (add `@tanstack/react-query`)
- Create: `web/lib/query.ts`
- Modify: `web/routes/__root.tsx` (provider + `useSettingsQuery` replaces the hand-rolled effect)
- Modify: `web/main.tsx` (mount `QueryClientProvider`)

**Interfaces:**
- Produces: `web/lib/query.ts` exports `queryClient: QueryClient` (defaults: `retry: false` — a local service is either up or the page reports the outage itself; `staleTime: 30_000`) and `useSettingsQuery(): UseQueryResult<{ locale: string | null }>` (query key `["settings"]`, fetch via `client.GET("/api/settings")`, returns `data?.locale ?? null` on ok, `null` on error — same contract the effect had).

- [ ] **Step 1: Install and wire the provider**

Run: `pnpm --dir web add @tanstack/react-query`
Then: `main.tsx` wraps the router in `<QueryClientProvider client={queryClient}>`; no other change.

- [ ] **Step 2: Migrate the root locale fetch to `useSettingsQuery`**

Replace the `useEffect` block in `Shell` (`__root.tsx:78-96`) with the hook; `adoptServerLocale(locale)` + `setReady(true)` behave exactly as before (server answer or `null` on outage).

- [ ] **Step 3: Verify**

Run: `just typecheck && just test-frontend && just test-e2e`
Expected: typecheck clean, unit tests pass, all 9 E2E green (selectors untouched).

- [ ] **Step 4: Commit with the prove-it sentences**

```
feat(web): adopt TanStack Query for the root locale fetch

Prove-it (spec §4.3): saves the hand-rolled load/cancel/adopt effect and
every future panel's copy of it; costs one dependency (~13 kB) and one
mental model; the smaller alternative — hand-rolled hooks per surface —
is the multi-panel invalidation drift v1 died of.

User-visible: none — behaviour identical, the page still waits for the
stored locale before first paint.
```

### Task 2: Top bar, skip-link, shell tokens

**Files:**
- Modify: `web/globals.css` (add tokens `--focus`, `--success`, `--warning`, `--panel`, light + dark values in the existing oklch families; map them in `@theme inline`)
- Create: `web/components/TopBar.tsx`
- Modify: `web/routes/__root.tsx` (render `<TopBar />`, add the skip-link as the first focusable element, wrap `<Outlet/>` in `<main id="main">`; remove the fixed-position language block)
- Test: `app/capabilities/settings/e2e/test_settings_e2e.py`

**Interfaces:**
- Consumes: `nav` from `@shell/lib/generated/capabilities`, `LanguageSwitcher` logic (moves into `TopBar` unchanged: native `<select>`, optimistic `applyLocale`, revert + `role="alert"` on refusal), `useTranslation`, `locales`, `catalogs`.
- Produces: `TopBar` renders `<header>` with: skip-link (`<a href="#main" class="…">{t("shell.skipToContent")}</a>`, visible on focus, styled with `--focus` ring), nav links (existing `nav` entries, `Link to={entry.path}`), language `<select>` with its existing `<label>`/`id="locale"` contract.

- [ ] **Step 1: Write the failing E2E**

In `test_settings_e2e.py` add:

```python
def test_skip_link_jumps_to_main_content(page: Page, stack: Stack) -> None:
    page.goto("http://127.0.0.1:3100/")
    body = page.locator("body")
    body.press("Tab")                       # first Tab reaches the skip link
    expect(page.getByRole("link", name="Zum Inhalt springen")).to_be_focused()
    body.press("Enter")
    expect(page.locator("#main")).to_be_focused()
```

plus the i18n key `shell.skipToContent` in all three catalogs (`de`: „Zum Inhalt springen", `en`: „Skip to content", `fr`: „Aller au contenu").

- [ ] **Step 2: Run it to verify it fails**

Run: `just test-file app/capabilities/settings/e2e/test_settings_e2e.py`
Expected: FAIL — no link with that name exists.

- [ ] **Step 3: Implement tokens + `TopBar` + root restructure** per Interfaces; every interactive element in the top bar gets the `focus-visible` ring on `--focus`.

- [ ] **Step 4: Run the full suite**

Run: `just test-e2e`
Expected: all green including the new test; existing selectors (e.g. `get_by_label` on the locale select) unchanged.

- [ ] **Step 5: Commit**

```
feat(web): top bar with capability nav, language control and skip link

User-visible: a proper top bar replaces the fixed corner language
control; keyboard users get a skip link straight to the content.
```

### Task 3: axe in every E2E flow, proved bidirectional

**Files:**
- Modify: `web/package.json` (devDependency `axe-core`)
- Create: `app/kernel/testing/a11y.py`
- Modify: all five `app/capabilities/*/e2e/test_*.py` (one `assert_accessible(page)` line at the end of each test function, after the flow's own assertions)

**Interfaces:**
- Produces: `assert_accessible(page: Page) -> None` in `app/kernel/testing/a11y.py` — injects `web/node_modules/axe-core/axe.min.js` via `page.add_script_tag(path=…)`, runs `axe.run(document.body)` scoped to WCAG A/AA rules, and **fails the test** when: any violation is reported, the script did not load (missing file → `Fail` with the path), or the evaluate did not execute (empty result → `Fail`, never a silent pass).

- [ ] **Step 1: Write the helper + apply it to all nine tests**

Add the import and one call per test in: `settings`, `chat`, `setup`, `knowledge`, `writing` (3 files) e2e tests. No other change to existing tests.

- [ ] **Step 2: Probe that the check actually catches a violation (then revert)**

Temporarily inject `page.evaluate("() => { const i = document.createElement('img'); i.src='x'; document.body.append(i); }")` before one call — an image without alt text.
Run: `just test-file app/capabilities/chat/e2e/test_chat_e2e.py`
Expected: FAIL naming the img rule. Then remove the injection.
Run again: PASS. (A check that cannot fail protects nothing.)

- [ ] **Step 3: Full suite**

Run: `just test-e2e`
Expected: all 9 green with assertions active.

- [ ] **Step 4: Commit**

```
test(e2e): mechanical accessibility assertions in every flow

axe-core injected from web/node_modules; the helper fails on violations,
on a missing script file and on a vacuous run. Fault-probe evidence in
the task report.
```

### Task 4: Route table generator + chat moves first (build wiring included)

**Files:**
- Modify: `web/tsconfig.json` (`include` adds `"../app/capabilities/*/web/**/*.ts"`, `"../app/capabilities/*/web/**/*.tsx"`; `paths` adds `"@shell/*": ["./*"]`)
- Modify: `web/vite.config.ts` (`resolve.alias` `"@shell"` → the `web/` dir, so the alias resolves identically in dev, build and typecheck)
- Create: `app/capabilities/chat/web/routes.tsx`, `app/capabilities/chat/web/ChatPage.tsx` (moved from `web/routes/chat.tsx`)
- Modify: `scripts/generate_capabilities.py` (new output `web/lib/generated/routes.ts`)
- Create (generated): `web/lib/generated/routes.ts`
- Modify: `web/router.tsx`, `web/routes/__root.tsx` (Suspense boundary around `<Outlet/>`)
- Test: `app/capabilities/chat/e2e/test_chat_e2e.py`

**Interfaces:**
- Produces: the **capability route contract** — `app/capabilities/<id>/web/routes.tsx` exports `export const routes: Route[]`, each built with `getParentRoute: () => rootRoute` imported as `import { rootRoute } from "@shell/routes/__root"`; page components load through `React.lazy` so each capability stays a bundle split. First instance: chat.
- Produces: `web/lib/generated/routes.ts` — `DO NOT EDIT` header naming `scripts/generate_capabilities.py`; imports each `app/capabilities/*/web/routes.tsx` it finds (folders without one, e.g. `settings`, are simply absent) and exports `export const capabilityRoutes: Route[]` (flattened, folder order).
- Produces: `web/router.tsx` mounts `rootRoute.addChildren([...capabilityRoutes, /* hand-listed until Task 6 */])`.

- [ ] **Step 1: Write the two failing E2E checks**

Append to `test_chat_e2e.py`:

```python
def test_chat_styling_survives_the_move(page: Page, stack: Stack, tmp_path: Path) -> None:
    # ...upload + ask flow as in the existing test...
    bg = page.get_by_role("button", name="Senden").evaluate(
        "el => getComputedStyle(el).backgroundColor")
    assert bg not in ("", "rgba(0, 0, 0, 0)")   # Tailwind scanned the moved file

def test_conversation_survives_a_locale_switch(page: Page, stack: Stack, tmp_path: Path) -> None:
    # ...ask something, then switch the locale via the top bar select...
    # the streamed answer must still be on screen afterwards
```

(Exact German label strings for the chat flow come from `i18n/de.json` keys `chat.*`; reuse the existing test's setup verbatim.)

- [ ] **Step 2: Run to verify they fail**

Run: `just test-file app/capabilities/chat/e2e/test_chat_e2e.py`
Expected: FAIL — chat route still lives at the old path; the new assertions cannot pass until the move.

- [ ] **Step 3: Wiring, generator, move**

tsconfig + vite alias; move `chat.tsx` to `app/capabilities/chat/web/` (page component in `ChatPage.tsx`, lazy-loaded; route def in `routes.tsx` per contract); extend `generate_capabilities.py`'s output dict with the routes table; regenerate; mount in `router.tsx`; delete `web/routes/chat.tsx`; Suspense boundary in the shell root.

- [ ] **Step 4: Verify**

Run: `just generate && just typecheck && just build && just test-file app/capabilities/chat/e2e/test_chat_e2e.py && just test-e2e`
Expected: regeneration clean, build splits a chat chunk, chat tests green (old selector assertions untouched), full suite green.

- [ ] **Step 5: Commit**

```
refactor(web): capability-owned routes behind a generated route table

Chat moves first as the proving slice; knowledge/setup/writing follow.
The generator only extends scripts/generate_capabilities.py (governance
budget). @shell alias: capabilities import the shell, never each other.

User-visible: none — same routes, same labels, now code-split per
capability.
```

### Task 5: knowledge and setup move

**Files:**
- Create: `app/capabilities/knowledge/web/{routes.tsx,KnowledgePage.tsx}` (from `web/routes/knowledge.tsx`)
- Create: `app/capabilities/setup/web/{routes.tsx,SetupPage.tsx}` (from `web/routes/setup.tsx`)
- Modify: `web/router.tsx` (hand list shrinks to writing's two routes)
- Modify: `scripts/generate_capabilities.py` only if the scan needed it (it should not — that is the point)

- [ ] **Step 1: Move both routes per the Task 4 contract**

Same recipe: page component lazy, `routes.tsx` exporting `Route[]`, delete the old `web/routes/` files, regenerate, mount.

- [ ] **Step 2: Verify**

Run: `just generate && just typecheck && just build && just test-e2e`
Expected: generated table now lists chat, knowledge, setup; all suites green with selectors unchanged.

- [ ] **Step 3: Commit**

```
refactor(web): move knowledge and setup routes into their capabilities

User-visible: none.
```

### Task 6: writing moves; the shell mounts only generated routes

**Files:**
- Create: `app/capabilities/writing/web/routes.tsx` (`indexRoute` + `novelRoute`), `app/capabilities/writing/web/{NovelsPage.tsx,NovelPage.tsx}`
- Create: `app/capabilities/writing/web/ChapterEditor.tsx` (moved from `web/components/ChapterEditor.tsx`)
- Modify: `web/router.tsx` (mounts only `capabilityRoutes`; the hand list is gone)
- Modify: `web/components/` (empty after the move — the directory goes)
- Modify: `app/capabilities/writing/e2e/*` (nothing but `assert_accessible` already added in Task 3)

- [ ] **Step 1: Move writing's routes and editor per the contract**

`indexRoute` at `/` and `novelRoute` at `/novels/$id` both into `writing/web/routes.tsx`; pages lazy; `ChapterEditor` imports switch to `@shell/lib/…` where they touched `web/lib`.

- [ ] **Step 2: Verify selectors unchanged and the table is stable**

Run: `just generate && git diff --exit-code web/lib/generated/routes.ts` (regeneration is a no-op — no drift)
Run: `just typecheck && just build && just test-e2e && just verify`
Expected: clean diff, build green, all E2E green (writing suite's German selectors `Anlegen`, `Neues Kapitel` untouched), full gate passes.

- [ ] **Step 3: Commit**

```
refactor(web): writing owns its routes; shell mounts only the generated table

User-visible: none — phase 2 of the frontend design is complete: a
capability's frontend lives in its folder, composed by
scripts/generate_capabilities.py.
```

---

## Self-review notes

Spec coverage (phases 1–2): tokens (5.1) → Task 2; `ui/` layer primitives deferred to their first real consumer (phase 3+ surfaces) — YAGNI, and the spec's component-test rule gives them no test home earlier; top bar + skip link (5.1) → Task 2; Query (4.3, 5.10) → Task 1; generated route table (5.2) → Tasks 4–6; dock child-routes (5.4) arrive with the workspace plan; axe/keyboard/announce (5.11): axe → Task 3, keyboard-only flow variants and `announce()` assertions arrive with the surfaces that have keyboard contracts (workspace/editor plans). Settings has no route to move — correct: its surface is the top bar. Proportion: six tasks, each independently rejectable, each landing with the suite green.
