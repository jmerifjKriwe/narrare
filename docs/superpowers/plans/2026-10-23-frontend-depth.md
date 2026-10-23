# Frontend Depth Implementation Plan (spec §6, phase 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The editor AI contract — ghost-text continuation with Tab/Esc, live-region announcements, the chat dock tab composed through the generated route table, and the ProposalCard primitive with its first real consumer.

**Architecture:** Recon against the code proves `POST /chapters/{id}/continue` is already side-effect-free SSE (spec D14; the persistence was always the frontend's insert + autosave, never the endpoint) — so ghost text is purely an editor-layer change: the stream renders as a tentative decoration, Tab commits it (autosave then persists), Esc discards it. The dock resolves the phase-1/2 design flag: capabilities export `dockRoutes`, the **generated route table** nests them under writing's exported `workspaceRoute` — capabilities still never import each other, composition stays in generated code. A shell-owned proposal bus lets the chat dock offer text into the editor as a ghost without a capability import. Phase 6 (knowledge depth, `kernel/jobs`) is a separate plan.

**Tech Stack:** as before + `@react-aria/live-announcer` (announce) + `@testing-library/react`/`jsdom` (first editor component tests — real TipTap, zero mocks).

**Spec:** `docs/superpowers/specs/2026-10-22-frontend-design.md` — §5.3 (keyboard contract), §5.4 (dock composition), §5.5 (editor layer), §5.6 (ProposalCard), §5.11 (announce assertions), §6 phase 5.

**Base:** branch `frontend-foundation` @ f7614510. Execute on a new branch `frontend-depth` from it.

## Global Constraints

- English in code, comments, tests, commits. User-visible text only through `i18n/{en,de,fr}.json`, all three together; German du-form.
- Capabilities never import capabilities; shell imports capability code only through the generated table; RAC is imported only in `web/ui/`.
- Route contract: `routes = […] as const`; **validateSearch parsers must be tolerant** (the router delivers `?rail=0` as NUMBER `0` — string-only literals never fire); **search writes use the function form** `(prev) => ({ …prev, key })`.
- Esc layering seam (built in phase 4): the editor marks its Esc handled; `NovelPage`'s window handler stands down on `event.defaultPrevented`. Ghost-text Esc never steps focus; focus Esc never discards a ghost (there is none at that moment by construction).
- `@tiptap/react` strips `editorProps` attributes `@tiptap/core` injects — editor attributes go in the React binding's props, not core's.
- Chapter writes invalidate `["novels"]` (the convention landed in 07b91098 — new write paths keep it).
- E2E = real UI, real API, real Postgres; fake only at the LLM/embeddings boundary; `assert_accessible(page)` ends every flow. Component tests exist ONLY for the editor layer (real TipTap, zero mocks).
- Editor component tests are new test class in this repo: Vitest + @testing-library/react + jsdom, `web/` scope, run by `just test-frontend`.
- No new scripts/gates; the dock parenting extends `scripts/generate_capabilities.py`. Generated files keep the DO-NOT-EDIT header.
- Conventional commits; `feat`/`fix` carry a real `User-visible:` line; `--no-verify` forbidden; `just` recipes only.

## Review Focus

1. **Accept persists, discard does not** — the one data-integrity line of the ghost contract: Tab → reload shows the text; Esc → reload shows it absent. Pinned by the rewritten continuation E2E (Task 1).
2. **Esc layering both directions** — ghost present: Esc discards, focus depth unchanged; ghost absent: Esc steps focus, nothing discarded. Pinned in Task 1's E2E (both orders in one flow).
3. **Stream/autosave interleaving** — a suggestion completing while an autosave PUT is in flight must not corrupt either: ghost is decoration (not document) until Tab; the accept path inserts then lets the debounced autosave persist. Pinned by component test (accept during in-flight save) + E2E.
4. **Dock state is URL truth** — `?dock=chat` renders the tab open, back-button closes it, dock writes never clobber `rail`/`focus` (function form). Pinned in Task 2's E2E.
5. **Proposal bus has no ghosts after navigation** — an offer made in the dock must not resurrect when the user leaves the novel and returns. Pinned in Task 3's E2E (offer → navigate away → back → no ghost).

---

### Task 1: Editor ghost-text layer — the AI contract at the caret

**Files:**
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx` (decoration plugin, ghost state, Tab/Esc keymap, `announce` on ghost appear/accept/discard; attributes per the strip-carry rule)
- Create: `web/lib/announce.ts` (thin re-export/wrapper around `@react-aria/live-announcer`'s `announce`, so the shell owns the live-region policy)
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (`continueWriting` now feeds the ghost, not the document; keyboard-edge guard carry `if (event.repeat || event.isComposing) return`)
- Create: `app/capabilities/writing/web/ChapterEditor.test.tsx` (component tests)
- Modify: `web/package.json` (+`@react-aria/live-announcer`, dev: `@testing-library/react`, `@testing-library/user-event`, `jsdom`; vitest jsdom environment for this file)
- Test: rewrite `app/capabilities/writing/e2e/test_continuation_e2e.py`; add unmount-at-depth-2 carry test in `test_focus_e2e.py`

**Interfaces:**
- Consumes: the existing `/chapters/{id}/continue` SSE (`delta` frames via `web/lib/stream.ts`), `useAutosave`, the phase-4 Esc seam.
- Produces: `ChapterEditor` prop `proposal?: string | null` + `onProposalResolve(accepted: boolean)` (Task 3's bus drives the same props); the editor's ghost lifecycle = arrive → `announce(t("editor.ghostArrived"))` → Tab (insert at caret, `announce(t("editor.ghostAccepted"))`, autosave persists) or Esc (drop, `announce(t("editor.ghostDiscarded"))`).
- Produces: `web/lib/announce.ts` exporting `announce(text: string)`.

- [ ] **Step 1: Component tests first (red)** — `ChapterEditor.test.tsx`: (a) ghost text renders decoratively (present in DOM, NOT in `editor.getText()`); (b) Tab accepts (text now in `editor.getText()`); (c) Esc discards (absent everywhere); (d) accept during in-flight autosave does not lose text. Run red.
- [ ] **Step 2: Implement** the plugin (a ProseMirror decoration on the caret position keyed by a plugin state; NO document mutation until accept), the keymap (Tab/Esc only when a ghost exists; `preventDefault` + `stopPropagation` on handled Esc — the seam), `announce` wiring, the `NovelPage` feed change, the keyboard-edge carry.
- [ ] **Step 3: Green component tests**, then rewrite the E2E red→green: Weiterschreiben → ghost visible → Tab → reload shows text; fresh flow → Esc → reload shows absence; Esc-order assertions (ghost Esc leaves focus depth at 0; then F9 → Esc works). Plus the unmount-at-depth-2 carry test. `assert_accessible` everywhere.
- [ ] **Step 4: Full gates** — `just typecheck && just test-frontend && just test-e2e`.
- [ ] **Step 5: Commit**

```
feat(web): ghost-text continuation — the editor's AI contract

The continuation stream renders as tentative decoration at the caret:
Tab commits it (autosave persists), Esc discards it, and a live region
announces each transition. The window Esc handler stands down when the
editor marks its key handled, so focus stepping and ghost discarding
never fight. First editor component tests (real TipTap, zero mocks).

User-visible: Weiterschreiben now proposes instead of overwriting —
the text is yours only when you take it.
```

### Task 2: Dock parenting through the generated table — chat beside the text

**Files:**
- Modify: `app/capabilities/writing/web/routes.tsx` (export `workspaceRoute = novelRoute` — the convention name the generator looks for; `validateSearch` gains `dock`: `"chat"|"none"|undefined → "chat"|"none"` tolerant)
- Create: `app/capabilities/chat/web/dock.tsx` (dock panel: the ask/answer flow extracted from `ChatPage.tsx`, reused — extract shared pieces into `app/capabilities/chat/web/ChatPanel.tsx` and have both pages use it)
- Modify: `app/capabilities/chat/web/routes.tsx` (add `dockRoutes = [chatDockRoute] as const`, path `"chat"` under the workspace → `/novels/$id/chat`)
- Modify: `scripts/generate_capabilities.py` (nest every capability's `dockRoutes` under the exported `workspaceRoute` via `addChildren` in the generated file; deterministic order; DO-NOT-EDIT header notes the convention)
- Modify: `app/capabilities/writing/web/NovelPage.tsx` (right dock area: tab surface rendering the matched dock child route via `<Outlet/>`; `?dock=chat` opens, `"none"`/absent collapses; function-form writes)
- Modify: `i18n/{en,de,fr}.json` (`workspace.dockChat`, `workspace.dockClose` or equivalent)
- Test: `app/capabilities/chat/e2e/test_chat_e2e.py` (dock flows; standalone `/chat` tests untouched)

**Interfaces:**
- Produces: the **dock convention** — a capability exports `dockRoutes = […] as const`; exactly one capability exports `workspaceRoute`; the generated table nests them. Phase 6's knowledge dock (`"wissen"`) mounts the same way, no generator change.
- Produces: `validateSearch` now parses `{ rail, focus, dock }` — all tolerant, all optional.

- [ ] **Step 1: Failing E2E** — in the novel workspace: `?dock=chat` shows the chat panel beside the editor; ask a question, streamed answer arrives (reuse existing fixtures); back-button closes the dock; `rail=false&focus=1` survive a dock toggle (URL truth). Run red.
- [ ] **Step 2: Implement** the convention (workspaceRoute export, dockRoutes, generator nesting), the dock area with `<Outlet/>`, the shared `ChatPanel`. Regenerate (`just generate`), drift-check clean.
- [ ] **Step 3: Green** — chat dock tests + full suite (`/chat` standalone untouched and green), typecheck, build.
- [ ] **Step 4: Commit**

```
feat(web): chat dock beside the editor, composed by the generated table

Dock tabs are child routes of the workspace: writing exports
workspaceRoute, chat exports dockRoutes, and the generator nests
them — capabilities still never import each other. The open dock
lives in the URL beside rail and focus.

User-visible: the chat sits beside your text while you write; it is
a URL state, shareable like everything else in the workspace.
```

### Task 3: ProposalCard and the proposal bus — the review primitive lands

**Files:**
- Create: `web/ui/ProposalCard.tsx` (`ProposalCard({ titleKey, body, onAccept, onDiscard, children? })` — RAC, the accept/reject/edit pattern of §5.6)
- Create: `web/lib/proposal.ts` (`offerProposal(text: string)`, `subscribeProposal(cb)` — shell-owned bus; single pending offer, last-wins, cleared on resolve)
- Modify: `app/capabilities/chat/web/ChatPanel.tsx` (a completed answer renders „Als Variante übernehmen" → `ProposalCard` → accept calls `offerProposal(answer)`)
- Modify: `app/capabilities/writing/web/ChapterEditor.tsx` (subscribes: a bus offer renders as a ghost at the caret — same Tab/Esc/announce lifecycle as Task 1, via the Task-1 props)
- Modify: `web/globals.css` (scrim/shadow tokens — carry: first overlay consumer since the dialog)
- Carries (same commit): `NovelsPage` create-failure behavior (dialog stays open, new `novels.errorCreate` key, RAC validation on Titel); `aria-multiline="true"` on the editor; `Date.parse` compares replacing `updated_at` string compares in `NovelsPage`/`NovelPage`; query.ts comment fold.
- Test: `app/capabilities/chat/e2e/test_chat_e2e.py` (proposal flow), `app/capabilities/writing/e2e/test_novels_e2e.py` (create-failure stays open)

**Interfaces:**
- Consumes: Task 1's `proposal`/`onProposalResolve` props; Task 2's dock.
- Produces: `ProposalCard` (phase 6's extraction review builds on it); the proposal bus (any dock surface offers text into the editor without a capability import).

- [ ] **Step 1: Failing E2E** — dock chat → answer → „Als Variante übernehmen" → ghost appears in the editor (announced) → Tab → persisted after reload; navigate-away variant: offer → leave novel → back → no ghost. Create-failure: dialog stays open, `novels.errorCreate` shown, Titel intact. Run red.
- [ ] **Step 2: Implement** bus + card + wiring + carries.
- [ ] **Step 3: Green** — full suite, typecheck, build.
- [ ] **Step 4: Commit**

```
feat(web): proposal cards — AI offers, the editor decides

The ProposalCard primitive lands with its first consumer: a chat
answer can be offered into the editor as ghost text through a
shell-owned bus, accepted with Tab, discarded with Esc. Same
pattern, phase 6's extraction review will reuse. Carries: create
failure keeps the dialog open with its own message; scrim tokens;
aria-multiline; Date.parse timestamp compares.

User-visible: a chat answer can become a proposal in your text —
never inserted without your keypress.
```

---

## Self-review notes

Spec coverage: §5.5 editor layer — ghost/decoration/announce/Tab-Esc in Task 1; selection-rewrite toolbar and multi-draft NOT in §6's phase-5 list, recorded as deliberate deferral (return with the editor-toolbar work, where the §3-scope note expects the spacing/type-scale tokens' first consumer). §5.4 dock composition → Task 2 (design flag RESOLVED: generated-table parenting — `workspaceRoute`/`dockRoutes` conventions; rejected: parent-by-route-id (unverified router API risk, coupling via string ids) and shell-owned layout route (workspace chrome is writing's product logic, not the shell's)). §5.6 ProposalCard → Task 3 with a real consumer. §5.11 announce assertions → Task 1 E2E asserts live-region text. Backend: recon proves `/continue` already side-effect-free SSE — the plan's "ghost-text backend contract" is a frontend commit policy, no new endpoint (plan correction against spec §6 wording, evidence: router.py:124-140 + service read-only; the spec is the authority on goals, the plan on means). Phases 1–4 carries placed: keyboard-edge guard + unmount test (Task 1), Date.parse/aria-multiline/query-comment (Task 3), scrim tokens (Task 3), dialog create-failure (Task 3), `?dock` encoding documented via Task 2's validateSearch. Proportion: three tasks, each one reviewable seam.
