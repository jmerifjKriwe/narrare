# Narrare v2 — Frontend Design

> **Status:** Accepted — product-owner approval 2026-10-22, builder check passed
> **Type:** Design spec for the web shell (decisions and consequences)
> **Authority:** implements the web frontend under the v2 architecture design
> (`2026-10-21-narrare-v2-architecture-design.md`, ADR-100), which stays the
> authority; where the two disagree, that document wins. This one governs the
> frontend.
> **Design dialogue:** this session, 2026-10-22; builder check by a fresh
> read-only reviewer against the repo (7 questions: 4 answered by the product
> owner, 3 settled in §7).

---

## 1. Intent and why

The v2 build has five capabilities (writing, knowledge, chat, setup, settings)
behind a thin one-route-per-capability UI: one shared component, ~8 design
tokens, hand-rolled `useState`/`useEffect` data flow. The product identity —
deep AI-assisted writing over a knowledge base — needs a frontend that makes
features cheap to add.

The v1 feature corpus (92 registered features) reduces to five recurring UI
patterns, and the frontend is organised around them:

- **AI proposes, the user decides** — suggestions, extraction, findings,
  drafts, merges are all the same review flow;
- **text anchors** — findings, suggestions and entity mentions attach to
  passages;
- **async jobs** — analysis, extraction, long generation outlive their request;
- **editor-embedded AI** — ghost text, rewrite of a selection, streaming;
- **docked context panels** — chat, knowledge, context inspection beside the
  text.

Priority decided with the product owner: **depth in writing and the knowledge
base first**; analysis, planning and canvas surfaces return later (spec §11).
Role model for stance (not for chrome): Papyrus 12 — the book is the unit, a
rich workbench beside the text, a real focus mode, manuscript-quality
typography.

## 2. Goals / Non-goals / Anti-goals

**Goals**

- Book-centric start page: continue-writing hero over a bookshelf.
- Workbench workspace: editor at the center, structure left, context docked
  right, everything collapsible down to text only.
- Capability-owned frontend folders, composed by a generated route table.
- Accessibility by construction (behaviour bought, not rebuilt).
- E2E-first testing, extended with mechanical accessibility checks.

**Non-goals (now; each returns per spec §11 on merit)**

- Graph/canvas surfaces (KB-008, KB-010, PLAN canvases), analysis reports,
  series/volumes UI, auth UI (deferred with the hosting model), a manual
  dark-mode toggle (system-following stays), a du/Sie formality switch.

**Anti-goals**

- Hand-written API types (generated client only).
- A capability importing another capability.
- A second design-token source.
- Mock-based tests as proof of function.
- Visual regression testing (the spec deleted it; it stays deleted).

## 3. Constraints (binding)

From the architecture spec and the standing rules:

- Capabilities never import capabilities. Shared UI lives in the shell
  (`web/`); shared domain lives in `kernel/`. Dependencies point one way.
- A capability is done only with a green E2E through the real UI, the real
  API and the real database; the only fake is the LLM provider at the
  boundary. No internal mocks.
- i18n: en/de/fr, framework-free central catalogs (`i18n/`), a missing key is
  a build error. A capability adds its keys to the three catalogs; that
  three-file touch is the accepted cost (spec §14).
- The TypeScript client is generated from OpenAPI (openapi-typescript +
  openapi-fetch). Zero hand-maintained API type modules.
- Governance budget: the route-table generator **extends** `scripts/generate`;
  it is not a new script, and this design adds no gate, registry, hook or
  mandatory document.
- No side effect in the request path beyond its transaction; durable work
  goes through `kernel/jobs` when it first exists (§5.6).

## 4. Approaches (decided in dialogue, with what each traded off)

| # | Decision | Chosen | Rejected — why |
|---|---|---|---|
| 1 | Structure | Capability `web/` folders + **generated route table** | Central `web/` subdivided by capability (a capability split across two trees; "delete = one folder" dies) · status quo one route file (breaks exactly at the depth now planned). Spec §14 named this trigger: capabilities owning many routes. |
| 2 | Component basis | **React Aria Components** behind a thin `ui/` layer | Radix (no ComboBox; would need cmdk/Downshift; less uniform across input modalities) · shadcn/ui (copy-in code with its own visual opinion; restyling effort fights token ownership). RAC is accessibility-first, headless, ships ComboBox/Autocomplete/GridList/Tree/Toolbar/Toast, German locale included. |
| 3 | Server state | **TanStack Query now** | Staying with hand-rolled hooks: multi-panel invalidation, job polling and post-stream cache updates are precisely the hand-rolled state v1 drifted on. Prove-it sentences go in the introducing PR (what it saves: the hand cache; what is smaller: nothing sensible). |
| 4 | Start page | **Continue-hero + bookshelf** | Shelf only (no task entry) · hero only (no book identity). |
| 5 | Workspace | **Workbench with progressive focus** | Pure editor + overlay drawers (the workbench is too far away when writing). |
| 6 | Editor tests | **Component tests, editor layer only** (real TipTap in Vitest + Testing Library, zero mocks) | E2E-only (TipTap interactions are slow and flaky through the full stack; E2E stays the done-proof regardless). |
| 7 | Dock composition | **Dock tabs are child routes of the workspace**, aggregated through the generated route table | A second generated contributions view (new `capability.yaml` fields; fails the "every field read by ≥2 views" rule) · shell hard-coding (third tab = generator work anyway). |
| 8 | `kernel/jobs` | **Built in the knowledge phase** — extraction is the durable side effect spec §13 names as the trigger | Extraction synchronous/in-stream (JobStatus would ship as an unprovable primitive). |
| 9 | Standalone pages | **`/chat` and `/knowledge` stay routes**; dock tabs mount the same components in novel context | Moving knowledge entirely into the workspace (upload unreachable outside a novel; existing flows and nav churn). |
| 10 | Backend scope | **Each phase ships its capability's backend** (one folder, OpenAPI, generated client) | Frontend-only phases against absent contracts (nothing to test E2E against). |

## 5. The design

### 5.1 Shell (`web/`)

- **Tokens:** the oklch set grows (focus ring, success, warning, panel
  surface, spacing/type scale). The shell owns tokens in `web/globals.css`;
  capabilities never carry palettes. Dark mode follows the system.
- **`ui/` layer:** thin wrappers (Button, Dialog, ComboBox, Tabs, Toolbar,
  Toast, GridList, …) over React Aria Components, styled via `data-*`
  attributes and tokens. Capabilities import UI primitives only from the
  shell. Swapping a primitive later stays cheap.
- **Root shell:** providers (QueryClient, i18n), skip-link, document title,
  and a proper top bar carrying the language control and the capability
  navigation rendered from the already-generated `capabilities.ts`.

### 5.2 Routing

`web/router.tsx` mounts a **generated route table** (`web/lib/generated/`,
DO-NOT-EDIT, named source) aggregating the route modules exported by
`app/capabilities/*/web/`. `React.lazy` per capability keeps bundles split.
TanStack Router's type registration stays, so a `to=` naming no route remains
a build error. The generator is an extension of `scripts/generate`.

### 5.3 Workspace (`/novels/$id`)

- Top bar (breadcrumb, capability nav, locale, focus toggle) · left rail:
  chapters (volumes later), collapsible · center: the editor · right dock,
  collapsible.
- Panel and collapse state lives in URL search params: linkable, back-button
  works.
- **Progressive focus:** F9 collapses dock and rail; the next step hides all
  chrome; only the text remains. Esc restores stepwise.
- **Keyboard contract:** Tab accepts ghost text, Esc discards it, F9 focuses,
  ⌘K opens the palette (entity search, commands, chapter jump). The palette is
  the one part not built; it lands with the coherence phase, and until then
  chapter and entity navigation have a pointer path only.
- **Autosave:** debounced PUT on typing pause and on navigation away; an
  unobtrusive save-state signal; no save button. Single-user last-write-wins
  is accepted for now.

### 5.4 Dock composition

The dock's tabs are **child routes of the workspace route**, aggregated
through the same generated route table as everything else — the one
composition point the architecture already has. No `capability.yaml` fields
are added; the shell hard-codes nothing.

### 5.5 Editor layer (`writing/web`)

TipTap stays. A decoration layer serves ghost text (inline AI suggestion),
text anchors (findings, entity mentions) and selection affordances (rewrite
toolbar). Streaming inserts at the caret; screen-reader announcements go
through `@react-aria/live-announcer`. The editor toolbar is an RAC Toolbar;
the editor itself gets an accessible role and label and is **not** a focus
trap (Tab leaves the surface per the keyboard contract). The editor engine
moves to the shell only when a second capability needs it (kernel rule).

Ghost text is a **new backend contract**: today `/continue` streams into the
chapter body and autosaves — the opposite of a tentative suggestion the user
accepts or discards.

### 5.6 Primitives (`ui/`) and jobs

- `ProposalCard` — the recurring "AI proposes, you decide" pattern
  (accept/reject/edit) behind suggestions, extraction, findings, drafts,
  merges.
- `JobStatus` — progress/result pattern, wired to `kernel/jobs`.
- Dock/Panel, EntityRef, the anchor-decoration API.

`kernel/jobs` (table + single worker, spec §9 D10) **is built in the
knowledge phase**: extraction over chapters and documents is the durable side
effect the spec names as its trigger, and it makes JobStatus provable in E2E
against real job state.

### 5.7 Start page (`/`, writing-owned)

A "continue where you left off" hero (last-touched novel/chapter) over a
bookshelf of novel cards with progress, plus the new-book affordance with
metadata (title, genre, blurb). Backend additions in the same phase:
`updated_at` on novels and chapters (the hero has no data source today) and
the metadata fields. Capability navigation lives in the top bar, not in the
page body.

### 5.8 Standalone routes stay

`/chat` and `/knowledge` remain destinations with their own flows (free-form
chat; document upload and semantic search). The dock tabs mount the same
capability components in novel context. Existing E2E flows and navigation
stay stable.

### 5.9 Knowledge depth (`knowledge/web`)

An entities surface (searchable list + detail; RAC GridList/ComboBox), an
extraction review queue built from `ProposalCard`, and the existing documents
and search integrated as the workspace dock tab "Wissen". Graph UI is
explicitly later. `kernel/jobs` + worker land here (§5.6).

### 5.10 Data layer

The generated client plus TanStack Query. Per-capability query-key
convention; invalidation after mutations; SSE streaming handled by a custom
hook outside Query, with the cache updated when the stream completes.

### 5.11 Accessibility and testing

- React Aria behaviour with token styling.
- **axe assertions in every E2E flow** — the accessibility baseline is
  checked mechanically, not claimed.
- **Keyboard-only variants of the main flows** — the same flows driven
  without a mouse; catches focus defects axe cannot see.
- **`announce()` content asserted** for ghost text and streaming, so AI
  offers are not invisible to screen readers.
- **One manual NVDA pass per main flow** — a practice recorded here, not a
  gate (axe finds only part of the truth).
- Component tests only for the editor layer (real TipTap, zero mocks) as the
  fast inner loop; unit tests for pure logic; E2E stays the definition of
  done. No VRT, no coverage threshold.

Product behaviour for the depth features comes from the v1 corpus files
(WRITE-007, KB-007, …), triaged per spec §11 at plan time; each phase ships
its capability backend (one folder, OpenAPI, generated client).

### 5.12 Settings (`/settings`)

Landed with WP2a (Fahrplan §5.9): `settings/web/routes.tsx` mounts `/settings`,
and the top bar's gear links to it (`nav: false` — it is a control, not a
browsing destination). Sections today: language, providers. The prompts section
and the ⌘K palette remain WP5's. It stays a capability (its HTTP surface
already is), so the generated route table and the one-way `@shell` import need
no exception.

## 6. Phasing (input for the implementation plan)

1. **Shell:** tokens + `ui/` layer + top bar + Query — no behaviour change;
   E2E green throughout.
2. **Routing restructure:** capability `web/` folders + generated route
   table; the five existing routes move; E2E selectors unchanged.
3. **Start page:** hero + shelf + metadata backend (`updated_at`, genre,
   blurb).
4. **Workspace:** workbench layout, URL panel state, progressive focus.
5. **Writing depth:** ghost-text backend contract, decoration layer, chat
   dock tab, `ProposalCard`.
6. **Knowledge depth:** entities, extraction review, `kernel/jobs` + worker,
   `JobStatus` wired.

The plan may reorder 3–4; each phase lands with its capability E2E green and
rewrites the E2E specs it changes behaviour for (in scope, not a regression).

## 7. Calls made by the designer (rejectable)

- **Desktop-first.** The phone is not a design target: no mobile layouts, no
  touch gestures. Every page must still not overflow horizontally at 360 px, and
  panels become overlays there. Checked by eye, not by a gate.
- E2E specs of behaviour-changing phases are rewritten as part of that phase.
- A dock flow is tested by the capability owning the feature (chat's `e2e/`
  drives the chat dock tab inside the workspace); the route owner provides
  preconditions.
- Esc layering (discard suggestion → step out of focus) is left to the
  builder.
- German copy uses **du**, fixed.
- Autosave is single-user last-write-wins, accepted until a second writer can
  exist.
- Dark mode follows the system only.

## 8. Explicitly left to the builder

Exact token additions within shell ownership · query-key naming details ·
editor engine file layout inside `writing/web` · the `ProposalCard` API shape
· how the ⌘K palette assembles generated nav and entity search · the TS/Vite/
Tailwind mechanics of moving TSX under `app/capabilities/*/web/`.
