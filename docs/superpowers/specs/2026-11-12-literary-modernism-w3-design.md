# Literary Modernism — W3: the writing workspace

> **Status:** Draft for approval
> **Type:** Design spec for the writing capability's workspace surface
> **Authority:** implements on top of the
> [v2 architecture design](2026-10-21-narrare-v2-architecture-design.md) (ADR-100),
> the [frontend design](2026-10-22-frontend-design.md), and the
> [Literary Modernism umbrella spec](2026-11-11-literary-modernism-frontend-design.md)
> (§6.5, §6.6, §8). Supersedes only the *visual* treatment of the workspace; the
> command-focus norm's architecture (Platz-Atlas, single-active dock, canvas routes,
> palette, AI patterns, focus rings, forced-colors) stands.
> **Norm for values:** `docs/design/stitch/DESIGN.md` and
> `docs/design/stitch/screens/writing/workspace*.webp` / `zen-focus.webp`.
> **Origin:** owner decision 2026-11-12 — W3 is the next wave after the shelf pilot.

---

## 1. Intent and why

The shelf pilot proved the system: tokens, chrome primitives, and one real surface
indistinguishable from its draft. The workspace is where the user actually writes —
the surface that has to feel like a book, not like an admin panel. W3 brings the
workspace, the chapter rail, the editor card, the floating prompt bar, ghost text,
and zen focus onto the drafted composition, at the same 1:1 fidelity the shelf held.

Nothing architectural moves: the rail/editor/dock anatomy, the focus depths (F9
deepens, Esc releases), autosave, ghost text, the slash palette, the leave guard,
and the dock registry all stay as the command-focus norm fixed them. W3 is
re-tokening and re-composing what is already there, plus the drafted widgets that
have no backend yet — handled honestly, like the shelf's missing data.

## 2. Goals, non-goals, anti-goals

**Goals**

- G1 — The workspace *is* `screens/writing/workspace`: rail, editor card, floating
  prompt bar, ghost-text keycap, running head, folio, page marker, drop cap, zen
  focus, session stats and story arc render as drafted, 1:1.
- G1a — The shell chrome the draft shows is completed in W3 (owner decision
  2026-11-12): the icon rail's book-switcher, sync-status dot, theme toggle and
  user block ship drafted, and the side-by-side gate judges them with the
  workspace surface. The dock *contents* stay W4.
- G2 — Theme intact: every new surface carries `light-dark()` pairs already in
  `globals.css`; no new palette enters except through shell tokens.
- G3 — Fidelity gate: an E2E screenshot of `/novels/$id` next to
  `workspace.webp` (and `zen-focus.webp` for the focus state) in the PR.
- G4 — Gates green: `just check`, the writing suites, axe AA in both themes, the
  writing E2E.

**Non-goals** (later waves or separate work)

- Dock *contents* (consistency-finding card, entity spotlight, scene-mood grid,
  cover miniature) stay in the knowledge/chat capabilities and ship in W4 — W3
  delivers the dock frame and chrome only (already W1).
- New backend features: no streak/goal/version/pagination/scene data is added in
  W3. Missing fields render honestly (interim) and become follow-up issues.
- Re-routing, re-composing or re-architecting anything (routes, docks, canvas,
  palette, AI patterns unchanged).
- The draft's other workspace variants (`workspace-ai-dock`, `workspace-lore-dock`,
  `workspace-continued-manuscript`, `workspace-aria-dialogue`,
  `workspace-chapter-2-nevada-echoes`) are states of this surface, not separate
  pages; only the base `workspace` and `zen-focus` are fidelity targets for W3.
  The others inform details (running head, ghost text, dialogue insertion) where
  they show states the base does not.

**Anti-goals**

- A mix of old neutral and new parchment tokens anywhere in the workspace.
- Invented widgets, values or states no draft shows; gaps go to Stitch or to a
  follow-up issue, never to imagination.
- German-only copy: draft labels inform `de`; `en`/`fr` follow by translation.

## 3. Constraints

- Shell owns tokens (`web/globals.css`); capabilities carry utilities only.
- UI work by subagents (implementer + reviewer per task), whole-branch review at
  the end; model preference per AGENTS.md.
- i18n rule 5, a11y gates, E2E-green definition of done apply.
- The focus-depth contract is inviolable: F9 deepens (0→1→2), Esc releases
  (2→1→0); at depth 2 only the writing surface remains. Ghost text owns Esc
  first when a ghost is pending.
- Autosave, ghost text, slash palette, leave guard, chapter CRUD and reorder keep
  their behaviour; W3 changes presentation, not semantics.
- Interim fields live in code beside the element they hide, referencing their
  follow-up issue number, exactly as the shelf's `shelf/` files do.

## 4. Approaches considered

| Approach | Verdict |
|---|---|
| **A — One wave, one plan, one PR** (chosen): all W3 surfaces together, task groups pushed after each green group, one side-by-side fidelity gate at the end. | Matches the pilot's cadence and the AGENTS.md push rule; the fidelity gate needs the whole surface present. |
| B — Split into W3a (rail + editor core) and W3b (prompt bar, zen, ghost text). | Smaller PRs, but the side-by-side gate cannot be split honestly and the second half would re-touch the first. |
| C — Composition-only, no new widgets. | Rejected: leaves the draft's distinctive elements (drop cap, running head, prompt bar, story arc) unbuilt, which is what makes this wave worth doing. |

Dock contents are deferred to W4 (decided): W3 ships the dock frame/chrome only.

## 5. Surface map

### 5.0 Shell chrome (shared components — W3 completes it)

The draft's icon rail carries four blocks W1 did not build (owner decision
2026-11-12: they ship in W3, inside the fidelity gate):

- **Book-switcher** at the rail's head: the active novel's cover chip + name,
  `unfold_more` opens a menu of the user's novels (`useNovelsQuery` — real data)
  and navigates. Below it the rail nav keeps W1's drafting.
- **Sync-status dot** with "Sync Online" label in the rail's foot: derived from
  the autosave state (saved = online, pending/failed = its own state) — real
  data, no follow-up.
- **Theme toggle**: cycles system/light/dark, the same tri-state the settings
  row owns (real).
- **User block**: avatar chip + name + tier line from the user row; the author
  name may be null — the block then names the user row's own label (real).

These live in `web/components/IconRail.tsx`/`TopBar.tsx`, so their tests and the
a11y legs widen with them; no capability boundary moves.

### 5.1 Top bar (WorkspaceToolbar + topbar band)

- Breadcrumb `Manuscripts / <book>` with the book title in `text-emph`.
- Save state with the success dot ("Gespeichert", amber focus on the dot).
- Live word count chip (Σ of the book's chapters, derived — real data).
- Language chip (EN/DE/FR).
- Right cluster: focus toggle (F9), history (renders disabled — no capability
  yet, follow-up), export — as drafted, 28 px dense buttons.
- Save state and the card-foot autosave line render from the **same** `status`
  value (one owner, no drift); the top bar's chip is the `SaveIndicator`'s drafted
  look, the card foot names the timestamp the autosave state already carries.
- The editor ribbon's mono chapter badge ("KAP-01") is derived from the chapter's
  position, zero-padded, with the prefix from the i18n catalogs (de `KAP`, en/fr
  `CH`) — never a hard-coded string.
- Paper running head: `book — author`; when `author` is null the head names the
  book alone (no trailing dash).
- Target-progress pill ("Kapitel-Ziel: 765 / 1.000 Wörter" + bar) — interim: hidden
  until a per-chapter target exists (shared with shelf follow-up #783); the pill's
  slot stays empty rather than showing a fake number.

### 5.2 Chapter rail (ChapterRail)

- Meta header card: eyebrow "Projekt-Gliederung" (area-writing), "Entwurf v2.4"
  badge (neutral — no version field yet), chapter count + total words (derived).
- Tabs "Kapitel" / "Szenen & Plot": Kapitel is active; Szenen tab renders an empty
  state linking to planning (interim) until scenes exist — the link targets the
  active novel's planning surface with the novel param, exact route from
  `routes.tsx`.
- Chapter rows: drag handle, eyebrow "Kapitel 0N", word count (right, tabular),
  title (`text-emph`, truncate with full `aria-label`), status dot + status line
  ("Szenen-Fokus: …" / "In Überarbeitung" / "Erster Entwurf"). Status is interim:
  "Erster Entwurf" for every chapter until a status field exists (shared with shelf
  #784).
- "Neues Kapitel hinzufügen" button (full width, dense).
- Story-arc SVG widget (area-writing gradient, current-chapter marker) — interim:
  static placeholder curve until planning data exists.
- Session-stats card at the rail foot ("Schreibsitzung heute", words, goal bar,
  percentage) — interim: neutral (no session tracking yet); shows "—" where no
  number exists, never a fake one.

### 5.3 Editor card (ChapterEditor)

- Runhead above the card: `book · title input` (left, `text-emph` 600) and save
  state + actions (right) — already exists; retune to the drafted geometry (11 px
  eyebrow spacing, 1 px rule).
- "Weiterschreiben" primary button above the card (already exists) — keep as the
  trigger; the floating prompt bar (§5.4) is the *additional* affordance.
- Paper card: already `rounded-[--radius-surface]` with border + focus ring; add the
  drafted running head (book — author, folio "FOLIO 12") at the top and the page
  bottom marker ("Seite 1 von 8", autosave dot) at the foot. Both are interim:
  folio and page count render only when pagination exists; otherwise the running
  head shows book — author and the foot shows the autosave state only.
- Chapter headline: eyebrow "Kapitel Eins" (area-writing, tracked) — the ordinal
  is **written out as drafted** (owner decision 2026-11-12): a small locale-aware
  number-words util covers en/de/fr (one–ninety-nine is enough for a chapter
  count; beyond it the util falls back to digits and a note names the bound),
  title in EB Garamond (`prose-heading-1`), 1 px sepia rule beneath.
- Drop cap on the first paragraph (CSS `first-letter`, as drafted).
- Ghost text: italic, area-writing/70, with the `[Tab] Vorschlag übernehmen`
  keycap pill (already have Keycap from W1; reuse).
- Footer: word count + position "n von m" (already exists, tabular).

### 5.4 Floating prompt bar

- Sticky bottom bar: context trigger ("Stil: Schattiert & Bedrohlich"), inline
  prompt input, "Weiterschreiben" primary button (terracotta pill), and quick-prompt
  pills ("⚡ Spannungsspitze einbauen", etc.).
- Context trigger and quick pills are interim: the trigger shows a neutral "Stil:
  —" until style presets exist. The inline input and the quick-prompt pills render
  but stay **disabled** — the continuation endpoint takes no prompt parameter, and
  a control that looks like it sends one would lie. Their follow-up issue names
  the prompt parameter as its trigger.
- The bar reuses the existing continuation endpoint; only the UI moves.

### 5.5 Zen focus (focus depth 2)

- At depth 2 the rail and dock are already hidden; W3 re-skins the remaining
  surface to `zen-focus.webp`: centered paper, no top bar, the focus hint line
  ("Esc zum Zurückkehren"), the ghost text keycap still reachable.
- No new state machine; only presentation.

### 5.6 What W3 does *not* touch

- Dock contents (W4). Chapter CRUD, reorder, autosave, ghost text logic, slash
  palette, leave guard, focus-depth keybindings — behaviour unchanged.
- `NovelsPage` / shelf (W2, done).

## 6. Missing data (interim + follow-up)

One index issue (label `follow-up-index`) filed at W3's opening, one child per row
below (label `follow-up` + `area: writing`), plus the shared shelf children where
a field already has an issue (#783 target, #784 status). Each interim lives in code
beside the element, ending in its child number.

| Drafted field | Interim logic | Follow-up |
|---|---|---|
| "Entwurf v2.4" badge | neutral "Entwurf" | new issue |
| Chapter status dot/line | "Erster Entwurf" for every chapter | #784 (shared) |
| Chapter target bar in topbar | hidden until field exists | #783 (shared) |
| Story-arc SVG | static placeholder curve | new issue |
| Session stats (today's words/goal/%) | neutral "—" | new issue |
| Kapitel/Szenen tabs (Szenen) | empty state → planning | new issue |
| Running head folio ("FOLIO 12") | omitted until pagination | new issue |
| Page bottom marker ("Seite 1 von 8") | omitted until pagination | new issue (or same as folio) |
| Floating bar context trigger | "Stil: —" | new issue |
| Floating bar prompt input | renders, disabled (no prompt param on the endpoint) | new issue |
| Quick-prompt pills | render, disabled — they are prompts, and the endpoint takes none | shares the input's issue |
| History button in the top bar | renders, disabled (no version-history capability) | new issue |
| "KAP-01" chapter-code badge | derived from position, prefix from the catalogs | none |
| Book word count chip | derived (Σ word_count) | none — real data |
| Chapter count/total words in rail header | derived | none — real data |

Dock contents (consistency, entity, scene mood, cover miniature) are not interim
here — they are W4's surfaces and carry their own follow-ups there.

## 7. Verification

- `just check` (fast) after each task group.
- `just test-file` on every touched test.
- `just verify` (full) before the PR.
- Writing E2E suite green (including focus, autosave, continuation, interchange).
- axe AA in both themes on the workspace route (existing E2E axe leg).
- Fidelity: E2E screenshot of `/novels/$id` (and the focus-depth-2 state) next to
  `workspace.webp` / `zen-focus.webp`, plus a re-shot master frame in
  `assets/screenshots/`.
- `/design` gallery unaffected (already on the new tokens).

## 8. Left to the builder

- Exact component/file edits, task order, class strings, i18n keys, E2E updates.
- The number-words util for the chapter eyebrow (en/de/fr, bound, fallback).
- Story-arc and session-stats interim rendering: hidden vs. neutral card.
  Recommend a neutral card with "—" so the layout matches the draft.
- Task count and grouping for the plan (writing-plans).

## Decisions (owner, 2026-11-12)

- **D-1** — Shell chrome completes in W3 (G1a); the gate judges shell + surface.
- **D-2** — Both bars stay: global `TopBar` as W1 shipped it, the workspace band
  becomes the drafted editor ribbon. **Superseded 2026-11-13** by the Shelf fidelity
  repair (owner): the drafted `TopBar` ships shell-wide and owns the shell facts
  (breadcrumb, save chip, word count, language) on every route; the workspace band
  loses its duplicated left cluster and keeps only the workbench controls. See
  `specs/2026-11-13-shelf-fidelity-design.md` §5.1/§5.8, decision D-5.
- **D-3** — Chapter eyebrow written out ("Kapitel Eins"), locale number words.
- **D-4** — Floating prompt bar input and pills render disabled + one follow-up
  issue naming the prompt parameter as its trigger.

## My calls (settled without the owner — check while reading)

- Prompt input/pills, history button: disabled, each with a follow-up row (§6).
- "KAP-01" badge ships, derived from position, catalog-supplied prefix.
- Save state: top bar and card foot render from one `status` owner.
- Running head without author: book alone, no trailing dash.
- Szenen tab links to the active novel's planning surface with the novel param.
- Folio and page marker: omitted until pagination exists (not neutral placeholders).

---

*Drafted 2026-11-12. Awaiting builder check and owner approval before the plan.*
