---
status: deprecated
---

# UI/UX Remediation — Phase B Shared UI Primitives Specification

> **Status:** draft — architecture gate, pre-implementation (no code written in this slice)
> **Historical note:** Remediation implemented; this is a closed design record — some referenced component paths drifted or were renamed during implementation (hence frontmatter `status: deprecated`, which skips spec file-reference validation).
> **Date:** 2026-07-03
> **Owner:** Architecture Specialist
> **Scope order:** C Panel/Shell Architecture → **B UI Primitives** → A Docs & SSOT → D polish/a11y/i18n/focus
> **Source contract:** `docs/features/remediation/ui-ux-remediation-panel-shell-architecture.md` §6 (Panel Taxonomy), §10 & §10.2 (Accessibility Contract + primitive implications), §11 (Phase B handoff)
> **Token/style authority:** `docs/development/ui-principles.md` §3 (Design Tokens), §4 (Component Conventions), §11 (Accessibility), §15 (File Size Limits)

---

## 1. Problem Statement

Phase C establishes the shell/panel interaction contract; Phase B must supply the concrete components that implement it. Today there is **no shared primitive layer for interactive surfaces**:

- Icon-only buttons are hand-rolled everywhere as `<button type="button" aria-label={...} className="p-1.5 text-muted-foreground hover:bg-muted ...">` — verified in `StudioWorkspaceShell.tsx`, `ConsistencyPanelHeader.tsx`, `NovelCardGrid.tsx`, and **100+ matches** across `components/`. Each repeat re-derives focus, disabled, and label behaviour.
- Panel headers are duplicated per panel: `ConsistencyPanelHeader.tsx`, `BetaReaderHeader.tsx`, and the inline headers inside `POVPanel`, `CoreferencePanel`, `VoiceCheckPanel`, `CharacterVoicePanel` each re-implement title + icon + close + status layout, `border-b bg-card`, and close-button a11y.
- Responsive panel chrome exists only as shell-specific code in `StudioWorkspaceShell.tsx` (desktop sidebar + mobile dialog/drawer); editor right panels and KB have no equivalent shared wrapper.
- Tab state in settings and analysis is local `useState`; KB search is local. The URL-addressable policy from Phase C §8 has no component to bind to.
- Status/live-region announcements are ad-hoc (an inline `role="status" aria-live="polite"` block in `StudioWorkspaceShell`, bespoke loading/error/empty blocks in `extraction/*`, and the specialised `connection-lost-banner`).

Without a primitive layer, each new panel repeats the same drift Phase C exists to eliminate.

## 2. Root Cause Analysis

**Symptom:** Duplicated button/header/status markup, inconsistent a11y, no URL-bound tabs/search.

**Why #1:** Every feature built the minimum local markup it needed; no one owned the shared-surface contract.

**Why #2:** Phase C did not exist, so there was no authoritative list of what a "panel" must do. Primitives written before that contract would have been arbitrary.

**Root cause:** The shell/panel contract (Phase C) is now defined; the missing layer is the **primitives that implement it**. Building them from the Phase C §10.2 obligations turns ad-hoc repetition into typed, tested, reusable components. Patching markup per panel would preserve the drift.

## 3. Non-goals

- No production code, tests, or commits in this slice (architecture spec only).
- No new runtime dependency (no headless-ui / radix-ui additions; reuse Tailwind + existing shadcn-compatible patterns — Phase C §11.5, §16.10).
- No redesign of tokens, copy, or visual style (ui-principles §3/§4 remain authority).
- No backend/core changes.
- Does **not** re-spec the shell/panel taxonomy — that is Phase C. Phase B only builds components that conform to it.

## 4. Alternatives Considered

| Option | Description | Pros | Cons | Decision |
|---|---|---|---|---|
| A — Inline-fix per finding | Add labels/focus/width fixes in each component independently. | Zero new files; fastest per symptom. | Preserves the 100+ duplication; Phase C drift returns on the next panel; a11y stays un-enforceable. | Rejected — symptom treatment. |
| B — Adopt an external headless library | Use a full headless UI kit (Radix, Ariakit) for buttons/dialogs/tabs. | Battle-tested a11y out of the box. | Violates Phase C §11.5 / §16.10 (no new dependency without ADR); diverges from existing Tailwind+token workflow; large blast radius. | Rejected — needs ADR + re-evaluation; out of scope. |
| C — Minimal in-repo primitive set derived from Phase C | Build 7 small primitives under `components/ui/`, each mapping to a Phase C §10.2 obligation, using existing tokens and Tailwind. | Fits stack; enforces the contract locally; testable; no dependency; sustainable for new panels. | Requires per-primitive tests and a migration pass over existing panels. | **Chosen.** |
| D — Defer until Phase D | Ship nothing now; patch in Phase D polish. | Less short-term churn. | Phase D polish has no foundation; "documented ≠ implemented" repeats (CONSTRAINTS §7). | Rejected — defers root cause. |

## 5. Primitive Specifications

All primitives live under `packages/web/components/ui/` (existing home of `confirm-dialog`, `connection-lost-banner`, `toaster`, `feature-tour`). Each is one-component-per-file (ui-principles §4), named-export PascalCase, `"use client"` only where it uses hooks. All visible text is i18n-backed (RULE-16); icon-only labels are **required** props, never inferred. Primitives must not import feature-specific panels (Phase C §12). File-size limits apply (ui-principles §15): primitive ≤ 200 lines; split hooks into `use*.ts` (≤ 150 lines) if needed.

### 5.1 `IconButton`

**Responsibility:** Single icon action with an accessible name, focus ring, and disabled/loading state. The atomic building block for close, refresh, toggle, menu.

**Replaces:** All inline `<button type="button" aria-label=... className="p-1.5 ... rounded-md hover:bg-muted ...">` patterns (e.g. `StudioWorkspaceShell.tsx:35-42`, `ConsistencyPanelHeader.tsx:33-40,71-78`).

**Key props:** `label` (required, i18n string → `aria-label`), `icon` (Lucide component), `onClick`, `disabled?`, `loading?` (renders spinner, sets `aria-busy`), `variant?` (`'ghost' | 'destructive' | 'default'`), `size?`. **Always** renders `type="button"`.

**a11y:** visible focus (`focus-visible:ring-1 ring-ring`); `aria-label` mandatory; `aria-disabled`/`disabled` when `disabled`; spinner has `aria-hidden`. Complies with ui-principles §11.

**File:** `packages/web/components/ui/icon-button.tsx`

### 5.2 `PanelHeader`

**Responsibility:** Accessible header for any workspace side panel / inspector: title, optional description/status slot, leading icon, trailing actions, optional close. Wires `aria-labelledby`.

**Replaces:** `ConsistencyPanelHeader.tsx`, `BetaReaderHeader.tsx`, and the inline headers in `POVPanel` / `CoreferencePanel` / `VoiceCheckPanel` / `CharacterVoicePanel`. Eliminates repeated `flex items-center justify-between p-4 border-b border-border bg-card` + close-button boilerplate.

**Key props:** `title` (required i18n), `icon?`, `description?`, `statusSlot?` (ReactNode: live status/progress), `actions?` (ReactNode: refresh/stop), `onClose?` (renders `IconButton` close when provided). Generates a stable `id` for `aria-labelledby` consumers (`PanelShell`).

**a11y:** `<div role="heading">` or heading-level element with `id`; close uses `IconButton`; status slot is the integration point for `StatusMessage`. Meets Phase C §10.1 (programmatic title + close button).

**File:** `packages/web/components/ui/panel-header.tsx`

### 5.3 `PanelShell`

**Responsibility:** Desktop side-panel container and responsive drawer/sheet transformation for a single workspace side panel. Generalises the existing `StudioWorkspaceShell` mobile-dialog pattern (§9 responsive policy) into a reusable, panel-scoped wrapper.

**Replaces:** Shell-specific drawer code in `StudioWorkspaceShell.tsx:51-68` (generalised) and the absence of any shared responsive wrapper for editor right panels / KB inspector.

**Key props:** `titleId` (links to `PanelHeader` id → `aria-labelledby`), `side?` (`'right' | 'left'`), `children`, `responsive?` (default true), `open`, `onClose` (mobile drawer lifecycle). Desktop renders `<section role="region" aria-labelledby={titleId}>`; below the breakpoint renders dialog/drawer (`role="dialog" aria-modal="true"`).

**a11y (Phase C §10.1):** Escape closes; focus moves to header/first control on open; focus returns to opener on close; focus trapped while drawer open; preserves panel identity across breakpoints. **Streaming note (RULE-13):** PanelShell is presentation only — it does not own SSE; AI panels keep their streaming/cancel via existing hooks.

**File:** `packages/web/components/ui/panel-shell.tsx` (focus/escape logic may extract to `packages/web/lib/hooks/use-panel-focus.ts`)

### 5.4 `PanelTabs`

**Responsibility:** URL-addressable tab list that renders the active tab and keeps a search-param in sync — the component Phase C §8.1 binds settings/analysis/KB-mode navigation to.

**Replaces:** Local `useState<SettingsCategory>` tab switching (`SettingsView` / `SettingsSidebar`) and `AnalysisPanel`/`BetaReaderTabBar` local tab state.

**Key props:** `tabs: {id, label, content}[]`, `value`, `onValueChange`, `paramName?` + adapter (see §6), `aria-label`. Uses `role="tablist"`/`tab`/`tabpanel` semantics; arrow-key navigation.

**a11y:** ARIA tabs pattern; active tab `aria-selected`; panels linked via `aria-labelledby`; keyboard arrows/home/end.

**File:** `packages/web/components/ui/panel-tabs.tsx`

### 5.5 `ToolbarButton`

**Responsibility:** Editor/panel toolbar action with icon + optional visible label (or icon-only with tooltip). Distinct from `IconButton` because toolbar buttons are a labelled, horizontally-grouped set (formatting, AI triggers).

**Replaces:** The repeated `type="button"` entries in `packages/web/components/studio/editor-view/EditorToolbar.tsx` and the per-analysis trigger buttons (`POVTrigger`, `ConsistencyTrigger`, `CoreferenceTrigger`, `CharacterVoiceTrigger`, `ReadabilityTrigger`).

**Key props:** `label` (required — visible or tooltip/`aria-label`), `icon`, `onClick`, `disabled?`, `loading?`, `showLabel?` (default icon-only on narrow, label on wide), `variant?`, `active?` (pressed state, e.g. active formatting). `type="button"` enforced.

**a11y:** `aria-pressed` when `active`; tooltip is supplemental, never the sole name; focus-visible ring.

**File:** `packages/web/components/ui/toolbar-button.tsx`

### 5.6 `SearchInput`

**Responsibility:** Labelled text search with a clear button and hooks for URL sync. Backs KB `?q=` (Phase C §8.1) and any future filter surface.

**Replaces:** KB/worldbuilding inline search box; scattered local search inputs.

**Key props:** `label` (required → `<label htmlFor>` + visible or `sr-only`), `value`, `onValueChange`, `onClear?`, `placeholder?`, `paramName?` + URL adapter. Clear button uses `IconButton`.

**a11y (ui-principles §11):** `<label>` + `htmlFor`; clear is `IconButton` with i18n label; `type="search"` semantics; live results announcement delegated to the consumer's `StatusMessage`.

**File:** `packages/web/components/ui/search-input.tsx`

### 5.7 `StatusMessage`

**Responsibility:** Non-blocking loading/error/empty/success/live-region display. Single source for the status announcements Phase C §10.1 requires of long-running panels.

**Replaces:** Inline `role="status" aria-live="polite"` block (`StudioWorkspaceShell.tsx:48-50`), bespoke loading/error/empty blocks in `packages/web/components/studio/extraction/ExtractionLoading.tsx`/`ExtractionError.tsx`, and generalises `connection-lost-banner.tsx` (which can be re-expressed on top of it). Actionable errors follow ui-principles §16.5 (`[what happened] [what to do]`).

**Key props:** `state: 'idle' | 'loading' | 'success' | 'error' | 'empty'`, `message?`, `action?` (retry/reconnect button), `politeness?` (`'polite' | 'assertive'`, default polite; assertive for errors). Renders `role="status"`/`aria-live` correctly per state.

**a11y:** correct `aria-live`/`role` per state; error messages actionable and i18n-backed; loading uses `aria-busy`. Must not be used as a modal (ui-principles §1.5).

**File:** `packages/web/components/ui/status-message.tsx`

## 6. URL Sync (shared adapter, not a component)

`PanelTabs` and `SearchInput` both need URL-addressable state. Phase C §8.3 mandates one adapter per surface, not per component. Spec requires a small shared hook `packages/web/lib/hooks/use-url-param.ts` (≤ 150 lines): `value`, `setValue`, with explicit `replace | push` control and fail-safe normalisation to a valid default. **One adapter instance per surface** (settings category, KB mode/search, analysis tab); components consume it, they do not own it.

## 7. Migration Strategy

Migration is **gradual and evidence-cited**, panel-by-panel, behind tests. No big-bang rewrite. Order follows blast radius (lowest first):

| Step | Primitive | Adopters (evidence) | Note |
|---|---|---|---|
| 1 | `IconButton` | `StudioWorkspaceShell.tsx` (menu + close), `ConsistencyPanelHeader` close buttons | Lowest risk; pure markup extraction. |
| 2 | `StatusMessage` | `extraction/ExtractionLoading`, `ExtractionError`, `ExtractionDone`; re-express `connection-lost-banner` | Replaces ad-hoc live regions. |
| 3 | `PanelHeader` | `ConsistencyPanelHeader`, `BetaReaderHeader`, inline headers in `POVPanel`/`CoreferencePanel`/`VoiceCheckPanel`/`CharacterVoicePanel` | Largest dedup; preserve current behaviour. |
| 4 | `PanelShell` | Editor right panels (via `EditorRightPanelSlot`), KB inspector | Wires to typed panel registry (Phase C §7.3). |
| 5 | `ToolbarButton` | `EditorToolbar.tsx`, analysis triggers (`*Trigger.tsx`) | Editor-specific grouping. |
| 6 | `PanelTabs` + URL adapter | `SettingsView`/`SettingsSidebar` category, `AnalysisPanel` tabs | Introduces URL state (Phase C §8.1). |
| 7 | `SearchInput` + URL adapter | KB/worldbuilding search (`?q=`) | Last; depends on KB state adapter (Phase C §8.1). |

`StudioWorkspaceShell` is **not** rewritten onto `PanelShell` — it remains the shell owner (Phase C §5.3); only its buttons adopt `IconButton`. New panels adopt the primitives; existing panels migrate in the order above.

## 8. RULE-XX Compliance

| Rule | Status | Nachweis |
|---|---|---|
| RULE-03 | ✅ | This spec is the contract before any primitive implementation. |
| RULE-04 | ✅ | Each primitive is one file; shared logic (URL, focus) extracts to `use*.ts` hooks. |
| RULE-06 | ✅ | One responsibility per file: button, header, shell, tabs, toolbar, search, status remain distinct. |
| RULE-09 | ✅ | All props fully typed; `label` required where a11y depends on it. |
| RULE-10 | ✅ | Acceptance criteria require per-primitive tests + a11y tests. |
| RULE-11 | ✅ | `StatusMessage` makes errors actionable; invalid URL params fail-safe via the adapter. |
| RULE-13 | ✅ | `PanelShell`/`PanelHeader` are presentation only; AI streaming/cancel stay with panel hooks (no REST-only downgrade). |
| RULE-16 | ✅ | All visible labels/aria labels/status text i18n-backed; `label` is a required prop. |
| RULE-20 | ✅ | Primitives land before docs claim they exist; no half-implementation. |
| RULE-21 | ✅ | Adding an 8th primitive or changing a primitive's a11y contract requires Architecture re-review. |
| RULE-22 | ✅ | Central primitive set removes cross-feature UI divergence. |
| RULE-23 | ✅ | No type suppressions introduced by this spec. |

## 9. Acceptance Criteria

Implementation may pass the architecture gate only when:

1. The seven primitives (or named equivalents) exist under `components/ui/` and conform to their §5 specs.
2. `type="button"`, required `aria-label`/`label`, and `focus-visible` are enforced by the primitives — not re-derived per call site.
3. `PanelHeader` + `PanelShell` together satisfy Phase C §10.1 (title, status, close, Escape, focus return, focus trap on drawer).
4. `PanelTabs` and `SearchInput` bind to a single per-surface URL adapter (`use-url-param`) with fail-safe normalisation.
5. `StatusMessage` renders correct `role`/`aria-live` per state; errors are actionable (ui-principles §16.5).
6. No new runtime dependency; primitives use only existing tokens (ui-principles §3) and Tailwind.
7. Migration steps 1–7 are reflected in real adopter files (documentation is not closure evidence — CONSTRAINTS §7).
8. Tests cover: icon-button labels/focus/disabled; panel close/Escape/focus-return; URL param parse/normalise; responsive render of at least one panel; status-message live-region roles.
9. No file exceeds ui-principles §15 limits.

## 10. Risks and Trade-offs

| Risk | Impact | Mitigation |
|---|---|---|
| `PanelShell` focus-trap conflicts with TipTap shortcuts. | Writing shortcuts regress on mobile drawer. | Define focus priority; test editor + drawer interaction (Phase C §16). |
| Migration touches many files at once. | Large diff, merge churn. | Gradual panel-by-panel order (§7); each step independently shippable. |
| URL adapter over-uses `push`, pollutes history. | Back button unusable. | Adapter defaults to `replace` for transient typing; `push` only for explicit tab/selection changes (Phase C §16). |
| Primitives grow features over time (prop creep). | RULE-04/§15 pressure. | Keep one responsibility; new variants → new file or ADR re-review (RULE-21). |
| `connection-lost-banner` re-expression breaks existing a11y. | Banner regression. | Keep old behaviour as acceptance baseline before re-expressing. |

## 11. Sustainability Check

1. **Correct in 3 months?** Yes — new panels adopt primitives instead of re-deriving markup; Phase C §10 obligations are satisfied by composition.
2. **Hard-to-undo coupling?** No — primitives are leaf components with no feature imports; URL adapter is per-surface.
3. **Simplest correct solution?** Yes — seven small primitives, no dependency, no monolithic kit (Alternative B rejected).
4. **Design intent clear?** Yes — each primitive cites the Phase C obligation it implements and the ad-hoc pattern it replaces.

---

## 12. Architecture Handoff

**Spec type:** Feature spec (Phase B). **Status:** draft — pending Coordinator validation + user approval.
**Root cause:** Phase C contract now exists; the missing layer is the primitives that implement it. Ad-hoc markup (100+ inline buttons, 6+ duplicated panel headers) is the symptom.
**Alternatives rejected:** inline-fix per finding; external headless library (needs ADR + new dependency); defer to Phase D.

**Implementation plan (layer order):**
1. **Frontend (Phase B):** build primitives in `components/ui/` against §5; extract `use-url-param` + `use-panel-focus` hooks to `lib/hooks/`.
2. **Frontend (migration):** adopt per §7 order, panel-by-panel, behind tests.
3. **Platform/Testing:** add targeted a11y/URL-state tests (§9.8); no new static checker mandated by this spec alone.
4. **Docs (Phase A):** document primitives in `docs/development/ui-principles.md` only after files + tests exist.

**Critical constraints:** RULE-16 (i18n labels mandatory), RULE-13 (no REST-only AI downgrade — PanelShell is presentation only), Phase C §10 (a11y), ui-principles §15 (file size), Phase C §11.5 (no new dependency).

**Re-review triggers:** adding an 8th primitive; changing any primitive's a11y contract; introducing a dependency for focus/URL/dialog; merging primitives.
**Definition of Done:** §9 criteria met; no code/commit in this slice.
