# UI/UX Remediation — Phase C Panel/Shell Architecture Specification

> **Status:** draft — architecture gate, pre-implementation
> **Date:** 2026-07-01
> **Owner:** Architecture Specialist
> **Scope order approved by user:** C Panel/Shell Architecture → B UI Primitives → A Docs & SSOT → D Remaining polish/accessibility/i18n/focus findings
> **Related:** `docs/development/ui-principles.md`, `docs/architecture/governance/ai-ux-compliance-v2.md`

---

## 1. Problem Statement

Narrare's frontend has accumulated feature-local layouts and panel toggles without a central shell/panel contract. The product direction is coherent at the feature level, but dashboard, wizard, and studio workspace routes feel like separate applications; the editor has many mutually exclusive right-side panels whose arbitration exists in code but not as an architecture contract; and stateful navigation such as settings tabs, planning tabs, KB modes/search/selection, and analysis tabs is mostly local state rather than deep-linkable URL state.

### Verified current implementation reality

Representative files were checked after graph discovery and exact reads:

| Area | Current evidence | Architectural gap |
|---|---|---|
| Studio shell | `packages/web/app/(studio)/layout.tsx` always renders `<Sidebar />` plus `main`; `Sidebar.tsx` is novel-aware. | The route group currently also contains `/wizard`, so workspace chrome ownership is broader than the intended novel-scoped shell. |
| Wizard shell | `packages/web/app/(studio)/wizard/layout.tsx` says it is a no-sidebar layout and provides a minimal top logo header, but it sits below the `(studio)` layout that renders the sidebar. | Wizard shell ownership is ambiguous in the route tree and must be separated from workspace shell chrome. |
| Dashboard shell | `packages/web/app/page.tsx` renders `DashboardView`; `DashboardView.tsx` uses `DashboardHeader` and no sidebar. | Dashboard is a project selector shell outside the workspace shell, not the studio workspace shell. |
| Editor panels | `EditorView.tsx`, `useEditorPanelVisibility.ts`, `EditorSidePanels.tsx`, `editorStore.ts`, and `editorPanelToggles.ts` implement right-panel mutual exclusion and metadata fallback. | Priority/arbitration is encoded procedurally, not specified. New panels can easily drift. |
| KB/worldbuilding | `WorldBuilding.tsx`, `worldBuildingState.ts`, and `WorldBuildingLayout.tsx` use a 3-column browser with local `showAnalysis/showConsistency/showGraph/showWiki`, selected entry, and active type state. | The 3-column desktop layout has no responsive contract and no URL state policy. |
| Settings/planning/analysis | `SettingsView.tsx`, `PlanningPanel.tsx`, `AnalysisPanel.tsx` use local `useState` for tabs/active cards. | Shareable URLs, back/forward behavior, and reload recovery are undefined. |

### Non-goals

- No frontend implementation in this architecture slice.
- No new runtime dependency.
- No changes to backend/core service contracts.
- No redesign of visual style, tokens, copy, or brand.
- No attempt to close all product-polish/accessibility/i18n/focus findings; those are Phase D after the shell/panel and primitive contracts exist.

---

## 2. Root Cause Analysis

**Symptom:** Missing icon-button labels, stale layout docs, local tab state, mobile gaps, and panel collisions appear as many independent UI issues.

**Why #1:** Each feature added the minimum local layout/state needed for itself: editor AI panels added their own toggles, KB modes live in `WorldBuilding` local state, settings/planning tabs live in local `useState`, and dashboard/wizard route shells diverged from the original sidebar-only documentation.

**Why #2:** There is no authoritative frontend shell/panel interaction model defining route shell ownership, panel taxonomy, panel arbitration, responsive transformations, URL persistence, and accessibility obligations. Without that contract, Phase B primitives would be arbitrary components rather than implementations of a shared model, and Phase A docs would keep describing whichever route was last edited.

**Root cause:** The UI governance layer lacks a central product-shell and panel orchestration contract. The correct fix is to define the shell/panel architecture first, then derive shared primitives and docs from it. Patching labels, local state, or individual panel widths first would treat symptoms and preserve the underlying drift.

---

## 3. Architectural Fit

This is a frontend architecture remediation spec. It fits Narrare's layers as follows:

| Layer | Responsibility in this remediation |
|---|---|
| Core | No changes. Core remains UI-agnostic. |
| Backend/API | No changes unless a later Phase D finding discovers an API contract gap. |
| Frontend | Implements shell ownership, panel registry/arbitration, URL-state adapters, responsive transformations, accessibility affordances, and shared UI primitives. |
| Platform | Adds/updates targeted static checks only if Phase B/D introduces enforceable patterns; no broad checker is required by this Phase C spec alone. |
| Docs | Updates UI principles, feature help/status docs, and governance prose after implementation evidence exists. |

Dependency direction remains frontend-internal. No `packages/core/` or `apps/api/` import changes are implied. The shell/panel model lives in `packages/web/` and consumes existing route params, search params, TanStack Query state, Zustand UI state, and existing API hooks.

---

## 4. Alternatives Considered

| Option | Description | Pros | Cons | Decision |
|---|---|---|---|---|
| A — Patch each finding locally | Add labels, mobile classes, and URL params in each affected component independently. | Fast per symptom; minimal initial refactor. | Preserves route-shell drift; new panels repeat custom logic; Phase B primitives lack a source contract; URL/responsive behavior remains inconsistent. | Rejected. This is symptom treatment. |
| B — One global app shell and one global panel manager for every route | Force dashboard, wizard, and studio into one shell abstraction with one panel manager. | Strong centralization; one place to inspect. | Over-couples distinct user journeys; dashboard/wizard legitimately need different chrome; risks a monolith that violates RULE-06 and becomes hard to adapt. | Rejected. Too much coupling. |
| C — Shell taxonomy + workspace panel registry/arbitration contract | Define three route shells; define panel types; centralize workspace right-slot arbitration while allowing route-specific ownership for dashboard/wizard and modal/dialog/popover cases. | Fixes root cause; respects existing route differences; gives Phase B primitives a clear contract; sustainable for new AI panels. | Requires refactoring existing editor panel toggles and URL adapters instead of one-off patches. | **Chosen.** |

---

## 5. Shell Taxonomy and Route Ownership

Narrare has three first-class shell types. A route must declare exactly one shell type by file location and component ownership.

### 5.1 Dashboard shell

**Purpose:** Project/novel selection, demo discovery, account-level entry actions.

**Routes:** `/` via `app/page.tsx` and `DashboardView`.

**Chrome rules:**

- Uses a top header (`DashboardHeader`) with app identity and account controls.
- Does **not** render the persistent studio sidebar.
- Body may scroll vertically; it is a project-list surface, not the writing workspace.
- Opens global dialogs only for destructive confirmations or authentication/account flows.

**Rationale:** Before a novel is selected, the studio sidebar's novel-scoped navigation is not meaningful. Treating dashboard as a no-sidebar shell aligns code and product intent.

### 5.2 Wizard/setup shell

**Purpose:** Focused setup/onboarding flow with step progression and minimum navigation chrome.

**Routes:** `/wizard` via the existing wizard route and `WizardShell`; implementation must ensure the route is not wrapped by the workspace sidebar shell. A separate setup route group is acceptable if Frontend chooses that structure.

**Chrome rules:**

- Uses a minimal logo/header bar.
- Does **not** render the persistent studio sidebar.
- Main content is centered, scrollable, and step-oriented.
- Step state remains wizard-owned unless a later explicit decision makes steps URL-addressable.

**Rationale:** Setup is a transient, guided flow. Persistent studio navigation would invite partial exits and conflict with completion semantics.

### 5.3 Studio workspace shell

**Purpose:** Novel-scoped productive work: editor, volumes, worldbuilding/KB, analysis, chat, settings.

**Routes:** `/novel/[id]/**` under `app/(studio)/novel/[id]/...`. The workspace shell must not own dashboard or wizard chrome.

**Chrome rules:**

- Uses the persistent left sidebar (`Sidebar`) with novel-scoped navigation.
- No top app header inside the shell; route-level headers live inside the workspace content if needed.
- Shell owns viewport sizing: full-height app, `main` uses `min-h-0 min-w-0` and child routes own internal scroll regions.
- Sidebar is persistent on desktop, collapsible/drawer-like on tablet/mobile per §9.

**Documentation correction required in Phase A:** `ui-principles.md` must stop saying that all app areas use persistent sidebar/no header. The correct statement is: dashboard uses a dashboard shell, wizard uses a setup shell, and novel-scoped studio routes use the persistent sidebar workspace shell.

---

## 6. Panel Taxonomy

Panel type determines ownership, state persistence, responsive behavior, and accessibility obligations.

| Type | Allowed use | Not allowed for | Ownership |
|---|---|---|---|
| Workspace side panel | Long-lived, route/workspace-scoped companion content beside the main surface: editor metadata, AI analysis results, writing session, generation review. | Tiny actions, destructive confirmation, transient menus. | Route/workspace panel registry and arbitration. |
| Inspector panel | Object-specific details/editing that belongs to the current route's selected item: KB detail panel, volume detail, future context inspector. | Global app state or cross-route flows. | Owning route/view. |
| Modal/dialog | Blocking confirmation or constrained task with explicit completion/cancel: delete confirmation, AI rewrite suggestion modal, name generator if it blocks editor interaction. | Long-running side work or browsing/selection state that should remain visible while editing. | Owning component; must meet dialog accessibility. |
| Drawer/sheet | Mobile/tablet transformation of a workspace side panel or sidebar; may slide from side/bottom. | Desktop primary pattern when side-by-side space exists. | Same owner as the panel it transforms from. |
| Inline popover | Small anchored, dismissible controls: bubble menu, compact filters, tooltips. | Anything with long-running AI lifecycle, complex forms, or persistent navigation. | Owning component; ephemeral state only. |

Rule: a feature must not introduce a new panel style until it can classify itself under this taxonomy. If none fits, Architecture re-review is required.

---

## 7. Editor Panel Arbitration Contract

The editor has one canonical right workspace side-panel slot. The slot may render exactly one occupant at a time on desktop. On tablet/mobile, the same slot transforms into a drawer/sheet; it still has one active occupant.

### 7.1 Right-slot occupants

Current occupants:

1. Writing session (`SessionPanel`)
2. Generation review (`GenerationPanel`)
3. Beta reader (`BetaReaderPanel`)
4. Readability (`ReadabilityPanel`)
5. POV (`POVPanel`)
6. Coreference (`CoreferencePanel`)
7. Character voice (`CharacterVoicePanel`)
8. Voice check (`VoiceCheckPanel`)
9. Sentiment (`SentimentPanel`)
10. Consistency (`ConsistencyPanel`)
11. Metadata/wiki summary (`MetadataSidebar` + `WikiChapterSummaryPanel`)

### 7.2 Priority and mutual exclusion

The canonical priority is:

`session > generation > beta_reader > readability > pov > coreference > character_voice > voice_check > sentiment > consistency > metadata`

Rules:

- `session` is highest priority because it represents an active conversational writing turn and may have recovery/stop semantics.
- `generation` is next because it can carry draft accept/reject state.
- Analysis panels are mutually exclusive and use the priority order above only as deterministic conflict recovery, not as product ranking.
- `metadata` is the fallback occupant when `contextPanelOpen` is true and no higher-priority occupant is active.
- Opening any analysis/generation panel closes metadata and other right-slot panels.
- Closing the active panel returns to the previous safe state:
  - if metadata was explicitly open before the active panel opened, restore metadata;
  - otherwise close the right slot;
  - session close follows the session lifecycle contract and must not discard unsaved/partial session output silently.
- Starting a session while another panel is open suspends the previous panel occupant; after session close, recovery should prefer the latest explicit user panel request if its source data is still valid.

### 7.3 Architecture shape for implementation handoff

Frontend should replace distributed boolean arbitration with a typed panel registry/controller:

```text
EditorRightPanelId =
  metadata | session | generation | beta_reader | readability | pov |
  coreference | character_voice | voice_check | sentiment | consistency

EditorRightPanelState = {
  active: EditorRightPanelId | null
  previous: EditorRightPanelId | null
  requestedBy: toolbar | sidebar | ai_result | recovery | url
}
```

This is not a mandate to create these exact type names, but the implementation must expose equivalent typed semantics. A list of booleans is not an acceptable long-term panel arbitration contract because it makes invalid multi-open states representable and forces priority to be re-encoded in selectors.

### 7.4 Metadata vs AI panels

- Metadata is an inspector for the current chapter, not an AI operation panel.
- Metadata may remain URL-addressable as `panel=metadata` but does not own AI lifecycle, cancel, streaming, or accept/reject semantics.
- AI panels remain governed by `ui-principles.md` §16 and `ai-ux-compliance-v2.md`: SSE where available, visible lifecycle, cancel where long-running, structured errors, canonical action vocabulary, and operation inventory coverage.

---

## 8. URL-State Policy

URL state is required when state changes what the user considers their current place in the product and should survive reload/share/back-forward. Ephemeral interaction state remains local.

### 8.1 Required URL state

| Surface | URL state required | Example policy |
|---|---|---|
| Settings | Active category | `/novel/{id}/settings?category=ai`; valid values come from `SettingsCategory`; invalid value falls back to default and replaces/normalizes URL. |
| Planning panel | Open/collapsed and active tab when used as route-level workspace context | `/novel/{id}?planning=1&planningTab=timeline`; default remains collapsed/no param. |
| Editor right panel | Active right-slot occupant where deep-linking is useful and safe | `/novel/{id}?panel=metadata`, `panel=readability`, `panel=voice_check`. Session recovery may use `panel=session&sessionId=...` only if compatible with ADR-052/ADR-053 recovery semantics. |
| KB/worldbuilding | Active type/category, mode, selected entry, search/filter | `/novel/{id}/worldbuilding?type=character&mode=detail&entry={entryId}&q=ada`; `mode=graph|wiki|analysis|consistency|detail|create|assist`. |
| Analysis route | Active analysis tab/card/panel | `/novel/{id}/analysis?tab=readability` or `?panel=readability`; must align with final route UX. |

### 8.2 Ephemeral local state

Keep local only:

- Unsaved input text within forms before explicit save/apply.
- Loading flags and in-flight request IDs, except session recovery IDs already governed by ADR-052/ADR-053.
- Hover, focus, drag overlays, transient popover open state.
- Destructive confirmation dialog open state.
- Wizard intermediate field state already persisted in `wizardStore` for the flow; step URL-addressing is not required in this phase.

### 8.3 URL adapter rules

- URL parsing must be centralized per surface, not repeated in every component.
- Invalid params must fail safe: normalize to a valid default, show an empty/not-found state for deleted selected entities, or remove stale params.
- Back/forward navigation must update the visible panel/tab/mode without full data loss.
- Server state remains TanStack Query; URL state selects/query-filters, it does not duplicate server data.
- Zustand may remain the transient UI state owner, but URL-addressable state needs a synchronization adapter with a single source-of-truth decision per surface.

---

## 9. Responsive Policy

Breakpoints should follow Tailwind conventions already in the project. Exact pixel values are Frontend-owned, but behavior is architectural:

| Surface | Desktop | Tablet | Mobile |
|---|---|---|---|
| Studio sidebar | Persistent left sidebar, 288px. | Collapsible rail or drawer; content keeps full-height shell. | Drawer opened from an accessible menu button; no permanent 288px sidebar. |
| Editor right slot | Fixed side panel, current width around 400px; editor keeps `min-w-0`. | Side panel may become overlay drawer from right; one active occupant. | Bottom sheet or full-height drawer; focus trapped while open; editor remains recoverable behind it. |
| Metadata panel | Same slot as other right panels. | Drawer/overlay. | Drawer/sheet; must not compress writing surface below usable width. |
| KB 3-column layout | Category sidebar + entry list + detail/inspector. | Category and entry list may collapse into stacked master/detail or side drawer; selected detail remains primary. | Single-column progressive disclosure: category → list → detail/mode panel; browser back or in-view back returns to previous level. |
| Storyboarding/planning | Horizontal storyboard lanes can scroll within planning panel. | Horizontal scroll with visible affordances; tab bar remains reachable. | Storyboard becomes horizontally scrollable board or stacked stage list; drag/drop must have keyboard/touch alternative or a non-DnD edit path. |
| Dashboard | Header + grid/list with normal document scroll. | Cards reflow. | Cards become single-column; no studio sidebar. |
| Wizard | Centered card. | Centered with reduced padding. | Full-width card/steps; no horizontal overflow. |

Responsive transformation must preserve the same panel identity and URL state. A desktop `panel=voice_check` URL must open the voice-check right drawer/sheet on mobile, not drop the panel.

---

## 10. Accessibility Contract

Phase B will define concrete components; Phase C defines their required behavior.

### 10.1 Required semantics

- Every workspace side panel/drawer must have a programmatic title. Desktop side panels may use `role="region"` with `aria-labelledby`; modal/drawer transformations must use dialog semantics when focus is constrained.
- Every panel has a header containing title, optional status/description, and a close button when closeable.
- Icon-only buttons require localized `aria-label` and visible focus ring.
- `Escape` closes the active panel/drawer/popover when no text-entry or editor-specific shortcut has higher priority. Closing must be equivalent to the visible close button.
- Long-running AI panels announce loading, streaming, completion, and actionable errors through an appropriate live region or existing status primitive.
- Focus on open: move focus to the panel header or first meaningful control. Focus on close: return to the control that opened the panel when it still exists; otherwise return to the editor/workspace landmark.
- Panels opened by URL on page load focus conservatively: do not steal focus from initial route load unless the panel is modal/drawer on mobile; make the panel discoverable via landmarks/headings.
- Keyboard tab order follows visual order. Drawer/sidebar overlays must prevent focus from moving behind the overlay while open.

### 10.2 Phase B primitive implications

The primitive library must support this contract rather than merely restyling current buttons. Phase B should introduce, at minimum:

- `IconButton` — enforces `type="button"`, localized label, focus styles, disabled/loading state.
- `PanelHeader` — title, description/status slot, close/action slot, `aria-labelledby` integration.
- `PanelShell` — desktop side-panel and responsive drawer/sheet wrapper with width/placement/accessibility behavior.
- `PanelTabs` — URL-addressable tab list pattern where required.
- `ToolbarButton` — consistent icon+label/tooltip behavior for editor toolbar actions.
- `SearchInput` — labelled search field with clear button and URL sync hooks where used for KB.
- `StatusMessage` — non-blocking loading/error/empty/success/live-region pattern.

If Phase B chooses different component names, it must provide equivalent responsibilities.

---

## 11. Handoff to Phase B and Phase A

### Phase B — UI primitives derive from this spec

Frontend must implement primitives only after accepting these contracts:

1. Shell-aware components must not hardcode assumptions that all routes have a sidebar.
2. Panel primitives must support both desktop side-panel and mobile drawer/sheet behavior.
3. Panel close/focus/escape behavior must be built into primitives or reusable hooks, not reimplemented per panel.
4. URL-addressable tabs/panels must use a shared adapter pattern per surface.
5. Primitives must use existing theme tokens and Tailwind/shadcn patterns; no new dependency.

### Phase A — Docs & SSOT derive from implementation evidence

Docs must be updated after Phase C/B implementation evidence exists:

- `docs/development/ui-principles.md` shell section: replace global sidebar/no-header claim with the three-shell taxonomy.
- `docs/development/ui-principles.md` panel section: add panel taxonomy, editor right-slot arbitration, URL-state and responsive policy.
- Feature specs/help docs: mention deep-linkable settings/planning/KB/analysis states where user-facing.
- AI-UX inventory prose: distinguish workspace side panels from modals/popovers and keep §16 lifecycle semantics for AI panels.

Docs must not claim a primitive or URL policy is implemented until the files and tests exist. Documentation is not closure evidence.

---

## 12. Module Boundary and Dependency Direction

Proposed frontend module ownership for implementation handoff:

| Module/files | Responsibility |
|---|---|
| `packages/web/app/page.tsx`, `components/studio/DashboardView.tsx`, `DashboardHeader.tsx` | Dashboard shell content and header. No studio sidebar. |
| Wizard route/layout, `components/studio/wizard/*` | Setup shell and wizard flow. No studio sidebar; route grouping must not let workspace shell chrome wrap the wizard. |
| `packages/web/app/(studio)/layout.tsx` or successor workspace route group, `Sidebar.tsx` | Studio workspace shell for novel-scoped routes only. |
| `packages/web/components/studio/editor-view/*` | Editor workspace composition and right-slot registry/arbitration adapter. |
| `packages/web/lib/stores/editorStore*` or successor | Typed editor UI state; must not represent impossible multi-panel states. |
| `packages/web/components/ui/*` or `components/studio/_primitives/*` | Phase B shared primitives. Exact location is Frontend-owned, but primitives must be reusable and not editor-only. |
| Route-specific state adapters | Settings, planning, KB, analysis URL param parsing/sync. Keep one adapter per surface. |

No module may import from another module's private internals. Frontend route/view components may consume shared UI primitives and lib hooks; primitives must not import feature-specific panels.

---

## 13. RULE-XX Compliance

| Rule | Status | Nachweis |
|---|---|---|
| RULE-03 | ✅ | This spec is the contract before Frontend implementation. |
| RULE-04 | ✅ | Requires modular panel registry/adapters/primitives; explicitly rejects a monolithic shell manager. |
| RULE-05 | ✅ | Module boundaries separate shell, route views, panel registry, primitives, and docs. |
| RULE-06 | ✅ | One responsibility per file/module: shell chrome, panel arbitration, URL adapter, primitive, and feature panel remain distinct. |
| RULE-09 | ✅ | Implementation handoff requires typed panel IDs/state and typed URL param adapters. |
| RULE-10 | ✅ | Acceptance criteria require tests for panel arbitration, URL state, responsive behavior, and accessibility. |
| RULE-11 | ✅ | Invalid URL params and deleted/stale selected entries must fail safe, not silently crash or display misleading state. |
| RULE-13 | ✅ | AI panels remain subject to streaming/cancel semantics where backend SSE exists; this spec does not permit REST-only downgrades. |
| RULE-15 | ✅ | No middleware/proxy changes. |
| RULE-16 | ✅ | All visible labels/aria labels/status text remain i18n-backed. |
| RULE-17 | ✅ | No API schema changes in this phase; later API-facing changes require TS/backend parity. |
| RULE-20 | ✅ | Prevents half-fixes: primitives/docs come after shell/panel contract, not before. |
| RULE-21 | ✅ | Material deviation from shell taxonomy, panel taxonomy, or URL policy requires Architecture re-review. |
| RULE-22 | ✅ | Cross-feature UI coherence is addressed centrally; editor, KB, planning, analysis, settings no longer define incompatible local interaction models. |
| RULE-23 | ✅ | No type suppressions introduced by this documentation-only spec. |

---

## 14. Acceptance Criteria for Frontend Implementation

Frontend Phase C/B implementation may pass the architecture gate only when:

1. Dashboard, wizard, and studio workspace shell ownership matches §5; wizard is not wrapped by the workspace sidebar shell; docs no longer contradict current reality.
2. Editor right-slot state is typed or equivalently impossible-state-safe; more than one right-slot occupant cannot be active in representable state.
3. Existing editor panels preserve current functionality and close/recovery behavior is deterministic.
4. Metadata remains the fallback inspector and does not conflict with AI panels.
5. Settings category, planning tab/open state, KB mode/type/search/selected entry, and analysis active tab/panel follow the URL policy or have an explicitly documented exception approved by Architecture.
6. Desktop/tablet/mobile behavior exists for sidebar, editor right panels, KB 3-column layout, and storyboarding without horizontal viewport breakage.
7. Panel headers, icon buttons, close buttons, `Escape`, focus return, and live/status messages satisfy §10.
8. Phase B primitives implement the responsibilities listed in §10.2 or provide named equivalents.
9. Tests cover at least: editor panel mutual exclusion; panel close/recovery; URL param parsing/normalization for settings and KB; responsive rendering for at least one right panel and KB layout; icon-only button labels/focus/escape behavior.
10. No new dependency, no new RULE-XX exception, no `middleware.ts`, no hardcoded user-facing strings.

---

## 15. Acceptance Criteria for Docs Update

Docs Phase A may pass only when:

1. `ui-principles.md` describes the three-shell taxonomy and no longer states that all app areas have a persistent sidebar/no header.
2. `ui-principles.md` documents panel taxonomy, editor right-slot arbitration, URL-state policy, responsive policy, and accessibility contract.
3. Feature/help docs that mention settings, KB, planning, analysis, or editor panels reflect final implemented URL/deep-link behavior.
4. AI-UX governance prose remains truthful: AI panel lifecycle compliance still depends on implementation + enforcement evidence, not the existence of this spec or primitives alone.
5. Any status registry/current-state updates are conservative and cite implementation/test evidence.

---

## 16. Risks and Dependencies

| Risk | Impact | Mitigation |
|---|---|---|
| Panel registry refactor changes user-visible panel behavior. | Users may lose expected panel recovery or close semantics. | Preserve current priority as baseline; add tests before changing behavior. |
| URL state causes noisy history entries for transient interactions. | Back button becomes unusable. | Only required deep-link state uses URL; ephemeral state remains local; use replace vs push deliberately. |
| Mobile drawer focus trapping conflicts with TipTap/editor shortcuts. | Accessibility or writing shortcuts regress. | Define focus priority and test editor + panel interactions. |
| KB 3-column responsive refactor is larger than expected. | Phase C implementation may sprawl. | Keep route-owned KB state adapter separate from generic `PanelShell`; split components per RULE-04/RULE-06. |
| Docs updated before implementation. | Repeats “documented ≠ implemented” failure mode. | Phase A occurs after C+B implementation evidence; docs cite files/tests. |

Dependencies:

- Existing Next.js App Router structure and current route grouping.
- Existing Zustand/TanStack Query patterns.
- Existing theme tokens and shadcn-compatible primitives.
- Existing AI-UX governance for AI operation lifecycle.

---

## 17. Sustainability Check

1. **Still correct in 3 months?** Yes. New AI panels register as workspace side-panel occupants instead of adding booleans and ad hoc widths.
2. **Hard-to-undo coupling?** No. Shell types are explicit and route-owned; primitives are shared; feature panels remain feature-owned.
3. **Simplest correct solution?** Yes. It centralizes only the architectural invariants (shells, panel taxonomy, arbitration, URL/responsive/accessibility contracts) and avoids one giant global UI manager.
4. **Design intent understandable?** Yes. The spec records current implementation evidence, root cause, alternatives, decision, module boundaries, and handoff gates.

---

## 18. Implementation Handoff

### Layer order

1. **Frontend Phase C:** Implement shell declarations/route ownership cleanup if needed; introduce typed editor right-panel registry/arbitration; add URL-state adapters for settings, planning, KB, and analysis; add responsive transformations.
2. **Frontend Phase B:** Implement shared primitives (`IconButton`, `PanelHeader`, `PanelShell`, `PanelTabs`, `ToolbarButton`, `SearchInput`, `StatusMessage` or equivalents) against the Phase C contracts.
3. **Platform/Testing:** Add targeted tests/checks only where the implementation creates enforceable patterns.
4. **Docs Phase A:** Update UI principles, feature/help docs, and governance prose with implementation evidence.
5. **Phase D Review:** Re-review remaining product-polish/accessibility/i18n/focus findings against the new shell/panel/primitives baseline.

### Re-review triggers

- Adding a fourth shell type.
- Adding a second editor right-side desktop slot.
- Making wizard steps URL-addressable.
- Introducing a new panel type outside §6.
- Adding a dependency for responsive drawers, focus management, or URL state.
- Materially changing AI panel lifecycle semantics or streaming behavior.
