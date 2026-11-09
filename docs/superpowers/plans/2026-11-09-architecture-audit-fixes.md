# Architecture audit fixes (2026-11-09)

**Status:** approved by the product owner 2026-11-09 (the two forks decided on the
audit page: mutation testing stays under a dated approval; the knowledge dock
address becomes English).
**Source:** the architecture audit of 2026-11-09 against
`docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`,
`docs/_shared/CONSTRAINTS.md`, and the dated designs. Findings F-1 to F-9.

## Global constraints

- The five standing rules in `docs/_shared/CONSTRAINTS.md` bind every change.
- Generated files are written by `just generate` and never edited by hand.
- English in code, tests and developer documentation; user-visible text in every
  catalog (en, de, fr), sorted, same keys.
- Conventional commits; `feat`/`fix` need a real `User-visible:` line. Nothing is
  committed before the review is green. A commit made through an agent ends with
  the trailer `Assisted-by: OpenCode (<model>)`.
- Gates: `CI=true just check`; the touched suites; `just test-file` for the inner
  loop. E2E runs with isolated ports: `NARRE_E2E_API_PORT=8199
  NARRE_E2E_WEB_PORT=3199 CI=true just test-e2e <scope>`.
- Do not touch the user's in-flight documents under `docs/superpowers/` that this
  plan does not name.

## Task 1 — Governance and documentation (F-1, F-2 scripts, F-3, F-9)

**Goal:** the record matches the tree; the two unwired helpers are gone; the two
web pre-commit hooks are one; the recipe count is honest.

**Exact changes**

1. Delete `scripts/check_doc_links.py` and `scripts/find_free_ports.py`. Neither is
   called by `justfile`, `.pre-commit-config.yaml`, or any workflow; `rg` proves it.
2. `.pre-commit-config.yaml`: replace the two hooks `web-typecheck` and `web-tests`
   with one hook `web` that runs both commands in order
   (`pnpm --dir web typecheck` and `pnpm --dir web exec vitest run --changed HEAD`),
   keeping `pass_filenames: false`, the same `files:` filter
   `(^web/|^app/capabilities/.*/web/|^i18n/)` and `stages: [pre-commit]`. Keep the
   behaviour the 2026-11-05 decision records ("web tests changed at commit, full at
   push"): `web-tests-full` at pre-push stays untouched. Update the neighbouring
   comments so they describe one hook, not two. The hook count drops 11 → 10.
3. `justfile` line 2: `# 25 public recipes;` → `# 27 public recipes;`.
4. `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md`:
   - §2 "Corrections and notes": add a dated bullet — mutation testing returned
     2026-11-09 as an advisory monthly sweep, approved on 2026-11-09, naming no
     context in `ci-required` and therefore not a gate; the §6 "Removed" line is
     corrected accordingly. Add/correct the recipe count to 27 (the list gains
     `check-generated`, `test-frontend-changed`, `fuzz`).
   - §6: the recipe list becomes 27 (add the three names in the same block) and the
     "24" in the prose becomes 27; the "Removed: ... mutation-testing ..." sentence
     keeps its history and gains the dated correction.
   - §14 "As built": six capabilities, not five — add `prompts` (WP4, approved
     2026-10-29); state that `kernel/prompts` is built with the override system
     (ADR-102 pattern), correcting the "not built" line; correct the recipe count.
5. `docs/superpowers/specs/2026-11-05-github-platform-design.md`: append an
   addendum dated 2026-11-09 that (a) records the mutation-testing approval with the
   three §8 statements verbatim, and (b) adds the missing workflow-map rows:
   `fuzz.yml` (scheduled security sweep, not a gate), `pins.yml` (the pin guard this
   design asked for), `mutation.yml` (approved 2026-11-09, advisory monthly).

The three §8 statements for the addendum, verbatim:

> 1. Failure it prevents: branch coverage proves a line ran, not that the assertion
>    would notice a wrong result. The sweep mutates `app/kernel` monthly and names
>    survivors — branches the tests execute without checking.
> 2. Effort per change: none. The workflow is advisory, monthly, and names no
>    context in `ci-required`; it costs one scheduled run plus triage of survivors as
>    ordinary findings.
> 3. Cheaper alternative: branch coverage already runs in the `tests` job; the
>    Hypothesis property tests from the same commit prove input spaces, not assertion
>    strength. Nothing cheaper proves "the test bites"; if one appears, the workflow
>    goes.

**Gates:** `CI=true just check`; `pre-commit validate-config`; `just --list` shows 27
recipes; `rg -n "check_doc_links|find_free_ports" .` returns nothing; the hook ids in
`.pre-commit-config.yaml` number 10.

**Commits**
- `chore(scripts): delete the two helpers no gate calls`
- `ci(hooks): merge the two web pre-commit hooks`
- `docs(architecture): record the mutation sweep, the recipe count and the as-built state`

## Task 2 — Generator conformance and the shell alias (F-4, F-8)

**Goal:** `nav` is read by two generated views and the python registry carries no
dead field; the writing route test uses the alias.

**Exact changes**

1. `scripts/generate_capabilities.py`:
   - Remove `title_key` and `in_nav` from the generated python registry (the
     `Capability` dataclass and its rows). Nothing reads them: `app/api/main.py` logs
     `id` and `needs` only, and `app/api/test_capability_views.py` parses
     `capability.yaml`, not the registry.
   - Add a `nav` column to the generated `docs/user/INDEX.md`: header key
     `docs.table.nav`, cell `✓` when `nav` is true and `—` otherwise. The header key
     comes from the merged catalog, like `docs.table.needs`.
2. `i18n/en.json`, `i18n/de.json`, `i18n/fr.json`: add `docs.table.nav` in sorted
   position (`en: "Navigation"`, `de: "Navigation"`, `fr: "Navigation"`). Keep the
   three catalogs key-identical and sorted.
3. `app/capabilities/writing/web/routes.test.ts`: import the shell through the alias
   — `@shell/router` and `@shell/lib/generated/workspace` — instead of
   `../../../../web/...`.

**Gates:** `just generate` (then `git status` shows only the intended regenerated
files); `just check-generated`; `uv run pytest app/api/test_capability_views.py -q`;
`CI=true pnpm --dir web exec vitest run app/capabilities/writing/web/routes.test.ts`.

**Commits**
- `refactor(tooling): give nav a second reader and drop dead registry fields`
- `refactor(writing): use the @shell alias in the route test`

## Task 3 — React-Aria behind the ui primitives (F-5, F-7)

**Goal:** `web/ui/` is the only React-Aria import point; the stale shell comment is
gone.

**Exact changes**

1. `web/ui/Dialog.tsx` (preferred) or a new `web/ui/` module: expose the overlay
   composition `Palette` needs (`ModalOverlay`, `Modal`, `Dialog`) behind a ui
   component/props. `web/components/Palette.tsx` then imports React-Aria only through
   `@shell/ui/*`; its markup, classes and behaviour stay identical.
2. Move the `@react-aria/live-announcer` import into `web/ui/liveAnnounce.ts` and make
   `web/lib/announce.ts` re-export from it, so the 11 existing consumers keep their
   import path.
3. `web/lib/api/client.ts`: replace the comment "One origin: the Next.js shell
   forwards /api to the FastAPI process." with a sentence true since ADR-101 (the
   Vite SPA is served by FastAPI; a relative `baseUrl` keeps `/api` on that origin).
   Sweep `web/` for other `Next.js`/`next build`/`next start` references and correct
   them if they describe the shell.

**Gates:** `CI=true just check`; `CI=true just test-frontend` (367 tests).

**Commits**
- `refactor(web): route React-Aria through the ui primitives`
- `docs(web): correct the client's shell comment`

## Task 4 — The knowledge dock's address (F-6)

**Goal:** the dock route and command speak English.

**Exact changes**

1. `app/capabilities/knowledge/web/routes.tsx`: the dock slug `wissen` → `knowledge`;
   update the comment above it.
2. `app/capabilities/knowledge/web/commands.ts`: command id `open-wissen-dock` →
   `open-knowledge-dock`; any path/description strings that carry `wissen`.
3. `app/capabilities/knowledge/web/EntitiesPanel.tsx`: deep links to
   `/novels/$id/wissen` → `/novels/$id/knowledge`.
4. `just generate` regenerates `web/lib/generated/docks.ts` (and anything else that
   carries the path).
5. Update every test that names the old address or command id:
   `web/components/Palette.test.tsx`, `web/lib/commands.test.tsx`,
   `app/capabilities/knowledge/web/EntitiesPanel.test.tsx`, and the E2E specs
   `app/capabilities/knowledge/e2e/test_knowledge_dock_e2e.py`,
   `app/capabilities/writing/e2e/test_shell_chrome_e2e.py`,
   `app/capabilities/writing/e2e/test_viewport_e2e.py`,
   `app/capabilities/writing/e2e/test_coherence_e2e.py`. Also sweep
   `rg -n "wissen" app web` — the only remaining hits outside `i18n/` and the demo
   data must be none.
6. No redirect: spec §1 records that there are no real users. The i18n label
   (`knowledge.dockTitle`) stays localized.

**Gates:** `just generate`; `CI=true just check`; `CI=true just test-frontend`;
E2E: `NARRE_E2E_API_PORT=8199 NARRE_E2E_WEB_PORT=3199 CI=true just test-e2e knowledge`
and the three named writing E2E files via `uv run pytest <path> -m e2e`.

**Commit**
- `fix(knowledge): the dock answers to an English address`
  with `User-visible: The knowledge dock lives at /novels/<id>/knowledge in every
  language; the old /novels/<id>/wissen address is gone.`
