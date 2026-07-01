# UI/UX Phase C Shell & Panel Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan is Phase C only; do not implement Phase B shared primitives, Phase A docs, or Phase D polish in this pass.

**Goal:** Implement the approved Phase C shell and panel architecture so route shells are owned by the correct route layer, editor right-panel state is impossible-state-safe, deep-linkable workspace state is centralized, and the affected layouts have a responsive and accessibility baseline.

**Architecture:** Split shell ownership into an auth boundary, a novel-scoped workspace shell, and the existing dashboard/setup shells. Replace distributed editor right-panel booleans with a typed single-occupant controller, then add one URL-state adapter per affected surface so tabs, modes, search, selection, and safe panels can survive reload/share/back-forward without duplicating server data. Keep responsive and Phase-C accessibility behavior local to shell/panel orchestration; shared primitives remain a Phase B dependency.

**Tech Stack:** Next.js 16 App Router, React 19.2, TypeScript 6 strict mode, Tailwind CSS v4 utility classes, Zustand 5 for global UI state, TanStack Query v5 for server data, Vitest + Testing Library for component/unit tests.

## Global Constraints

- Base architecture spec: `docs/features/remediation/ui-ux-remediation-panel-shell-architecture.md` at commit `227c9763`.
- Approved sequence: C Panel/Shell Architecture → B UI Primitives → A Docs & SSOT → D remaining polish/accessibility/i18n/focus review.
- Scope: Phase C only; do not implement app code outside Phase C responsibilities.
- No new runtime dependency.
- No `middleware.ts`; Next.js route protection remains outside this plan and must not add middleware.
- No hardcoded user-facing strings if UI text is introduced; use existing `next-intl` namespaces and add locale keys for any new visible text.
- Keep files modular under RULE-04 and RULE-06; page files stay thin and feature components remain below the documented file limits.
- Tailwind utility classes only; no inline styles for new shell/panel work.
- No backend/core contract changes.
- Do not commit until coordinator review; commit messages below are for the implementation worker's checkpoints.

---

## Required Context Already Read for This Plan

- `.opencode/context/narrare-dev/standards/graph-exploration.md`
- `.opencode/context/narrare-dev/standards/architectural-discipline.md`
- `.opencode/context/narrare-dev/standards/typescript-standards.md`
- `docs/development/ui-principles.md`
- `docs/features/remediation/ui-ux-remediation-panel-shell-architecture.md`
- Representative implementation files listed by the coordinator, including current shell layouts, editor panel files, editor store files, Settings, WorldBuilding, Planning, and Analysis.

## Root Cause and Design Decision

**Root cause:** Route chrome, right-panel arbitration, local tab/mode state, and responsive/accessibility behavior are currently implemented feature-by-feature. That allows invalid editor multi-panel state to exist in the store, wraps setup routes in workspace chrome, and makes user-visible workspace positions non-shareable.

**Chosen design:** Implement the approved shell taxonomy plus a typed workspace right-panel registry/controller and surface-specific URL adapters.

**Alternatives considered:**

1. Patch each view locally with responsive classes and search-param reads. Rejected because it preserves feature-local drift and repeats panel/URL logic.
2. Build one global shell and panel manager for all routes. Rejected because dashboard, wizard/setup, and novel workspace have different ownership and one manager would over-couple unrelated journeys.
3. Chosen: an auth boundary, route-owned shells, and per-surface adapters. This centralizes invariants without creating a monolithic UI manager.

## File Structure Map Before Tasks

### Create

- `packages/web/app/(studio)/novel/[id]/layout.tsx` — novel-scoped workspace shell owner that renders `Sidebar`, `main`, `Toaster`, and `FeatureTour`.
- `packages/web/components/studio/shell/AuthGate.tsx` — shared authenticated loading/redirect boundary for studio/setup routes.
- `packages/web/components/studio/shell/StudioWorkspaceShell.tsx` — sidebar workspace chrome and responsive sidebar baseline.
- `packages/web/components/studio/shell/StudioWorkspaceShell.test.tsx` — verifies sidebar ownership, mobile toggle semantics, landmarks, and close-on-Escape behavior tied to shell chrome.
- `packages/web/lib/stores/editorRightPanelState.ts` — typed editor right-panel IDs, state, priority, and pure open/close/toggle reducers.
- `packages/web/lib/stores/editorRightPanelState.test.ts` — pure tests proving impossible multi-panel state is unrepresentable and recovery is deterministic.
- `packages/web/components/studio/editor-view/useActiveEditorRightPanel.ts` — selector hook that returns one active panel ID or `null` for the current chapter.
- `packages/web/components/studio/editor-view/EditorRightPanelSlot.tsx` — single switch renderer for the right slot with Phase-C panel accessibility hooks.
- `packages/web/components/studio/editor-view/EditorRightPanelSlot.test.tsx` — component tests for one active occupant, Escape close, focus return, and metadata fallback.
- `packages/web/lib/url-state/searchParams.ts` — generic typed helpers for parsing, cloning, normalizing, and updating `URLSearchParams`.
- `packages/web/components/studio/settings/settingsUrlState.ts` — `SettingsCategory` URL adapter for `category`.
- `packages/web/components/studio/settings/settingsUrlState.test.ts` — parse/normalize tests for settings category URL state.
- `packages/web/components/studio/planning/planningUrlState.ts` — planning open/tab adapter for `planning` and `planningTab`.
- `packages/web/components/studio/planning/planningUrlState.test.ts` — parse/serialize tests for planning URL state.
- `packages/web/components/studio/kb/kbUrlState.ts` — KB type/mode/search/entry adapter for `type`, `mode`, `q`, and `entry`.
- `packages/web/components/studio/kb/kbUrlState.test.ts` — parse/normalize tests for KB URL state.
- `packages/web/components/studio/analysis/analysisUrlState.ts` — analysis `tab`/`panel` adapter aligned with existing `AnalysisType`.
- `packages/web/components/studio/analysis/analysisUrlState.test.ts` — parse/normalize tests for analysis URL state.
- `packages/web/components/studio/editor-view/editorRightPanelUrlState.ts` — safe editor right-panel URL adapter for `panel`.
- `packages/web/components/studio/editor-view/editorRightPanelUrlState.test.ts` — tests for safe panel URL parsing and unsafe session URL exclusion.
- `packages/web/components/studio/__tests__/ShellOwnership.test.tsx` — route-shell composition regression tests showing dashboard and wizard do not render the workspace sidebar, while novel routes do.

### Modify

- `packages/web/app/(studio)/layout.tsx` — reduce to auth boundary only; remove workspace sidebar ownership.
- `packages/web/app/(studio)/wizard/layout.tsx` — consume `AuthGate`; keep setup shell minimal and no sidebar.
- No change: `packages/web/app/page.tsx` remains owned by the dashboard route and must not be wrapped by `StudioWorkspaceShell`.
- `packages/web/components/studio/Sidebar.tsx` — add responsive off-canvas support through typed props while preserving desktop default.
- `packages/web/components/studio/EditorView.tsx` — replace boolean visibility plumbing with `activeRightPanel`, URL sync hook, and typed panel actions.
- `packages/web/components/studio/editor-view/EditorToolbar.tsx` — consume `activeRightPanel` and `toggleRightPanel` instead of `generationPanelOpen` plus panel-specific open booleans.
- `packages/web/components/studio/editor-view/useEditorPanelVisibility.ts` — delete after `useActiveEditorRightPanel.ts` is in use.
- `packages/web/components/studio/editor-view/EditorSidePanels.tsx` — delete in Task 3 after `EditorView.tsx` imports `EditorRightPanelSlot.tsx` directly.
- `packages/web/lib/stores/editorStore.ts` — store `rightPanel: EditorRightPanelState` and expose `openRightPanel`, `closeRightPanel`, `toggleRightPanel`, and compatibility action names that call the typed controller.
- `packages/web/lib/stores/editorStoreTypes.ts` — remove right-panel boolean fields and type the new controller actions.
- `packages/web/lib/stores/editorPanelToggles.ts` — delete in Task 2 Step 5 after `editorStore.ts` no longer imports it; do not defer deletion to a type-check-driven conditional.
- `packages/web/components/studio/SettingsView.tsx` — initialize and update `activeCategory` through `settingsUrlState.ts`.
- `packages/web/components/studio/planning/PlanningPanel.tsx` — initialize open/tab state through `planningUrlState.ts`; keep `storyboardOpen` in Zustand as transient UI mirror.
- `packages/web/components/studio/WorldBuilding.tsx` — use `kbUrlState.ts` for active type/mode/search/entry and keep server data in TanStack Query.
- `packages/web/components/studio/_components/worldBuildingState.ts` — replace mode booleans with typed `KBMode` state derived from adapter inputs.
- `packages/web/components/studio/_components/WorldBuildingLayout.tsx` — add responsive progressive-disclosure classes and ARIA landmarks tied to current KB mode.
- `packages/web/components/studio/AnalysisPanel.tsx` — use `analysisUrlState.ts` for active analysis tab/panel.
- `packages/web/components/studio/__tests__/SettingsView.test.tsx` — cover URL category initialization and normalization.
- `packages/web/components/studio/__tests__/WorldBuilding.test.tsx` — cover URL mode/type/entry/search initialization and mode transitions.
- `packages/web/components/studio/planning/__tests__/PlanningPanel.test.tsx` — create, covering URL open/tab behavior and responsive container classes.
- `packages/web/components/studio/AnalysisPanel.test.tsx` — cover URL tab initialization and replace-vs-push policy.
- `packages/i18n/messages/de/studio.json` — add Phase-C shell/sidebar status keys with German reference copy.
- `packages/i18n/messages/en/studio.json` — add the same Phase-C shell/sidebar status keys with English copy.
- `packages/i18n/messages/fr/studio.json` — add the same Phase-C shell/sidebar status keys with French copy.

### Delete

- `packages/web/components/studio/editor-view/useEditorPanelVisibility.ts` after tests prove `useActiveEditorRightPanel.ts` is the only visibility selector.
- `packages/web/components/studio/editor-view/EditorSidePanels.tsx` after `EditorRightPanelSlot.tsx` is wired and imports are updated.
- `packages/web/lib/stores/editorPanelToggles.ts` in Task 2 Step 5 after every helper has been replaced by typed controller actions in `editorStore.ts`; this file must not survive past Task 2.

## Implementation Tasks

### Task 1: Route Shell Ownership Cleanup

**Files:**
- Create: `packages/web/components/studio/shell/AuthGate.tsx`
- Create: `packages/web/components/studio/shell/StudioWorkspaceShell.tsx`
- Create: `packages/web/components/studio/shell/StudioWorkspaceShell.test.tsx`
- Create: `packages/web/app/(studio)/novel/[id]/layout.tsx`
- Create: `packages/web/components/studio/__tests__/ShellOwnership.test.tsx`
- Modify: `packages/web/app/(studio)/layout.tsx`
- Modify: `packages/web/app/(studio)/wizard/layout.tsx`
- Modify: `packages/web/components/studio/Sidebar.tsx`
- Modify: `packages/i18n/messages/de/studio.json`
- Modify: `packages/i18n/messages/en/studio.json`
- Modify: `packages/i18n/messages/fr/studio.json`

**Interfaces:**
- Produces:
  - `interface AuthGateProps { children: React.ReactNode; loadingLabelKey?: string }`
  - `function AuthGate({ children, loadingLabelKey }: AuthGateProps): React.ReactNode`
  - `interface StudioWorkspaceShellProps { children: React.ReactNode }`
  - `function StudioWorkspaceShell({ children }: StudioWorkspaceShellProps): React.ReactNode`
  - `interface SidebarProps { variant?: "desktop" | "drawer"; open?: boolean; onClose?: () => void }`
- Consumes:
  - Existing `Sidebar`, `Toaster`, `FeatureTour`, `authApi.me`, `FEATURE_TOUR_STEPS`, and `next-intl` `studio.sidebar.appName`.

**Independently testable deliverable:** `(studio)` layout authenticates only, `/wizard` keeps setup chrome without the workspace sidebar, `/novel/[id]/**` owns `StudioWorkspaceShell`, and the focused shell tests pass before the checkpoint commit `refactor(web): separate dashboard setup and workspace shells`.

- [ ] **Step 1: Write failing route shell tests**

Create `packages/web/components/studio/__tests__/ShellOwnership.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/page";
import StudioLayout from "@/app/(studio)/layout";
import NovelLayout from "@/app/(studio)/novel/[id]/layout";
import WizardLayout from "@/app/(studio)/wizard/layout";

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: { id: "user-1" }, isError: false, isLoading: false }),
}));

vi.mock("@/lib/api/client", () => ({ authApi: { me: vi.fn() } }));
vi.mock("@/components/ui/toaster", () => ({ Toaster: () => <div data-testid="toaster" /> }));
vi.mock("@/components/ui/feature-tour", () => ({
  FeatureTour: () => <div data-testid="feature-tour" />,
}));
vi.mock("@/lib/config/feature-tour-steps", () => ({ FEATURE_TOUR_STEPS: [] }));
vi.mock("@/components/studio/DashboardView", () => ({
  DashboardView: () => <main data-testid="dashboard-shell">Dashboard</main>,
}));
vi.mock("@/components/studio/Sidebar", () => ({
  Sidebar: () => <aside data-testid="workspace-sidebar">Sidebar</aside>,
}));

describe("shell ownership", () => {
  it("dashboard route owns a dashboard shell without workspace sidebar", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("dashboard-shell")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-sidebar")).not.toBeInTheDocument();
  });

  it("studio auth boundary does not render workspace chrome by itself", () => {
    render(
      <StudioLayout>
        <div data-testid="studio-child" />
      </StudioLayout>,
    );
    expect(screen.getByTestId("studio-child")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-sidebar")).not.toBeInTheDocument();
  });

  it("wizard setup shell is auth-protected and not wrapped by sidebar", () => {
    render(
      <StudioLayout>
        <WizardLayout>
          <div data-testid="wizard-step" />
        </WizardLayout>
      </StudioLayout>,
    );
    expect(screen.getByTestId("wizard-step")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-sidebar")).not.toBeInTheDocument();
  });

  it("novel workspace route owns the sidebar shell", () => {
    render(
      <StudioLayout>
        <NovelLayout>
          <div data-testid="novel-child" />
        </NovelLayout>
      </StudioLayout>,
    );
    expect(screen.getByTestId("workspace-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("novel-child")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run shell test and verify it fails before implementation**

Run: `pnpm --dir packages/web test components/studio/__tests__/ShellOwnership.test.tsx`

Expected: FAIL because `packages/web/app/(studio)/novel/[id]/layout.tsx` does not exist and `StudioLayout` still renders `<Sidebar />`.

- [ ] **Step 3: Extract authenticated route boundary**

Create `packages/web/components/studio/shell/AuthGate.tsx`:

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { authApi } from "@/lib/api/client";

interface AuthGateProps {
  children: React.ReactNode;
  loadingLabelKey?: string;
}

export function AuthGate({ children, loadingLabelKey = "appName" }: AuthGateProps) {
  const t = useTranslations("studio.sidebar");
  const router = useRouter();
  const { isError, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    retry: false,
  });

  useEffect(() => {
    if (isError) router.push("/login");
  }, [isError, router]);

  if (isLoading || isError) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center flex flex-col items-center gap-4">
          <Image src="/logo.png" alt="" width={48} height={48} className="animate-pulse" priority />
          <span className="sr-only">{t(loadingLabelKey)}</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
```

- [ ] **Step 4: Reduce `(studio)` layout to auth boundary only**

Modify `packages/web/app/(studio)/layout.tsx` to:

```tsx
"use client";

import { AuthGate } from "@/components/studio/shell/AuthGate";

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
```

- [ ] **Step 5: Create the novel-scoped workspace shell**

Create `packages/web/components/studio/shell/StudioWorkspaceShell.tsx`:

```tsx
"use client";

import { Menu } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/studio/Sidebar";
import { FeatureTour } from "@/components/ui/feature-tour";
import { Toaster } from "@/components/ui/toaster";
import { FEATURE_TOUR_STEPS } from "@/lib/config/feature-tour-steps";

interface StudioWorkspaceShellProps {
  children: React.ReactNode;
}

export function StudioWorkspaceShell({ children }: StudioWorkspaceShellProps) {
  const t = useTranslations("studio");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!sidebarOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sidebarOpen]);

  return (
    <div className="size-full flex bg-background">
      <div className="hidden lg:flex lg:shrink-0">
        <Sidebar variant="desktop" />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center border-b border-border bg-card px-3 py-2 lg:hidden">
          <button
            type="button"
            aria-label={t("sidebar.openMenu")}
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-2 text-foreground hover:bg-accent focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
        <main className="flex-1 min-h-0 min-w-0" aria-label={t("shell.workspaceMain")}>{children}</main>
      </div>
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden" role="dialog" aria-modal="true" aria-label={t("sidebar.navigation")}>
          <button
            type="button"
            aria-label={t("sidebar.closeMenu")}
            className="absolute inset-0 bg-background/70"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-10 h-full w-72 bg-card shadow-xl">
            <Sidebar variant="drawer" open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}
      <Toaster />
      <FeatureTour steps={FEATURE_TOUR_STEPS} />
    </div>
  );
}
```

Before using `StudioWorkspaceShell`, modify all three locale files with these exact key/value additions. Insert the `sidebar` keys beside the existing `sidebar.logout` key and insert the `shell` object at the root level beside `sidebar`, preserving valid JSON commas.

`packages/i18n/messages/de/studio.json`:

```json
{
  "sidebar": {
    "openMenu": "Navigation öffnen",
    "closeMenu": "Navigation schließen",
    "navigation": "Workspace-Navigation"
  },
  "shell": {
    "workspaceMain": "Workspace-Inhalt",
    "editorRightPanel": "Editor-Seitenpanel",
    "panelOpened": "Panel geöffnet",
    "panelClosed": "Panel geschlossen"
  }
}
```

`packages/i18n/messages/en/studio.json`:

```json
{
  "sidebar": {
    "openMenu": "Open navigation",
    "closeMenu": "Close navigation",
    "navigation": "Workspace navigation"
  },
  "shell": {
    "workspaceMain": "Workspace content",
    "editorRightPanel": "Editor side panel",
    "panelOpened": "Panel opened",
    "panelClosed": "Panel closed"
  }
}
```

`packages/i18n/messages/fr/studio.json`:

```json
{
  "sidebar": {
    "openMenu": "Ouvrir la navigation",
    "closeMenu": "Fermer la navigation",
    "navigation": "Navigation de l’espace de travail"
  },
  "shell": {
    "workspaceMain": "Contenu de l’espace de travail",
    "editorRightPanel": "Panneau latéral de l’éditeur",
    "panelOpened": "Panneau ouvert",
    "panelClosed": "Panneau fermé"
  }
}
```

These snippets show only the keys to merge, not replacement file contents. Do not add English fallback strings in React code.

- [ ] **Step 6: Add novel route layout**

Create `packages/web/app/(studio)/novel/[id]/layout.tsx`:

```tsx
"use client";

import { StudioWorkspaceShell } from "@/components/studio/shell/StudioWorkspaceShell";

export default function NovelLayout({ children }: { children: React.ReactNode }) {
  return <StudioWorkspaceShell>{children}</StudioWorkspaceShell>;
}
```

- [ ] **Step 7: Keep wizard as setup shell and remove duplicated auth code**

Modify `packages/web/app/(studio)/wizard/layout.tsx` so it keeps the existing minimal header but no longer repeats `useQuery`/redirect logic. The layout should be:

```tsx
"use client";

import { BookOpen } from "lucide-react";
import { useTranslations } from "next-intl";

export default function WizardLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("studio.sidebar");

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="flex items-center px-6 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="text-sm font-semibold">{t("appName")}</span>
        </div>
      </header>
      <main className="flex-1 flex items-start justify-center overflow-y-auto">{children}</main>
    </div>
  );
}
```

- [ ] **Step 8: Type responsive sidebar props without changing desktop behavior**

Modify `packages/web/components/studio/Sidebar.tsx` with these exact structural changes:

1. Add `SidebarProps` after `NavItem`.
2. Change `export function Sidebar()` to `export function Sidebar({ variant = "desktop", onClose }: SidebarProps)`.
3. Add `handleNavigate` after `isActiveNav`.
4. Change the root `<div>` class from a string literal to `containerClassName`.
5. Add `onClick={handleNavigate}` to the logo `<Link href="/">`, the all-novels `<Link href="/">`, and each navigation `<Link href={item.href}>`.

```tsx
interface SidebarProps {
  variant?: "desktop" | "drawer";
  open?: boolean;
  onClose?: () => void;
}

export function Sidebar({ variant = "desktop", onClose }: SidebarProps) {
  const t = useTranslations("studio");
  const pathname = usePathname();
  const params = useParams();
  const logout = useAuthStore((s) => s.logout);

  const handleNavigate = () => {
    if (variant === "drawer") onClose?.();
  };

  const containerClassName =
    variant === "drawer"
      ? "w-72 bg-card flex flex-col h-full"
      : "w-72 bg-card border-r border-border flex flex-col h-full";
}
```

Replace the current root `<div className="w-72 bg-card border-r border-border flex flex-col h-full">` with `<div className={containerClassName}>`. Add `onClick={handleNavigate}` to these three existing `Link` elements: the logo `Link href="/"`, the all-novels `Link href="/"`, and each nav item `Link href={item.href}` inside `navItems.map()`.

Do not add new visible text inside `Sidebar.tsx`; drawer open/close/navigation labels are owned by `StudioWorkspaceShell` via the i18n keys added in Step 5. Keep the existing desktop root classes exactly when `variant === "desktop"`.

- [ ] **Step 9: Write workspace shell behavior tests**

Create `packages/web/components/studio/shell/StudioWorkspaceShell.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StudioWorkspaceShell } from "./StudioWorkspaceShell";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/components/studio/Sidebar", () => ({
  Sidebar: ({ variant = "desktop", onClose }: { variant?: "desktop" | "drawer"; onClose?: () => void }) => (
    <nav aria-label="sidebar.navigation" data-testid={`sidebar-${variant}`}>
      <button type="button" onClick={onClose}>
        close drawer
      </button>
    </nav>
  ),
}));

vi.mock("@/components/ui/toaster", () => ({
  Toaster: () => <div data-testid="toaster" />,
}));

vi.mock("@/components/ui/feature-tour", () => ({
  FeatureTour: () => <div data-testid="feature-tour" />,
}));

vi.mock("@/lib/config/feature-tour-steps", () => ({
  FEATURE_TOUR_STEPS: [],
}));

describe("StudioWorkspaceShell", () => {
  it("renders desktop sidebar, workspace main landmark, toaster, and feature tour", () => {
    render(
      <StudioWorkspaceShell>
        <div data-testid="workspace-child" />
      </StudioWorkspaceShell>,
    );

    expect(screen.getByTestId("sidebar-desktop")).toBeInTheDocument();
    expect(screen.getByRole("main", { name: "shell.workspaceMain" })).toContainElement(
      screen.getByTestId("workspace-child"),
    );
    expect(screen.getByTestId("toaster")).toBeInTheDocument();
    expect(screen.getByTestId("feature-tour")).toBeInTheDocument();
  });

  it("opens the mobile drawer from the menu button and closes it from the drawer callback", () => {
    render(<StudioWorkspaceShell>workspace</StudioWorkspaceShell>);

    fireEvent.click(screen.getByRole("button", { name: "sidebar.openMenu" }));
    expect(screen.getByRole("dialog", { name: "sidebar.navigation" })).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-drawer")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "close drawer" }));
    expect(screen.queryByRole("dialog", { name: "sidebar.navigation" })).not.toBeInTheDocument();
  });

  it("closes the mobile drawer on Escape", () => {
    render(<StudioWorkspaceShell>workspace</StudioWorkspaceShell>);

    fireEvent.click(screen.getByRole("button", { name: "sidebar.openMenu" }));
    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "sidebar.navigation" })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 10: Run focused shell verification**

Run: `pnpm --dir packages/web test components/studio/__tests__/ShellOwnership.test.tsx components/studio/shell/StudioWorkspaceShell.test.tsx`

Expected: PASS with all shell ownership and responsive shell tests green.

- [ ] **Step 11: Type-check shell changes**

Run: `pnpm --dir packages/web type-check`

Expected: PASS with no TypeScript errors and no `middleware.ts` introduced.

- [ ] **Step 12: Commit checkpoint after coordinator approval**

Commit message: `refactor(web): separate dashboard setup and workspace shells`

### Task 2: Editor Right-Panel Typed Registry and Store Arbitration

**Files:**
- Create: `packages/web/lib/stores/editorRightPanelState.ts`
- Create: `packages/web/lib/stores/editorRightPanelState.test.ts`
- Create: `packages/web/components/studio/editor-view/useActiveEditorRightPanel.ts`
- Modify: `packages/web/lib/stores/editorStoreTypes.ts`
- Modify: `packages/web/lib/stores/editorStore.ts`
- Delete: `packages/web/lib/stores/editorPanelToggles.ts`

**Interfaces:**
- Produces:
  - `type EditorRightPanelId = "metadata" | "session" | "generation" | "beta_reader" | "readability" | "pov" | "coreference" | "character_voice" | "voice_check" | "sentiment" | "consistency"`
  - `type EditorRightPanelRequestSource = "toolbar" | "sidebar" | "ai_result" | "recovery" | "url"`
  - `interface EditorRightPanelState { active: EditorRightPanelId | null; previous: EditorRightPanelId | null; requestedBy: EditorRightPanelRequestSource | null }`
  - `openEditorRightPanel(state, panel, requestedBy): EditorRightPanelState`
  - `closeEditorRightPanel(state, panel?): EditorRightPanelState`
  - `toggleEditorRightPanel(state, panel, requestedBy): EditorRightPanelState`
  - `isEditorRightPanelId(value: string | null): value is EditorRightPanelId`
  - `EDITOR_RIGHT_PANEL_PRIORITY: readonly EditorRightPanelId[]`
- Consumes:
  - Existing Zustand `set`, `sessionActive` lifecycle, and toolbar/panel close actions.

**Independently testable deliverable:** `EditorState.rightPanel` is the only right-panel state shape and pure reducer tests prove single occupancy and deterministic recovery. This task intentionally has no checkpoint commit because component call sites are migrated in Task 3 before the next type-check/commit gate.

- [ ] **Step 1: Write failing pure reducer tests**

Create `packages/web/lib/stores/editorRightPanelState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  closeEditorRightPanel,
  EDITOR_RIGHT_PANEL_PRIORITY,
  type EditorRightPanelState,
  isEditorRightPanelId,
  openEditorRightPanel,
  toggleEditorRightPanel,
} from "./editorRightPanelState";

describe("editor right panel state", () => {
  const closed: EditorRightPanelState = { active: null, previous: null, requestedBy: null };

  it("defines the approved priority order", () => {
    expect(EDITOR_RIGHT_PANEL_PRIORITY).toEqual([
      "session",
      "generation",
      "beta_reader",
      "readability",
      "pov",
      "coreference",
      "character_voice",
      "voice_check",
      "sentiment",
      "consistency",
      "metadata",
    ]);
  });

  it("can represent only one active panel", () => {
    const state = openEditorRightPanel(closed, "metadata", "toolbar");
    const next = openEditorRightPanel(state, "readability", "toolbar");
    expect(next).toEqual({ active: "readability", previous: "metadata", requestedBy: "toolbar" });
  });

  it("toggles the active panel closed and restores previous metadata", () => {
    const metadata = openEditorRightPanel(closed, "metadata", "toolbar");
    const readability = openEditorRightPanel(metadata, "readability", "toolbar");
    expect(toggleEditorRightPanel(readability, "readability", "toolbar")).toEqual({
      active: "metadata",
      previous: null,
      requestedBy: "recovery",
    });
  });

  it("closes to empty state when no previous panel is recoverable", () => {
    const state = openEditorRightPanel(closed, "voice_check", "toolbar");
    expect(closeEditorRightPanel(state, "voice_check")).toEqual(closed);
  });

  it("narrows valid panel IDs", () => {
    expect(isEditorRightPanelId("sentiment")).toBe(true);
    expect(isEditorRightPanelId("session")).toBe(true);
    expect(isEditorRightPanelId("extraction")).toBe(false);
  });
});
```

- [ ] **Step 2: Run reducer tests and verify failure**

Run: `pnpm --dir packages/web test lib/stores/editorRightPanelState.test.ts`

Expected: FAIL because `editorRightPanelState.ts` does not exist.

- [ ] **Step 3: Implement typed right-panel state**

Create `packages/web/lib/stores/editorRightPanelState.ts`:

```ts
export type EditorRightPanelId =
  | "metadata"
  | "session"
  | "generation"
  | "beta_reader"
  | "readability"
  | "pov"
  | "coreference"
  | "character_voice"
  | "voice_check"
  | "sentiment"
  | "consistency";

export type EditorRightPanelRequestSource = "toolbar" | "sidebar" | "ai_result" | "recovery" | "url";

export interface EditorRightPanelState {
  active: EditorRightPanelId | null;
  previous: EditorRightPanelId | null;
  requestedBy: EditorRightPanelRequestSource | null;
}

export const EDITOR_RIGHT_PANEL_PRIORITY = [
  "session",
  "generation",
  "beta_reader",
  "readability",
  "pov",
  "coreference",
  "character_voice",
  "voice_check",
  "sentiment",
  "consistency",
  "metadata",
] as const satisfies readonly EditorRightPanelId[];

export const CLOSED_EDITOR_RIGHT_PANEL_STATE: EditorRightPanelState = {
  active: null,
  previous: null,
  requestedBy: null,
};

const PANEL_IDS = new Set<EditorRightPanelId>(EDITOR_RIGHT_PANEL_PRIORITY);

export function isEditorRightPanelId(value: string | null): value is EditorRightPanelId {
  return value !== null && PANEL_IDS.has(value as EditorRightPanelId);
}

export function openEditorRightPanel(
  state: EditorRightPanelState,
  panel: EditorRightPanelId,
  requestedBy: EditorRightPanelRequestSource,
): EditorRightPanelState {
  return {
    active: panel,
    previous: state.active === panel ? state.previous : state.active,
    requestedBy,
  };
}

export function closeEditorRightPanel(
  state: EditorRightPanelState,
  panel: EditorRightPanelId | null = state.active,
): EditorRightPanelState {
  if (panel !== null && state.active !== panel) return state;
  if (state.previous !== null) {
    return { active: state.previous, previous: null, requestedBy: "recovery" };
  }
  return CLOSED_EDITOR_RIGHT_PANEL_STATE;
}

export function toggleEditorRightPanel(
  state: EditorRightPanelState,
  panel: EditorRightPanelId,
  requestedBy: EditorRightPanelRequestSource,
): EditorRightPanelState {
  if (state.active === panel) return closeEditorRightPanel(state, panel);
  return openEditorRightPanel(state, panel, requestedBy);
}
```

- [ ] **Step 4: Replace panel booleans in store types**

Modify `packages/web/lib/stores/editorStoreTypes.ts` to import the new types and replace `contextPanelOpen`, `generationPanelOpen`, and all right-panel analysis booleans with:

```ts
import type {
  EditorRightPanelId,
  EditorRightPanelRequestSource,
  EditorRightPanelState,
} from "./editorRightPanelState";

export interface EditorState {
  activeChapterId: string | null;
  activeVolumeId: string | null;
  saveStatus: SaveStatus;
  lastSavedAt: Date | null;
  sidebarOpen: boolean;
  rightPanel: EditorRightPanelState;
  focusMode: boolean;
  storyboardOpen: boolean;
  editor: Editor | null;
  isDragging: boolean;
  isGenerating: boolean;
  activeRequestId: string | null;
  generationMode: string | null;
  draftText: string;
  sessionActive: boolean;
  extractionPanelOpen: boolean;
  betaReaderResult: BetaReaderResponse | null;
  betaReaderLoading: boolean;
  sentimentResult: SentimentOverview[] | null;
  sentimentLoading: boolean;
  consistencyResult: ConsistencyResponse | null;
  consistencyLoading: boolean;
  openRightPanel: (panel: EditorRightPanelId, requestedBy: EditorRightPanelRequestSource) => void;
  closeRightPanel: (panel?: EditorRightPanelId) => void;
  toggleRightPanel: (panel: EditorRightPanelId, requestedBy: EditorRightPanelRequestSource) => void;
  toggleContextPanel: () => void;
  toggleGenerationPanel: () => void;
  toggleBetaReaderPanel: () => void;
  toggleSentimentPanel: () => void;
  toggleConsistencyPanel: () => void;
  toggleReadabilityPanel: () => void;
  togglePovPanel: () => void;
  toggleCoreferencePanel: () => void;
  toggleCharacterVoicePanel: () => void;
  toggleVoiceCheckPanel: () => void;
  setActiveChapterId: (id: string | null) => void;
  setActiveVolumeId: (id: string | null) => void;
  setSaveStatus: (status: SaveStatus) => void;
  setEditor: (editor: Editor | null) => void;
  setIsDragging: (dragging: boolean) => void;
  toggleSidebar: () => void;
  toggleFocusMode: () => void;
  toggleStoryboard: () => void;
  updateChapterWordCount: (
    chapterId: string,
    wordCount: number,
    chapters: ChapterSummary[],
  ) => ChapterSummary[];
  setGenerating: (value: boolean) => void;
  setActiveRequestId: (id: string | null) => void;
  setGenerationMode: (mode: string | null) => void;
  setDraftText: (text: string) => void;
  setSessionActive: (value: boolean) => void;
  toggleExtractionPanel: () => void;
  setBetaReaderResult: (result: BetaReaderResponse | null) => void;
  setBetaReaderLoading: (loading: boolean) => void;
  setSentimentResult: (result: SentimentOverview[] | null) => void;
  setSentimentLoading: (loading: boolean) => void;
  setConsistencyResult: (result: ConsistencyResponse | null) => void;
  setConsistencyLoading: (loading: boolean) => void;
}
```

Do not keep `betaReaderPanelOpen`, `readabilityPanelOpen`, `povPanelOpen`, `coreferencePanelOpen`, `characterVoicePanelOpen`, `voiceCheckPanelOpen`, `sentimentPanelOpen`, `consistencyPanelOpen`, or `generationPanelOpen` in `EditorState` after this task.

- [ ] **Step 5: Wire Zustand store to the typed controller**

Modify `packages/web/lib/stores/editorStore.ts` to initialize and update `rightPanel`. First remove this entire import block:

```ts
import {
  toggleBetaReaderPanel,
  toggleCharacterVoicePanel,
  toggleConsistencyPanel,
  toggleCoreferencePanel,
  togglePovPanel,
  toggleReadabilityPanel,
  toggleSentimentPanel,
  toggleVoiceCheckPanel,
} from "./editorPanelToggles";
```

Then add the typed controller import immediately after `import { create } from "zustand";` and replace the store initializer with the following shape. Keep the listed non-panel members present with the exact member names shown here: `activeChapterId`, `activeVolumeId`, `saveStatus`, `lastSavedAt`, `sidebarOpen`, `focusMode`, `storyboardOpen`, `editor`, `isDragging`, `isGenerating`, `activeRequestId`, `generationMode`, `draftText`, `sessionActive`, `extractionPanelOpen`, `betaReaderResult`, `betaReaderLoading`, `sentimentResult`, `sentimentLoading`, `consistencyResult`, `consistencyLoading`, `setActiveChapterId`, `setActiveVolumeId`, `setSaveStatus`, `setEditor`, `setIsDragging`, `toggleSidebar`, `toggleFocusMode`, `toggleStoryboard`, `updateChapterWordCount`, `setGenerating`, `setActiveRequestId`, `setGenerationMode`, `setDraftText`, `setSessionActive`, `toggleExtractionPanel`, `setBetaReaderResult`, `setBetaReaderLoading`, `setSentimentResult`, `setSentimentLoading`, `setConsistencyResult`, and `setConsistencyLoading`.

```ts
import {
  CLOSED_EDITOR_RIGHT_PANEL_STATE,
  closeEditorRightPanel,
  openEditorRightPanel,
  toggleEditorRightPanel,
} from "./editorRightPanelState";

export const useEditorStore = create<EditorState>((set) => ({
  activeChapterId: null,
  activeVolumeId: null,
  saveStatus: "idle",
  lastSavedAt: null,
  sidebarOpen: true,
  rightPanel: CLOSED_EDITOR_RIGHT_PANEL_STATE,
  focusMode: false,
  storyboardOpen: false,
  editor: null,
  isDragging: false,
  isGenerating: false,
  activeRequestId: null,
  generationMode: null,
  draftText: "",
  sessionActive: false,
  extractionPanelOpen: false,
  betaReaderResult: null,
  betaReaderLoading: false,
  sentimentResult: null,
  sentimentLoading: false,
  consistencyResult: null,
  consistencyLoading: false,

  openRightPanel: (panel, requestedBy) =>
    set((s) => ({ rightPanel: openEditorRightPanel(s.rightPanel, panel, requestedBy) })),
  closeRightPanel: (panel) =>
    set((s) => ({ rightPanel: closeEditorRightPanel(s.rightPanel, panel ?? s.rightPanel.active) })),
  toggleRightPanel: (panel, requestedBy) =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, panel, requestedBy) })),
  toggleContextPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "metadata", "toolbar") })),
  toggleGenerationPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "generation", "toolbar") })),
  setSessionActive: (sessionActive) =>
    set((s) => ({
      sessionActive,
      rightPanel: sessionActive
        ? openEditorRightPanel(s.rightPanel, "session", "recovery")
        : closeEditorRightPanel(s.rightPanel, "session"),
    })),
  toggleBetaReaderPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "beta_reader", "toolbar") })),
  toggleSentimentPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "sentiment", "toolbar") })),
  toggleConsistencyPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "consistency", "toolbar") })),
  toggleReadabilityPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "readability", "toolbar") })),
  togglePovPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "pov", "toolbar") })),
  toggleCoreferencePanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "coreference", "toolbar") })),
  toggleCharacterVoicePanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "character_voice", "toolbar") })),
  toggleVoiceCheckPanel: () =>
    set((s) => ({ rightPanel: toggleEditorRightPanel(s.rightPanel, "voice_check", "toolbar") })),

  setActiveChapterId: (id) => set({ activeChapterId: id }),
  setActiveVolumeId: (id) => set({ activeVolumeId: id }),
  setSaveStatus: (saveStatus) => set({ saveStatus, lastSavedAt: saveStatus === "saved" ? new Date() : null }),
  setEditor: (editor) => set({ editor }),
  setIsDragging: (isDragging) => set({ isDragging }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleFocusMode: () => set((s) => ({ focusMode: !s.focusMode })),
  toggleStoryboard: () => set((s) => ({ storyboardOpen: !s.storyboardOpen })),

  /** Pure function: caller syncs returned chapter array to TanStack Query cache. */
  updateChapterWordCount: (chapterId, wordCount, chapters) =>
    chapters.map((c) => (c.id === chapterId ? { ...c, word_count: wordCount } : c)),

  setGenerating: (isGenerating) => set({ isGenerating }),
  setActiveRequestId: (activeRequestId) => set({ activeRequestId }),
  setGenerationMode: (generationMode) => set({ generationMode }),
  setDraftText: (draftText) => set({ draftText }),
  toggleExtractionPanel: () => set((s) => ({ extractionPanelOpen: !s.extractionPanelOpen })),
  setBetaReaderResult: (betaReaderResult) => set({ betaReaderResult }),
  setBetaReaderLoading: (betaReaderLoading) => set({ betaReaderLoading }),
  setSentimentResult: (sentimentResult) => set({ sentimentResult }),
  setSentimentLoading: (sentimentLoading) => set({ sentimentLoading }),
  setConsistencyResult: (consistencyResult) => set({ consistencyResult }),
  setConsistencyLoading: (consistencyLoading) => set({ consistencyLoading }),
}));
```

Delete `packages/web/lib/stores/editorPanelToggles.ts` in this same step. `editorStore.ts` must not import from it after the typed controller actions above are inlined, and no other file may import it because `editorStore.ts` is the only current importer. Do not recreate the helper file and do not add a Task 2 type-check checkpoint; component call-site migration is deliberately completed in Task 3 before the next type-check gate.

- [ ] **Step 6: Replace visibility hook with active-panel selector**

Create `packages/web/components/studio/editor-view/useActiveEditorRightPanel.ts`:

```ts
import { useEditorStore } from "@/lib/stores/editorStore";
import type { EditorRightPanelId } from "@/lib/stores/editorRightPanelState";

export function useActiveEditorRightPanel(activeChapterId: string | null): EditorRightPanelId | null {
  const active = useEditorStore((s) => s.rightPanel.active);
  if (!activeChapterId) return null;
  return active;
}
```

- [ ] **Step 7: Run reducer tests and continue without a checkpoint**

Run: `pnpm --dir packages/web test lib/stores/editorRightPanelState.test.ts`

Expected: PASS.

Do not run `pnpm --dir packages/web type-check` and do not commit at the end of Task 2. The known remaining work is Task 3 component call-site migration; the next checkpoint is Task 3 Step 11 after type-check passes.

### Task 3: Editor Right-Panel Slot Rendering, URL Sync, and Phase-C Accessibility

**Files:**
- Create: `packages/web/components/studio/editor-view/EditorRightPanelSlot.tsx`
- Create: `packages/web/components/studio/editor-view/EditorRightPanelSlot.test.tsx`
- Create: `packages/web/components/studio/editor-view/editorRightPanelUrlState.ts`
- Create: `packages/web/components/studio/editor-view/editorRightPanelUrlState.test.ts`
- Modify: `packages/web/components/studio/EditorView.tsx`
- Modify: `packages/web/components/studio/editor-view/EditorToolbar.tsx`
- Delete: `packages/web/components/studio/editor-view/useEditorPanelVisibility.ts`
- Delete: `packages/web/components/studio/editor-view/EditorSidePanels.tsx`
- Modify: `packages/web/components/studio/__tests__/EditorView.test.tsx`

**Interfaces:**
- Produces:
  - `interface EditorRightPanelSlotProps` carrying the existing panel data plus `activePanel: EditorRightPanelId | null`, `closePanel: (panel?: EditorRightPanelId) => void`, and optional `returnFocusTo?: HTMLElement | null`.
  - `parseEditorRightPanelParam(value: string | null): EditorRightPanelId | null`
  - `serializeEditorRightPanelParam(panel: EditorRightPanelId | null): string | null`
- Consumes:
  - `useActiveEditorRightPanel`, `useEditorStore((s) => s.toggleRightPanel)`, and existing panel components.

**Independently testable deliverable:** `EditorView` renders all right-side editor panels through `EditorRightPanelSlot`, toolbar buttons call typed panel actions, obsolete visibility files are deleted, URL-safe panel parsing is covered, and the checkpoint commit is `refactor(web): render editor panels through typed right slot`.

- [ ] **Step 1: Write URL adapter tests for safe editor panel params**

Create `packages/web/components/studio/editor-view/editorRightPanelUrlState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseEditorRightPanelParam, serializeEditorRightPanelParam } from "./editorRightPanelUrlState";

describe("editor right panel URL state", () => {
  it("parses safe deep-linkable panels", () => {
    expect(parseEditorRightPanelParam("metadata")).toBe("metadata");
    expect(parseEditorRightPanelParam("readability")).toBe("readability");
    expect(parseEditorRightPanelParam("voice_check")).toBe("voice_check");
  });

  it("does not deep-link unsafe session recovery without explicit recovery contract", () => {
    expect(parseEditorRightPanelParam("session")).toBeNull();
  });

  it("serializes null by removing the param", () => {
    expect(serializeEditorRightPanelParam(null)).toBeNull();
  });
});
```

- [ ] **Step 2: Write slot rendering and accessibility tests**

Create `packages/web/components/studio/editor-view/EditorRightPanelSlot.test.tsx` with mocked child panels:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EditorRightPanelSlot } from "./EditorRightPanelSlot";

vi.mock("../editor/MetadataSidebar", () => ({ MetadataSidebar: () => <div data-testid="metadata-sidebar" /> }));
vi.mock("../kb/WikiChapterSummaryPanel", () => ({ WikiChapterSummaryPanel: () => <div /> }));
vi.mock("../analysis/ReadabilityPanel", () => ({
  ReadabilityPanel: ({ onClose }: { onClose: () => void }) => (
    <section data-testid="readability-panel"><button type="button" onClick={onClose}>close</button></section>
  ),
}));
vi.mock("../editor/SessionPanel", () => ({ SessionPanel: () => <section data-testid="session-panel" /> }));
vi.mock("../editor/GenerationPanel", () => ({ GenerationPanel: () => <section data-testid="generation-panel" /> }));
vi.mock("../analysis/BetaReaderPanel", () => ({ BetaReaderPanel: () => <section data-testid="beta-reader-panel" /> }));
vi.mock("../analysis/POVPanel", () => ({ POVPanel: () => <section data-testid="pov-panel" /> }));
vi.mock("../analysis/CoreferencePanel", () => ({ CoreferencePanel: () => <section data-testid="coreference-panel" /> }));
vi.mock("../analysis/CharacterVoicePanel", () => ({ CharacterVoicePanel: () => <section data-testid="character-voice-panel" /> }));
vi.mock("../analysis/VoiceCheckPanel", () => ({ VoiceCheckPanel: () => <section data-testid="voice-check-panel" /> }));
vi.mock("../analysis/SentimentPanel", () => ({ SentimentPanel: () => <section data-testid="sentiment-panel" /> }));
vi.mock("../analysis/ConsistencyPanel", () => ({ ConsistencyPanel: () => <section data-testid="consistency-panel" /> }));

const baseProps = {
  novelId: "novel-1",
  activeChapterId: "chapter-1",
  content: "<p>text</p>",
  chapter: undefined,
  chapters: [],
  sessionStartWordCount: 0,
  volumeStats: undefined,
  wordCount: 10,
  charCount: 50,
  paragraphCount: 1,
  sessionMode: "interactive_session" as const,
  handleSessionClose: vi.fn(),
  handleDraftAccepted: vi.fn(),
  handleStartSession: vi.fn(),
  closePanel: vi.fn(),
};

describe("EditorRightPanelSlot", () => {
  it("renders exactly the active panel occupant", () => {
    render(<EditorRightPanelSlot {...baseProps} activePanel="readability" />);
    expect(screen.getByTestId("readability-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("metadata-sidebar")).not.toBeInTheDocument();
  });

  it("renders no right slot when active panel is null", () => {
    render(<EditorRightPanelSlot {...baseProps} activePanel={null} />);
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });

  it("closes active panel on Escape", () => {
    const closePanel = vi.fn();
    render(<EditorRightPanelSlot {...baseProps} activePanel="metadata" closePanel={closePanel} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(closePanel).toHaveBeenCalledWith("metadata");
  });
});
```

- [ ] **Step 3: Run slot tests and verify failure**

Run: `pnpm --dir packages/web test components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/editor-view/editorRightPanelUrlState.test.ts`

Expected: FAIL because the new files do not exist.

- [ ] **Step 4: Implement editor right-panel URL adapter**

Create `packages/web/components/studio/editor-view/editorRightPanelUrlState.ts`:

```ts
import type { EditorRightPanelId } from "@/lib/stores/editorRightPanelState";
import { isEditorRightPanelId } from "@/lib/stores/editorRightPanelState";

const UNSAFE_DEEP_LINK_PANELS = new Set<EditorRightPanelId>(["session"]);

export function parseEditorRightPanelParam(value: string | null): EditorRightPanelId | null {
  if (!isEditorRightPanelId(value)) return null;
  if (UNSAFE_DEEP_LINK_PANELS.has(value)) return null;
  return value;
}

export function serializeEditorRightPanelParam(panel: EditorRightPanelId | null): string | null {
  if (panel === null || UNSAFE_DEEP_LINK_PANELS.has(panel)) return null;
  return panel;
}
```

- [ ] **Step 5: Implement the single right-panel slot**

Create `packages/web/components/studio/editor-view/EditorRightPanelSlot.tsx` with this complete content. Do not import `EditorPanelVisibility` or `EditorSidePanels`, and do not import through barrel files.

```tsx
"use client";

import { useTranslations } from "next-intl";
import { useEffect } from "react";
import type { EditorRightPanelId } from "@/lib/stores/editorRightPanelState";
import type { Chapter, ChapterSummary, VolumeStats } from "@/types";
import { BetaReaderPanel } from "../analysis/BetaReaderPanel";
import { CharacterVoicePanel } from "../analysis/CharacterVoicePanel";
import { ConsistencyPanel } from "../analysis/ConsistencyPanel";
import { CoreferencePanel } from "../analysis/CoreferencePanel";
import { POVPanel } from "../analysis/POVPanel";
import { ReadabilityPanel } from "../analysis/ReadabilityPanel";
import { SentimentPanel } from "../analysis/SentimentPanel";
import { VoiceCheckPanel } from "../analysis/VoiceCheckPanel";
import { GenerationPanel } from "../editor/GenerationPanel";
import { MetadataSidebar } from "../editor/MetadataSidebar";
import { SessionPanel } from "../editor/SessionPanel";
import { WikiChapterSummaryPanel } from "../kb/WikiChapterSummaryPanel";

export interface EditorRightPanelSlotProps {
  activePanel: EditorRightPanelId | null;
  closePanel: (panel?: EditorRightPanelId) => void;
  returnFocusTo?: HTMLElement | null;
  novelId: string;
  activeChapterId: string;
  content: string;
  chapter: Chapter | undefined;
  chapters: ChapterSummary[];
  sessionStartWordCount: number;
  volumeStats: VolumeStats | undefined;
  wordCount: number;
  charCount: number;
  paragraphCount: number;
  sessionMode: "interactive_session" | "interview_assisted";
  handleSessionClose: () => void;
  handleDraftAccepted: (text: string) => void;
  handleStartSession: (mode: string) => void;
}

export function EditorRightPanelSlot({
  activePanel,
  closePanel,
  returnFocusTo,
  novelId,
  activeChapterId,
  content,
  chapter,
  chapters,
  sessionStartWordCount,
  volumeStats,
  wordCount,
  charCount,
  paragraphCount,
  sessionMode,
  handleSessionClose,
  handleDraftAccepted,
  handleStartSession,
}: EditorRightPanelSlotProps) {
  const t = useTranslations("studio");

  useEffect(() => {
    if (activePanel === null) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closePanel(activePanel);
        if (returnFocusTo?.isConnected) returnFocusTo.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activePanel, closePanel, returnFocusTo]);

  if (activePanel === null) return null;

  const panelTitleId = "editor-right-panel-title";
  const panelContent = (() => {
    switch (activePanel) {
      case "session":
        return (
          <SessionPanel
            chapterId={activeChapterId}
            novelId={novelId}
            mode={sessionMode}
            onClose={handleSessionClose}
          />
        );
      case "generation":
        return (
          <GenerationPanel
            novelId={novelId}
            chapterId={activeChapterId}
            chapterContent={content}
            onDraftAccepted={handleDraftAccepted}
            onClose={() => closePanel("generation")}
            onStartSession={handleStartSession}
          />
        );
      case "metadata":
        return (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <MetadataSidebar
              wordCount={wordCount}
              charCount={charCount}
              paragraphCount={paragraphCount}
              chapter={chapter ?? null}
              chapters={chapters}
              sessionStartWordCount={sessionStartWordCount}
              activeVolumeStats={volumeStats ?? null}
            />
            <div className="px-4 pb-4">
              <WikiChapterSummaryPanel
                novelId={novelId}
                chapterId={activeChapterId}
                chapterTitle={chapter?.title}
              />
            </div>
          </div>
        );
      case "beta_reader":
        return <BetaReaderPanel novelId={novelId} chapterIds={[activeChapterId]} onClose={() => closePanel("beta_reader")} />;
      case "readability":
        return <ReadabilityPanel novelId={novelId} chapterIds={[activeChapterId]} onClose={() => closePanel("readability")} />;
      case "pov":
        return <POVPanel novelId={novelId} chapterIds={[activeChapterId]} onClose={() => closePanel("pov")} />;
      case "coreference":
        return <CoreferencePanel novelId={novelId} chapterIds={[activeChapterId]} onClose={() => closePanel("coreference")} />;
      case "character_voice":
        return <CharacterVoicePanel novelId={novelId} chapterIds={[activeChapterId]} onClose={() => closePanel("character_voice")} />;
      case "voice_check":
        return <VoiceCheckPanel chapterId={activeChapterId} onClose={() => closePanel("voice_check")} />;
      case "sentiment":
        return <SentimentPanel novelId={novelId} chapterIds={[activeChapterId]} onClose={() => closePanel("sentiment")} />;
      case "consistency":
        return <ConsistencyPanel novelId={novelId} chapterIds={[activeChapterId]} onClose={() => closePanel("consistency")} />;
      default: {
        const _exhaustive: never = activePanel;
        return _exhaustive;
      }
    }
  })();

  return (
    <aside
      role="region"
      aria-labelledby={panelTitleId}
      className="hidden h-full w-96 shrink-0 border-l border-border bg-card lg:flex lg:flex-col"
    >
      <h2 id={panelTitleId} className="sr-only">
        {t("shell.editorRightPanel")}
      </h2>
      {panelContent}
    </aside>
  );
}
```

- [ ] **Step 6: Wire EditorView and Toolbar to typed active panel**

Modify `packages/web/components/studio/EditorView.tsx` with these exact replacements:

1. Remove imports of `EditorSidePanels` and `useEditorPanelVisibility`. Add imports for the new slot and selector:

```tsx
import { EditorRightPanelSlot } from "./editor-view/EditorRightPanelSlot";
import { useActiveEditorRightPanel } from "./editor-view/useActiveEditorRightPanel";
```

2. Replace this selector block:

```tsx
const generationPanelOpen = useEditorStore((s) => s.generationPanelOpen);
const toggleGenerationPanel = useEditorStore((s) => s.toggleGenerationPanel);
const extractionPanelOpen = useEditorStore((s) => s.extractionPanelOpen);
const toggleExtractionPanel = useEditorStore((s) => s.toggleExtractionPanel);
const toggleBetaReaderPanel = useEditorStore((s) => s.toggleBetaReaderPanel);
const toggleSentimentPanel = useEditorStore((s) => s.toggleSentimentPanel);
const toggleConsistencyPanel = useEditorStore((s) => s.toggleConsistencyPanel);
const toggleReadabilityPanel = useEditorStore((s) => s.toggleReadabilityPanel);
const togglePovPanel = useEditorStore((s) => s.togglePovPanel);
const toggleCoreferencePanel = useEditorStore((s) => s.toggleCoreferencePanel);
const toggleCharacterVoicePanel = useEditorStore((s) => s.toggleCharacterVoicePanel);
const toggleVoiceCheckPanel = useEditorStore((s) => s.toggleVoiceCheckPanel);
```

with:

```tsx
const extractionPanelOpen = useEditorStore((s) => s.extractionPanelOpen);
const toggleExtractionPanel = useEditorStore((s) => s.toggleExtractionPanel);
const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
const closeRightPanel = useEditorStore((s) => s.closeRightPanel);
```

3. Replace `const panelVisibility = useEditorPanelVisibility(activeChapterId);` with:

```tsx
const activeRightPanel = useActiveEditorRightPanel(activeChapterId);
```

4. Replace the current `EditorToolbar` element in `EditorView.tsx` with:

```tsx

<EditorToolbar
  editor={editor}
  activeRightPanel={activeRightPanel}
  extractionPanelOpen={extractionPanelOpen}
  toggleRightPanel={toggleRightPanel}
  toggleExtractionPanel={toggleExtractionPanel}
  openNameGenerator={() => setNameGeneratorOpen(true)}
/>
```

5. Replace the current `EditorSidePanels` component element in `EditorView.tsx` with:

```tsx
<EditorRightPanelSlot
  activePanel={activeRightPanel}
  closePanel={closeRightPanel}
  novelId={novelId}
  activeChapterId={activeChapterId}
  content={chapterData.content}
  chapter={chapterData.chapter}
  chapters={chapterData.chapters}
  sessionStartWordCount={chapterData.sessionStartWordCount}
  volumeStats={chapterData.volumeStats}
  wordCount={chapterData.wordCount}
  charCount={chapterData.charCount}
  paragraphCount={chapterData.paragraphCount}
  sessionMode={generationActions.sessionMode}
  handleSessionClose={generationActions.handleSessionClose}
  handleDraftAccepted={generationActions.handleDraftAccepted}
  handleStartSession={generationActions.handleStartSession}
/>
```

Modify `packages/web/components/studio/editor-view/EditorToolbar.tsx` with these exact replacements:

1. Add the type import:

```ts
import type { EditorRightPanelId, EditorRightPanelRequestSource } from "@/lib/stores/editorRightPanelState";
```

2. Replace `EditorToolbarProps` with:

```ts

interface EditorToolbarProps {
  editor: Editor | null;
  activeRightPanel: EditorRightPanelId | null;
  extractionPanelOpen: boolean;
  toggleRightPanel: (panel: EditorRightPanelId, requestedBy: EditorRightPanelRequestSource) => void;
  toggleExtractionPanel: () => void;
  openNameGenerator: () => void;
}
```

3. Replace the function parameter destructuring so it uses `activeRightPanel` and `toggleRightPanel` instead of `generationPanelOpen`, `toggleGenerationPanel`, and `toggleVoiceCheckPanel`.

4. Replace the generation button `onClick` and active class expression with:

```tsx
onClick={() => toggleRightPanel("generation", "toolbar")}
className={cn("flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary", activeRightPanel === "generation" && "bg-accent")}
```

5. Replace the voice-check trigger with:

```tsx
<VoiceCheckTrigger onClick={() => toggleRightPanel("voice_check", "toolbar")} />
```

- [ ] **Step 7: Delete obsolete visibility files**

Delete:

```text
packages/web/components/studio/editor-view/useEditorPanelVisibility.ts
packages/web/components/studio/editor-view/EditorSidePanels.tsx
```

Run: `rg "useEditorPanelVisibility|EditorSidePanels" packages/web/components/studio packages/web/lib || true`

Expected: empty stdout; no remaining import or usage references the deleted visibility files.

- [ ] **Step 8: Update EditorView tests to the new store shape**

Modify `packages/web/components/studio/__tests__/EditorView.test.tsx` mocked store defaults from booleans to:

```ts
rightPanel: { active: null, previous: null, requestedBy: null },
toggleRightPanel: vi.fn(),
closeRightPanel: vi.fn(),
openRightPanel: vi.fn(),
```

Replace panel-open test setup:

```ts
editorStoreState = {
  activeChapterId: "chapter-1",
  rightPanel: { active: "metadata", previous: null, requestedBy: "toolbar" },
};
```

For voice-check:

```ts
editorStoreState = {
  activeChapterId: "chapter-1",
  rightPanel: { active: "voice_check", previous: null, requestedBy: "toolbar" },
};
```

- [ ] **Step 9: Run focused editor panel tests**

Run: `pnpm --dir packages/web test lib/stores/editorRightPanelState.test.ts components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/editor-view/editorRightPanelUrlState.test.ts components/studio/__tests__/EditorView.test.tsx`

Expected: PASS. No test should rely on multiple open right-panel booleans.

- [ ] **Step 10: Type-check editor panel refactor**

Run: `pnpm --dir packages/web type-check`

Expected: PASS with no references to removed right-panel boolean fields.

- [ ] **Step 11: Commit checkpoint after coordinator approval**

Commit message: `refactor(web): render editor panels through typed right slot`

### Task 4: URL-State Adapters for Settings, Planning, KB, Analysis, and Editor Panel

**Files:**
- Create: `packages/web/lib/url-state/searchParams.ts`
- Create: `packages/web/components/studio/settings/settingsUrlState.ts`
- Create: `packages/web/components/studio/settings/settingsUrlState.test.ts`
- Create: `packages/web/components/studio/planning/planningUrlState.ts`
- Create: `packages/web/components/studio/planning/planningUrlState.test.ts`
- Create: `packages/web/components/studio/kb/kbUrlState.ts`
- Create: `packages/web/components/studio/kb/kbUrlState.test.ts`
- Create: `packages/web/components/studio/analysis/analysisUrlState.ts`
- Create: `packages/web/components/studio/analysis/analysisUrlState.test.ts`
- Modify: `packages/web/components/studio/SettingsView.tsx`
- Modify: `packages/web/components/studio/planning/PlanningPanel.tsx`
- Modify: `packages/web/components/studio/WorldBuilding.tsx`
- Modify: `packages/web/components/studio/_components/worldBuildingState.ts`
- Modify: `packages/web/components/studio/AnalysisPanel.tsx`
- Create: `packages/web/components/studio/planning/__tests__/PlanningPanel.test.tsx`

**Interfaces:**
- Produces:
  - `cloneSearchParams(searchParams: URLSearchParams): URLSearchParams`
  - `setOptionalSearchParam(searchParams: URLSearchParams, key: string, value: string | null): URLSearchParams`
  - `searchParamsHref(pathname: string, searchParams: URLSearchParams): string`
  - `type PlanningTab = "storyboard" | "timeline" | "characterArc"`
  - `type KBMode = "detail" | "create" | "assist" | "analysis" | "consistency" | "graph" | "wiki"`
  - `interface KBUrlState { type: KBEntityType | null; mode: KBMode; entryId: string | null; query: string }`
  - `type AnalysisPanelId = AnalysisType`
- Consumes:
  - `useRouter`, `usePathname`, `useSearchParams` from `next/navigation` in component-level hooks only.

**Independently testable deliverable:** Settings, Planning, KB, Analysis, and safe editor panel state round-trip through typed URL adapters without storing server data in URL/Zustand, and the checkpoint commit is `feat(web): add typed URL state adapters for workspace panels`.

- [ ] **Step 1: Write pure URL adapter tests**

Create tests with exact expectations:

`packages/web/components/studio/settings/settingsUrlState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseSettingsCategory, serializeSettingsCategory } from "./settingsUrlState";

describe("settings URL state", () => {
  it("parses valid category", () => expect(parseSettingsCategory("ai")).toBe("ai"));
  it("falls back for invalid category", () => expect(parseSettingsCategory("missing")).toBe("novel-details"));
  it("serializes default as null", () => expect(serializeSettingsCategory("novel-details")).toBeNull());
});
```

`packages/web/components/studio/planning/planningUrlState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parsePlanningUrlState, serializePlanningUrlState } from "./planningUrlState";

describe("planning URL state", () => {
  it("parses open timeline state", () => {
    expect(parsePlanningUrlState(new URLSearchParams("planning=1&planningTab=timeline"))).toEqual({
      open: true,
      tab: "timeline",
    });
  });
  it("keeps default collapsed state out of the URL", () => {
    expect(serializePlanningUrlState({ open: false, tab: "storyboard" }).toString()).toBe("");
  });
});
```

`packages/web/components/studio/kb/kbUrlState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseKBUrlState, serializeKBUrlState } from "./kbUrlState";

describe("KB URL state", () => {
  it("parses type mode search and entry", () => {
    expect(parseKBUrlState(new URLSearchParams("type=character&mode=detail&entry=e1&q=ada"))).toEqual({
      type: "character",
      mode: "detail",
      entryId: "e1",
      query: "ada",
    });
  });
  it("normalizes invalid mode to detail", () => {
    expect(parseKBUrlState(new URLSearchParams("mode=unknown"))).toMatchObject({ mode: "detail" });
  });
  it("removes default detail mode on serialize", () => {
    expect(serializeKBUrlState({ type: null, mode: "detail", entryId: null, query: "" }).toString()).toBe("");
  });
});
```

`packages/web/components/studio/analysis/analysisUrlState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseAnalysisPanelParam, serializeAnalysisPanelParam } from "./analysisUrlState";

describe("analysis URL state", () => {
  it("parses readability panel", () => expect(parseAnalysisPanelParam("readability")).toBe("readability"));
  it("returns null for invalid panel", () => expect(parseAnalysisPanelParam("missing")).toBeNull());
  it("serializes null by removing panel", () => expect(serializeAnalysisPanelParam(null)).toBeNull());
});
```

- [ ] **Step 2: Run URL adapter tests and verify failure**

Run: `pnpm --dir packages/web test components/studio/settings/settingsUrlState.test.ts components/studio/planning/planningUrlState.test.ts components/studio/kb/kbUrlState.test.ts components/studio/analysis/analysisUrlState.test.ts`

Expected: FAIL because adapters do not exist.

- [ ] **Step 3: Implement shared search-param helpers**

Create `packages/web/lib/url-state/searchParams.ts`:

```ts
export function cloneSearchParams(searchParams: URLSearchParams): URLSearchParams {
  return new URLSearchParams(searchParams.toString());
}

export function setOptionalSearchParam(
  searchParams: URLSearchParams,
  key: string,
  value: string | null,
): URLSearchParams {
  const next = cloneSearchParams(searchParams);
  if (value === null || value === "") next.delete(key);
  else next.set(key, value);
  return next;
}

export function searchParamsHref(pathname: string, searchParams: URLSearchParams): string {
  const query = searchParams.toString();
  return query.length > 0 ? `${pathname}?${query}` : pathname;
}
```

- [ ] **Step 4: Implement settings adapter and wire SettingsView**

Create `packages/web/components/studio/settings/settingsUrlState.ts`:

```ts
import { SETTINGS_CATEGORIES, type SettingsCategory } from "./settings-view-config";

const SETTINGS_CATEGORY_IDS = new Set<SettingsCategory>(SETTINGS_CATEGORIES.map((category) => category.id));
export const DEFAULT_SETTINGS_CATEGORY: SettingsCategory = "novel-details";

export function parseSettingsCategory(value: string | null): SettingsCategory {
  if (value !== null && SETTINGS_CATEGORY_IDS.has(value as SettingsCategory)) return value as SettingsCategory;
  return DEFAULT_SETTINGS_CATEGORY;
}

export function serializeSettingsCategory(category: SettingsCategory): string | null {
  return category === DEFAULT_SETTINGS_CATEGORY ? null : category;
}
```

Modify `SettingsView.tsx` with these exact replacements:

1. Add imports:

```tsx
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { searchParamsHref, setOptionalSearchParam } from "@/lib/url-state/searchParams";
import { DEFAULT_SETTINGS_CATEGORY, parseSettingsCategory, serializeSettingsCategory } from "./settings/settingsUrlState";
```

2. Replace the current `useState<SettingsCategory>("novel-details")` initializer with:

```tsx
const router = useRouter();
const pathname = usePathname();
const searchParams = useSearchParams();
const searchParamsSnapshot = searchParams.toString();
const parsedCategory = useMemo(
  () => parseSettingsCategory(new URLSearchParams(searchParamsSnapshot).get("category")),
  [searchParamsSnapshot],
);
const [activeCategory, setActiveCategory] = useState<SettingsCategory>(parsedCategory);
```

3. Add this normalization/sync effect immediately after state initialization:

```tsx
useEffect(() => {
  const currentParams = new URLSearchParams(searchParamsSnapshot);
  const currentValue = currentParams.get("category");
  const normalizedValue = serializeSettingsCategory(parsedCategory);
  const normalizedParams = setOptionalSearchParam(currentParams, "category", normalizedValue);

  setActiveCategory(parsedCategory);
  if (currentValue !== normalizedValue && !(currentValue === null && parsedCategory === DEFAULT_SETTINGS_CATEGORY)) {
    router.replace(searchParamsHref(pathname, normalizedParams), { scroll: false });
  }
}, [parsedCategory, pathname, router, searchParamsSnapshot]);
```

4. Replace category button handlers `onClick={() => setActiveCategory(category.id)}` with:

```tsx
onClick={() => {
  setActiveCategory(category.id);
  const nextParams = setOptionalSearchParam(
    new URLSearchParams(searchParamsSnapshot),
    "category",
    serializeSettingsCategory(category.id),
  );
  router.push(searchParamsHref(pathname, nextParams), { scroll: false });
}}
```

Do not store server data in URL or Zustand.

- [ ] **Step 5: Implement planning adapter and wire PlanningPanel**

Create `packages/web/components/studio/planning/planningUrlState.ts`:

```ts
export type PlanningTab = "storyboard" | "timeline" | "characterArc";

export interface PlanningUrlState {
  open: boolean;
  tab: PlanningTab;
}

const PLANNING_TABS = new Set<PlanningTab>(["storyboard", "timeline", "characterArc"]);

export function parsePlanningUrlState(searchParams: URLSearchParams): PlanningUrlState {
  const tabParam = searchParams.get("planningTab");
  return {
    open: searchParams.get("planning") === "1",
    tab: PLANNING_TABS.has(tabParam as PlanningTab) ? (tabParam as PlanningTab) : "storyboard",
  };
}

export function serializePlanningUrlState(state: PlanningUrlState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.open) params.set("planning", "1");
  if (state.open && state.tab !== "storyboard") params.set("planningTab", state.tab);
  return params;
}
```

Modify `PlanningPanel.tsx` with these exact changes:

1. Replace the local `PlanningTab` type with an import from the adapter and add navigation helpers:

```tsx
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { searchParamsHref } from "@/lib/url-state/searchParams";
import { parsePlanningUrlState, serializePlanningUrlState, type PlanningTab } from "./planningUrlState";
```

2. Replace `const [activeTab, setActiveTab] = useState<PlanningTab>("storyboard");` with:

```tsx
const router = useRouter();
const pathname = usePathname();
const searchParams = useSearchParams();
const searchParamsSnapshot = searchParams.toString();
const urlState = useMemo(
  () => parsePlanningUrlState(new URLSearchParams(searchParamsSnapshot)),
  [searchParamsSnapshot],
);
const [activeTab, setActiveTab] = useState<PlanningTab>(urlState.tab);
```

3. Add these helpers/effects before the collapsed-state `if` block:

```tsx
const pushPlanningState = (open: boolean, tab: PlanningTab) => {
  const nextParams = serializePlanningUrlState({ open, tab });
  router.push(searchParamsHref(pathname, nextParams), { scroll: false });
};

useEffect(() => {
  setActiveTab(urlState.tab);
  if (storyboardOpen !== urlState.open) toggleStoryboard();
}, [storyboardOpen, toggleStoryboard, urlState.open, urlState.tab]);
```

4. Replace the collapsed button `onClick={toggleStoryboard}` with:

```tsx
onClick={() => {
  if (!storyboardOpen) toggleStoryboard();
  pushPlanningState(true, activeTab);
}}
```

5. Replace the three tab button handlers `onClick={() => setActiveTab("storyboard")}`, `onClick={() => setActiveTab("timeline")}`, and `onClick={() => setActiveTab("characterArc")}` with this pattern using each handler's matching tab value:

```tsx
onClick={() => {
  setActiveTab("timeline");
  pushPlanningState(true, "timeline");
}}
```

Use `"storyboard"`, `"timeline"`, and `"characterArc"` for the three tab buttons respectively. Keep `storyboardOpen` only as the existing Zustand mirror for toolbar compatibility.

- [ ] **Step 6: Implement KB adapter and replace mode booleans**

Create `packages/web/components/studio/kb/kbUrlState.ts`:

```ts
import type { KBEntityType } from "@/lib/api/kb";

export type KBMode = "detail" | "create" | "assist" | "analysis" | "consistency" | "graph" | "wiki";

export interface KBUrlState {
  type: KBEntityType | null;
  mode: KBMode;
  entryId: string | null;
  query: string;
}

const KB_TYPES = new Set<KBEntityType>([
  "character",
  "location",
  "artifact",
  "region",
  "religion",
  "magic_system",
  "concept",
]);
const KB_MODES = new Set<KBMode>(["detail", "create", "assist", "analysis", "consistency", "graph", "wiki"]);

export function parseKBUrlState(searchParams: URLSearchParams): KBUrlState {
  const typeParam = searchParams.get("type");
  const modeParam = searchParams.get("mode");
  return {
    type: KB_TYPES.has(typeParam as KBEntityType) ? (typeParam as KBEntityType) : null,
    mode: KB_MODES.has(modeParam as KBMode) ? (modeParam as KBMode) : "detail",
    entryId: searchParams.get("entry"),
    query: searchParams.get("q") ?? "",
  };
}

export function serializeKBUrlState(state: KBUrlState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.type) params.set("type", state.type);
  if (state.mode !== "detail") params.set("mode", state.mode);
  if (state.entryId) params.set("entry", state.entryId);
  if (state.query.trim().length > 0) params.set("q", state.query.trim());
  return params;
}
```

Modify `worldBuildingState.ts` and `WorldBuilding.tsx` with these concrete changes:

1. In `worldBuildingState.ts`, import `type { KBMode, KBUrlState }` from `../kb/kbUrlState` and change the hook signature to:

```ts
export function useWorldBuildingState(novelId: string, initialUrlState: KBUrlState) {
```

2. Replace these state initializers:

```ts
const [activeType, setActiveType] = useState<KBEntityType | null>(null);
const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
const [isCreating, setIsCreating] = useState(false);
const [showAnalysis, setShowAnalysis] = useState(false);
const [showConsistency, setShowConsistency] = useState(false);
const [showGraph, setShowGraph] = useState(false);
const [showWiki, setShowWiki] = useState(false);
```

with:

```ts
const [activeType, setActiveType] = useState<KBEntityType | null>(initialUrlState.type);
const [selectedEntryId, setSelectedEntryId] = useState<string | null>(initialUrlState.entryId);
const [isCreating, setIsCreating] = useState(initialUrlState.mode === "create");
const [mode, setMode] = useState<KBMode>(initialUrlState.mode);
```

3. Replace `resetModes()` with:

```ts
function resetModes() {
  setMode("detail");
}
```

4. Replace every `setShowAnalysis(false)`, `setShowConsistency(false)`, `setShowGraph(false)`, and `setShowWiki(false)` call inside `startNewAssistedSession`, `handleSelectEntry`, `handleCreateNew`, `handleResumeInterview`, `handleShowAnalysis`, `handleShowConsistency`, `handleShowGraph`, and `handleShowWiki` with `setMode("detail")` unless the handler sets a different mode in the next snippet.

5. Replace the mode handlers exactly as follows:

```ts
function handleShowAnalysis() {
  setMode("analysis");
  resetSelectionForMode();
}

function handleShowConsistency() {
  setMode("consistency");
  resetSelectionForMode();
}

function handleShowGraph() {
  setMode("graph");
  resetSelectionForMode();
}

function handleShowWiki() {
  setMode("wiki");
  resetSelectionForMode();
}

function handleCloseWiki() {
  setMode("detail");
}
```

6. Return `mode`, `setMode`, and derived booleans so existing layout props can migrate one at a time without duplicate state. Remove `setShowAnalysis` and `setShowConsistency` from the returned object; callers must use `setMode("detail")` for closes.

```ts
mode,
setMode,
showAnalysis: mode === "analysis",
showConsistency: mode === "consistency",
showGraph: mode === "graph",
showWiki: mode === "wiki",
handleCloseWiki,
```

7. Keep `showResumeDialog` unchanged and local because it is a destructive/resume prompt, not shareable state.

8. In `WorldBuilding.tsx`, add imports:

```tsx
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { searchParamsHref } from "@/lib/url-state/searchParams";
import { parseKBUrlState, serializeKBUrlState, type KBUrlState } from "./kb/kbUrlState";
```

9. Replace `const state = useWorldBuildingState(novelId);` with:

```tsx
const router = useRouter();
const pathname = usePathname();
const searchParams = useSearchParams();
const searchParamsSnapshot = searchParams.toString();
const urlState = useMemo(
  () => parseKBUrlState(new URLSearchParams(searchParamsSnapshot)),
  [searchParamsSnapshot],
);
const state = useWorldBuildingState(novelId, urlState);
```

10. Add these URL-writing wrappers immediately after `entries` is computed and before `layoutProps`:

```tsx
const pushKBState = (nextState: KBUrlState) => {
  router.push(searchParamsHref(pathname, serializeKBUrlState(nextState)), { scroll: false });
};

const handleTypeChange = (type: KBUrlState["type"]) => {
  state.handleTypeChange(type);
  pushKBState({ type, mode: "detail", entryId: null, query: urlState.query });
};

const handleSelectEntry = (entryId: string) => {
  state.handleSelectEntry(entryId);
  pushKBState({ ...urlState, mode: "detail", entryId });
};

const handleCreateNew = () => {
  state.handleCreateNew();
  pushKBState({ ...urlState, mode: "create", entryId: null });
};

const handleCreateAssisted = () => {
  state.handleCreateAssisted();
  pushKBState({ ...urlState, mode: "assist", entryId: null });
};

const handleAnalyze = () => {
  state.handleShowAnalysis();
  pushKBState({ ...urlState, mode: "analysis" });
};

const handleConsistencyCheck = () => {
  state.handleShowConsistency();
  pushKBState({ ...urlState, mode: "consistency" });
};

const handleShowGraph = () => {
  state.handleShowGraph();
  pushKBState({ ...urlState, mode: "graph" });
};

const handleShowWiki = () => {
  state.handleShowWiki();
  pushKBState({ ...urlState, mode: "wiki" });
};

const handleCloseMode = () => {
  state.setMode("detail");
  pushKBState({ ...urlState, mode: "detail" });
};
```

11. In `layoutProps`, replace `onSelectEntry: state.handleSelectEntry`, `onCreateNew: state.handleCreateNew`, `onCreateAssisted: state.handleCreateAssisted`, `onTypeChange: state.handleTypeChange`, `onAnalyze: state.handleShowAnalysis`, `onConsistencyCheck: state.handleShowConsistency`, `onShowGraph: state.handleShowGraph`, and `onShowWiki: state.handleShowWiki` with `handleSelectEntry`, `handleCreateNew`, `handleCreateAssisted`, `handleTypeChange`, `handleAnalyze`, `handleConsistencyCheck`, `handleShowGraph`, and `handleShowWiki` respectively.

12. Replace panel close callbacks exactly:

```tsx
<WorldbuildingAnalysisPanel novelId={novelId} onClose={handleCloseMode} />

<ConsistencyCheckPanel
  novelId={novelId}
  onClose={handleCloseMode}
  onEntityClick={(entityId) => {
    handleSelectEntry(entityId);
    state.setMode("detail");
  }}
/>

<WikiOverviewPanel novelId={novelId} onClose={handleCloseMode} />
```

Do not put fetched KB entry bodies or relationship data into URL or Zustand.

- [ ] **Step 7: Implement analysis adapter and wire AnalysisPanel**

Create `packages/web/components/studio/analysis/analysisUrlState.ts`:

```ts
import { ANALYSIS_TYPES, type AnalysisType } from "../analysis-data";

const ANALYSIS_IDS = new Set<AnalysisType>(ANALYSIS_TYPES.map((analysis) => analysis.id));

export function parseAnalysisPanelParam(value: string | null): AnalysisType | null {
  if (value !== null && ANALYSIS_IDS.has(value as AnalysisType)) return value as AnalysisType;
  return null;
}

export function serializeAnalysisPanelParam(panel: AnalysisType | null): string | null {
  return panel;
}
```

Modify `AnalysisPanel.tsx` with these exact replacements:

1. Add imports:

```tsx
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { searchParamsHref, setOptionalSearchParam } from "@/lib/url-state/searchParams";
import { parseAnalysisPanelParam, serializeAnalysisPanelParam } from "./analysis/analysisUrlState";
```

2. Replace the current `activeAnalysis` initialization with:

```tsx
const router = useRouter();
const pathname = usePathname();
const searchParams = useSearchParams();
const searchParamsSnapshot = searchParams.toString();
const parsedPanel = useMemo(
  () => parseAnalysisPanelParam(new URLSearchParams(searchParamsSnapshot).get("panel")),
  [searchParamsSnapshot],
);
const [activeAnalysis, setActiveAnalysis] = useState<AnalysisType | null>(parsedPanel);
```

3. Add this sync/normalization effect:

```tsx
useEffect(() => {
  setActiveAnalysis(parsedPanel);
  const currentParams = new URLSearchParams(searchParamsSnapshot);
  const currentValue = currentParams.get("panel");
  if (currentValue !== null && parsedPanel === null) {
    const normalizedParams = setOptionalSearchParam(currentParams, "panel", null);
    router.replace(searchParamsHref(pathname, normalizedParams), { scroll: false });
  }
}, [parsedPanel, pathname, router, searchParamsSnapshot]);
```

4. Replace the analyze button click handler with a helper that preserves toggle semantics and writes URL state:

```tsx
const handleAnalysisSelect = (analysisId: AnalysisType) => {
  const nextPanel = activeAnalysis === analysisId ? null : analysisId;
  setActiveAnalysis(nextPanel);
  const nextParams = setOptionalSearchParam(
    new URLSearchParams(searchParamsSnapshot),
    "panel",
    serializeAnalysisPanelParam(nextPanel),
  );
  router.push(searchParamsHref(pathname, nextParams), { scroll: false });
};
```

Use `onClick={() => handleAnalysisSelect(analysis.id)}` on the existing analysis buttons.

- [ ] **Step 8: Wire safe editor panel URL sync**

Modify `EditorView.tsx` with these exact URL-sync additions:

1. Add imports:

```tsx
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";
import { searchParamsHref, setOptionalSearchParam } from "@/lib/url-state/searchParams";
import { parseEditorRightPanelParam, serializeEditorRightPanelParam } from "./editor-view/editorRightPanelUrlState";
```

2. Add selector reads beside the existing right-panel selectors:

```tsx
const openRightPanel = useEditorStore((s) => s.openRightPanel);
const openerRef = useRef<HTMLElement | null>(null);
```

3. Add URL parsing state after `activeRightPanel` is computed:

```tsx
const router = useRouter();
const pathname = usePathname();
const searchParams = useSearchParams();
const searchParamsSnapshot = searchParams.toString();
const parsedUrlPanel = useMemo(
  () => parseEditorRightPanelParam(new URLSearchParams(searchParamsSnapshot).get("panel")),
  [searchParamsSnapshot],
);
```

4. Add URL → store sync:

```tsx
useEffect(() => {
  if (parsedUrlPanel !== null && activeRightPanel !== parsedUrlPanel) {
    openRightPanel(parsedUrlPanel, "url");
  }
}, [activeRightPanel, openRightPanel, parsedUrlPanel]);
```

5. Add store → URL sync:

```tsx
useEffect(() => {
  const currentParams = new URLSearchParams(searchParamsSnapshot);
  const serializedPanel = serializeEditorRightPanelParam(activeRightPanel);
  if (currentParams.get("panel") === serializedPanel) return;
  const nextParams = setOptionalSearchParam(currentParams, "panel", serializedPanel);
  router.replace(searchParamsHref(pathname, nextParams), { scroll: false });
}, [activeRightPanel, pathname, router, searchParamsSnapshot]);
```

6. Pass the focus-return prop into the slot:

```tsx
<EditorRightPanelSlot
  activePanel={activeRightPanel}
  closePanel={closeRightPanel}
  returnFocusTo={openerRef.current}
  novelId={novelId}
  activeChapterId={activeChapterId}
  content={chapterData.content}
  chapter={chapterData.chapter}
  chapters={chapterData.chapters}
  sessionStartWordCount={chapterData.sessionStartWordCount}
  volumeStats={chapterData.volumeStats}
  wordCount={chapterData.wordCount}
  charCount={chapterData.charCount}
  paragraphCount={chapterData.paragraphCount}
  sessionMode={generationActions.sessionMode}
  handleSessionClose={generationActions.handleSessionClose}
  handleDraftAccepted={generationActions.handleDraftAccepted}
  handleStartSession={generationActions.handleStartSession}
/>
```

Expected policy: `panel=session` is normalized out because `parseEditorRightPanelParam("session")` returns `null`; toolbar toggles use `replace`, not `push`, so browser history is not spammed.

- [ ] **Step 9: Run focused URL-state tests**

Run: `pnpm --dir packages/web test components/studio/settings/settingsUrlState.test.ts components/studio/planning/planningUrlState.test.ts components/studio/kb/kbUrlState.test.ts components/studio/analysis/analysisUrlState.test.ts components/studio/editor-view/editorRightPanelUrlState.test.ts`

Expected: PASS.

- [ ] **Step 10: Create PlanningPanel URL-state component tests**

Create `packages/web/components/studio/planning/__tests__/PlanningPanel.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PlanningPanel } from "../PlanningPanel";

const mocks = vi.hoisted(() => {
  const state = { storyboardOpen: false };
  return {
    routerPush: vi.fn(),
    routerReplace: vi.fn(),
    searchParams: new URLSearchParams(),
    state,
    toggleStoryboard: vi.fn(() => {
      state.storyboardOpen = !state.storyboardOpen;
    }),
  };
});

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.routerPush, replace: mocks.routerReplace }),
  usePathname: () => "/novel/novel-1",
  useSearchParams: () => mocks.searchParams,
}));

vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: (selector: (state: { storyboardOpen: boolean; toggleStoryboard: () => void }) => unknown) =>
    selector({ storyboardOpen: mocks.state.storyboardOpen, toggleStoryboard: mocks.toggleStoryboard }),
}));

vi.mock("../StoryboardPanel", () => ({
  StoryboardPanel: () => <section data-testid="storyboard-panel" />,
}));

vi.mock("../timeline/TimelinePanel", () => ({
  TimelinePanel: () => <section data-testid="timeline-panel" />,
}));

vi.mock("../CharacterArcPanel", () => ({
  CharacterArcPanel: () => <section data-testid="character-arc-panel" />,
}));

describe("PlanningPanel URL state", () => {
  beforeEach(() => {
    mocks.routerPush.mockClear();
    mocks.routerReplace.mockClear();
    mocks.toggleStoryboard.mockClear();
    mocks.searchParams = new URLSearchParams();
    mocks.state.storyboardOpen = false;
  });

  it("opens from planning=1 and renders the requested tab", () => {
    mocks.searchParams = new URLSearchParams("planning=1&planningTab=timeline");

    render(<PlanningPanel novelId="novel-1" />);

    expect(mocks.toggleStoryboard).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("timeline-panel")).toBeInTheDocument();
  });

  it("pushes URL state when opening from the collapsed button", () => {
    render(<PlanningPanel novelId="novel-1" />);

    fireEvent.click(screen.getByRole("button", { name: /storyboard.title/i }));

    expect(mocks.routerPush).toHaveBeenCalledWith("/novel/novel-1?planning=1", { scroll: false });
  });

  it("pushes selected tab while keeping planning open", () => {
    mocks.state.storyboardOpen = true;
    mocks.searchParams = new URLSearchParams("planning=1");
    render(<PlanningPanel novelId="novel-1" />);

    fireEvent.click(screen.getByRole("button", { name: "title" }));

    expect(mocks.routerPush).toHaveBeenCalledWith("/novel/novel-1?planning=1&planningTab=timeline", {
      scroll: false,
    });
  });
});
```

- [ ] **Step 11: Run affected component tests**

Run: `pnpm --dir packages/web test components/studio/__tests__/SettingsView.test.tsx components/studio/__tests__/WorldBuilding.test.tsx components/studio/planning/__tests__/PlanningPanel.test.tsx components/studio/AnalysisPanel.test.tsx components/studio/__tests__/EditorView.test.tsx`

Expected: PASS with URL initialization, normalization, and user navigation covered.

- [ ] **Step 12: Type-check URL adapter integration**

Run: `pnpm --dir packages/web type-check`

Expected: PASS. No adapter uses `any`; invalid params are narrowed to typed defaults.

- [ ] **Step 13: Commit checkpoint after coordinator approval**

Commit message: `feat(web): add typed URL state adapters for workspace panels`

### Task 5: Responsive Baseline for Sidebar, Right Panel, KB, and Planning

**Files:**
- Modify: `packages/web/components/studio/shell/StudioWorkspaceShell.tsx`
- Modify: `packages/web/components/studio/Sidebar.tsx`
- Modify: `packages/web/components/studio/editor-view/EditorRightPanelSlot.tsx`
- Modify: `packages/web/components/studio/_components/WorldBuildingLayout.tsx`
- Modify: `packages/web/components/studio/WorldBuilding.tsx`
- Modify: `packages/web/components/studio/planning/PlanningPanel.tsx`
- Modify: `packages/web/components/studio/planning/StoryboardPanel.tsx`
- Modify: `packages/web/components/studio/planning/timeline/TimelinePanel.tsx`
- Create: `packages/web/components/studio/_components/WorldBuildingLayout.test.tsx`
- Modify: `packages/web/components/studio/planning/__tests__/PlanningPanel.test.tsx`

**Interfaces:**
- Consumes: typed panel identity and URL state from earlier tasks.
- Produces: responsive Tailwind contracts that preserve panel identity across desktop/tablet/mobile.

**Independently testable deliverable:** Workspace sidebar, editor right panel, KB layout, and planning/storyboard containers have tested responsive wrappers and scroll containment without introducing Phase B primitives, and the checkpoint commit is `feat(web): add responsive baseline for workspace panels`.

- [ ] **Step 1: Write responsive baseline tests**

Create `packages/web/components/studio/_components/WorldBuildingLayout.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorldBuildingLayout } from "./WorldBuildingLayout";

vi.mock("../kb/KBCategorySidebar", () => ({ KBCategorySidebar: () => <nav data-testid="kb-categories" /> }));
vi.mock("../kb/KBEntryList", () => ({ KBEntryList: () => <section data-testid="kb-entry-list" /> }));

describe("WorldBuildingLayout responsive baseline", () => {
  it("uses desktop columns and mobile progressive disclosure containers", () => {
    render(
      <WorldBuildingLayout
        novelId="novel-1"
        activeType={null}
        entries={[]}
        entriesLoading={false}
        selectedEntryId={null}
        onSelectEntry={vi.fn()}
        onCreateNew={vi.fn()}
        onCreateAssisted={vi.fn()}
        onTypeChange={vi.fn()}
        onAnalyze={vi.fn()}
        onConsistencyCheck={vi.fn()}
        onShowGraph={vi.fn()}
        onShowWiki={vi.fn()}
        showGraph={false}
        showWiki={false}
      >
        <section data-testid="kb-detail" />
      </WorldBuildingLayout>,
    );
    const layout = screen.getByTestId("kb-responsive-layout");
    expect(layout.className).toContain("flex-col");
    expect(layout.className).toContain("lg:flex-row");
    expect(screen.getByTestId("kb-categories")).toBeInTheDocument();
    expect(screen.getByTestId("kb-entry-list")).toBeInTheDocument();
    expect(screen.getByTestId("kb-detail")).toBeInTheDocument();
  });
});
```

Add to `packages/web/components/studio/editor-view/EditorRightPanelSlot.test.tsx`:

```tsx
it("keeps a mobile drawer representation for the active panel", () => {
  render(<EditorRightPanelSlot {...baseProps} activePanel="metadata" />);
  expect(screen.getByTestId("editor-right-panel-mobile").className).toContain("lg:hidden");
  expect(screen.getByTestId("editor-right-panel-desktop").className).toContain("lg:flex");
});
```

Add to `packages/web/components/studio/planning/__tests__/PlanningPanel.test.tsx`:

```tsx
it("uses responsive tab scroller and bounded content region when expanded", () => {
  mocks.state.storyboardOpen = true;
  mocks.searchParams = new URLSearchParams("planning=1");

  render(<PlanningPanel novelId="novel-1" />);

  const panel = screen.getByRole("region", { name: "storyboard.title" });
  expect(panel.className).toContain("w-full");
  expect(panel.className).toContain("border-b");

  const tabScroller = screen.getByTestId("planning-tab-scroller");
  expect(tabScroller.className).toContain("overflow-x-auto");

  const content = screen.getByTestId("planning-tab-content");
  expect(content.className).toContain("max-h-[45vh]");
  expect(content.className).toContain("lg:max-h-[36vh]");
});
```

- [ ] **Step 2: Run responsive tests and verify failure**

Run: `pnpm --dir packages/web test components/studio/_components/WorldBuildingLayout.test.tsx components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/planning/__tests__/PlanningPanel.test.tsx`

Expected: FAIL with Testing Library errors for missing `editor-right-panel-mobile`, `kb-responsive-layout`, `planning-tab-scroller`, or `planning-tab-content`, because Task 5 implementation has not added those responsive wrappers yet.

- [ ] **Step 3: Update editor right panel responsive shell**

Modify `EditorRightPanelSlot.tsx` so desktop and mobile wrappers each get a unique heading id while using the same `returnFocusTo` Escape behavior. Replace the single `panelTitleId` constant and single `<aside>` return with:

```tsx
const renderPanelFrameContent = (titleId: string) => (
  <>
    <h2 id={titleId} className="sr-only">
      {t("shell.editorRightPanel")}
    </h2>
    {panelContent}
  </>
);

return (
  <>
    <aside
      data-testid="editor-right-panel-desktop"
      role="region"
      aria-labelledby="editor-right-panel-title-desktop"
      className="hidden h-full w-96 shrink-0 border-l border-border bg-card lg:flex lg:flex-col"
    >
      {renderPanelFrameContent("editor-right-panel-title-desktop")}
    </aside>
    <div
      data-testid="editor-right-panel-mobile"
      role="dialog"
      aria-modal="true"
      aria-labelledby="editor-right-panel-title-mobile"
      className="fixed inset-x-0 bottom-0 z-30 max-h-[85vh] overflow-y-auto rounded-t-xl border border-border bg-card shadow-2xl lg:hidden"
    >
      {renderPanelFrameContent("editor-right-panel-title-mobile")}
    </div>
  </>
);
```

This is Phase C baseline only. Do not build the Phase B `PanelShell` primitive in this task.

- [ ] **Step 4: Update KB 3-column responsive layout**

Modify `WorldBuildingLayout.tsx` root to:

```tsx
<div data-testid="kb-responsive-layout" className="flex-1 flex min-h-0 flex-col lg:flex-row">
  <div className="shrink-0 border-b border-border lg:w-56 lg:border-b-0 lg:border-r">
    <KBCategorySidebar
      novelId={novelId}
      activeType={activeType}
      onTypeChange={onTypeChange}
      onAnalyze={onAnalyze}
      onConsistencyCheck={onConsistencyCheck}
      onShowGraph={onShowGraph}
      onShowWiki={onShowWiki}
      showGraph={showGraph}
      showWiki={showWiki}
    />
  </div>
  {!showGraph && (
    <div className="shrink-0 border-b border-border lg:w-64 lg:border-b-0 lg:border-r">
      <KBEntryList
        novelId={novelId}
        entries={entries}
        isLoading={entriesLoading}
        selectedEntryId={selectedEntryId}
        activeType={activeType}
        onSelectEntry={onSelectEntry}
        onCreateNew={onCreateNew}
        onCreateAssisted={onCreateAssisted}
      />
    </div>
  )}
  <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
</div>
```

Keep `showGraph` behavior: graph mode may omit the entry list on desktop and mobile, but it must still preserve the active URL mode.

- [ ] **Step 5: Update planning and storyboard responsive containers**

Modify `PlanningPanel.tsx` expanded state markup with these exact wrapper replacements:

1. Replace the expanded root opening tag:

```tsx
<div className="w-full border-b border-border bg-card">
```

with:

```tsx
<section className="w-full border-b border-border bg-card" aria-label={t("storyboard.title")}>
```

2. Replace the tab header wrapper:

```tsx
<div className="flex items-center gap-3 px-6 py-2 border-b border-border">
```

with:

```tsx
<div
  data-testid="planning-tab-scroller"
  className="flex items-center gap-2 overflow-x-auto border-b border-border px-3 py-2 sm:px-6"
>
```

3. Immediately after the tab-header closing `</div>` and before the storyboard conditional render block `{activeTab === "storyboard" && <StoryboardPanel novelId={novelId} hideHeader />}`, insert:

```tsx
<div data-testid="planning-tab-content" className="max-h-[45vh] overflow-auto lg:max-h-[36vh]">
```

4. Immediately after `{activeTab === "characterArc" && <CharacterArcPanel novelId={novelId} />}`, insert the matching `</div>`.

5. Replace the expanded root closing `</div>` with `</section>`.

Modify `StoryboardPanel.tsx` at the existing stage-columns wrapper so the element with `ref={scrollRef}` keeps `overflow-x-auto` and also includes `min-w-0` on its class list: `className="flex min-w-0 gap-3 overflow-x-auto scrollbar-none"`. Modify `TimelinePanel.tsx` tab header from `className="flex items-center gap-2 px-4 py-2 border-b border-border bg-card"` to `className="flex items-center gap-2 overflow-x-auto px-4 py-2 border-b border-border bg-card"`, and modify its tab-button group from `className="flex rounded-md border border-border overflow-hidden"` to `className="flex shrink-0 rounded-md border border-border overflow-hidden"`. Do not add `overflow-y-auto` to `body`, route layouts, or page roots.

- [ ] **Step 6: Run responsive focused tests**

Run: `pnpm --dir packages/web test components/studio/_components/WorldBuildingLayout.test.tsx components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/planning/__tests__/PlanningPanel.test.tsx`

Expected: PASS.

- [ ] **Step 7: Type-check responsive changes**

Run: `pnpm --dir packages/web type-check`

Expected: PASS.

- [ ] **Step 8: Commit checkpoint after coordinator approval**

Commit message: `feat(web): add responsive baseline for workspace panels`

### Task 6: Phase-C Accessibility Behavior for Shell and Panels

**Files:**
- Modify: `packages/web/components/studio/shell/StudioWorkspaceShell.tsx`
- Modify: `packages/web/components/studio/editor-view/EditorRightPanelSlot.tsx`
- Modify: `packages/web/components/studio/SettingsView.tsx`
- Modify: `packages/web/components/studio/WorldBuilding.tsx`
- Modify: `packages/web/components/studio/AnalysisPanel.tsx`
- Modify: `packages/web/components/studio/planning/PlanningPanel.tsx`
- Modify: `packages/web/components/studio/shell/StudioWorkspaceShell.test.tsx`
- Modify: `packages/web/components/studio/editor-view/EditorRightPanelSlot.test.tsx`
- Modify: `packages/web/components/studio/__tests__/SettingsView.test.tsx`
- Modify: `packages/web/components/studio/__tests__/WorldBuilding.test.tsx`
- Modify: `packages/web/components/studio/AnalysisPanel.test.tsx`

**Interfaces:**
- Produces:
  - `returnFocusTo?: HTMLElement | null` on `EditorRightPanelSlotProps`; `closePanel` remains exactly `(panel?: EditorRightPanelId) => void` everywhere.
  - Data attributes or refs only for tests; no user-visible test-only text.
- Consumes:
  - Existing panel close callbacks and i18n labels.

**Independently testable deliverable:** Shell and panel-owned landmarks, Escape close, focus return, and shell status announcements are covered by focused component tests, and the checkpoint commit is `feat(web): add shell panel accessibility baseline`.

- [ ] **Step 1: Extend accessibility tests for focus return and Escape**

Add to `EditorRightPanelSlot.test.tsx`:

```tsx
it("returns focus to the opener when the panel closes", () => {
  const opener = document.createElement("button");
  opener.textContent = "open";
  document.body.appendChild(opener);
  opener.focus();
  const closePanel = vi.fn(() => opener.focus());
  render(<EditorRightPanelSlot {...baseProps} activePanel="metadata" closePanel={closePanel} returnFocusTo={opener} />);
  fireEvent.keyDown(window, { key: "Escape" });
  expect(closePanel).toHaveBeenCalledWith("metadata");
  expect(document.activeElement).toBe(opener);
  opener.remove();
});
```

Add to `StudioWorkspaceShell.test.tsx`:

```tsx
it("uses main and navigation landmarks for workspace chrome", () => {
  render(<StudioWorkspaceShell><div>workspace</div></StudioWorkspaceShell>);
  expect(screen.getByRole("main", { name: "shell.workspaceMain" })).toBeInTheDocument();
  expect(screen.getByRole("navigation")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run accessibility-focused tests and verify failure**

Run: `pnpm --dir packages/web test components/studio/shell/StudioWorkspaceShell.test.tsx components/studio/editor-view/EditorRightPanelSlot.test.tsx`

Expected: FAIL because `EditorRightPanelSlotProps` does not yet accept `returnFocusTo` and the shell/panel landmarks from Step 3 are not yet wired.

- [ ] **Step 3: Add landmarks to shell and route panels**

Apply this landmark checklist:

- `StudioWorkspaceShell.tsx`: the workspace content wrapper is exactly `<main className="flex-1 min-h-0 min-w-0" aria-label={t("shell.workspaceMain")}>{children}</main>`.
- `Sidebar.tsx`: the existing navigation wrapper is exactly `<nav aria-label={t("sidebar.navigation")} className="p-3 border-b border-border space-y-0.5">` and still contains the current `navItems.map()` body.
- `SettingsView.tsx`: wrap the current settings view content in a `<section aria-labelledby="settings-view-title">`; if there is no visible title element with `id="settings-view-title"`, add `<h1 id="settings-view-title" className="sr-only">{t("settings.title")}</h1>` as the first child.
- `WorldBuilding.tsx`: wrap the current KB view content in a `<section aria-labelledby="kb-view-title">`; if there is no visible title element with `id="kb-view-title"`, add `<h1 id="kb-view-title" className="sr-only">{t("worldbuilding.title")}</h1>` as the first child.
- `AnalysisPanel.tsx`: wrap the current analysis view content in a `<section aria-labelledby="analysis-view-title">`; if there is no visible title element with `id="analysis-view-title"`, add `<h1 id="analysis-view-title" className="sr-only">{t("analysis.title")}</h1>` as the first child.

Use existing visible headings as labels when present; otherwise add the specified `sr-only` heading using an existing or newly localized key. Do not introduce hardcoded English labels.

- [ ] **Step 4: Add Escape and focus return in editor right panel slot**

Modify `EditorRightPanelSlot.tsx` props:

```ts
interface EditorRightPanelSlotProps {
  activePanel: EditorRightPanelId | null;
  closePanel: (panel?: EditorRightPanelId) => void;
  returnFocusTo?: HTMLElement | null;
  novelId: string;
  activeChapterId: string;
  content: string;
  chapter: Chapter | undefined;
  chapters: ChapterSummary[];
  sessionStartWordCount: number;
  volumeStats: VolumeStats | undefined;
  wordCount: number;
  charCount: number;
  paragraphCount: number;
  sessionMode: "interactive_session" | "interview_assisted";
  handleSessionClose: () => void;
  handleDraftAccepted: (text: string) => void;
  handleStartSession: (mode: string) => void;
}
```

When Escape closes a panel, call `closePanel(activePanel)` and then focus `returnFocusTo` if it is still connected:

```ts
if (returnFocusTo?.isConnected) returnFocusTo.focus();
```

Use only the `returnFocusTo` prop for focus return. URL-opened panels naturally have `openerRef.current === null`, so initial load does not steal focus; toolbar-opened panels pass the triggering element through `returnFocusTo={openerRef.current}` once Task 4 wires the ref.

- [ ] **Step 5: Add status/live regions directly tied to panel shell**

For panel containers that expose loading/streaming via existing child panels, add a shell-level region only when the shell itself changes state. Example for mobile drawer opening:

```tsx
<div role="status" aria-live="polite" className="sr-only">
  {activePanel ? t("shell.panelOpened") : t("shell.panelClosed")}
</div>
```

Use the `shell.panelOpened` and `shell.panelClosed` keys added to `packages/i18n/messages/{de,en,fr}/studio.json` in Task 1 Step 5. Do not add a second key name and do not move AI lifecycle announcements from existing AI panels in this phase.

- [ ] **Step 6: Run focused accessibility tests**

Run: `pnpm --dir packages/web test components/studio/shell/StudioWorkspaceShell.test.tsx components/studio/editor-view/EditorRightPanelSlot.test.tsx components/studio/__tests__/SettingsView.test.tsx components/studio/__tests__/WorldBuilding.test.tsx components/studio/AnalysisPanel.test.tsx`

Expected: PASS with accessible names, Escape close, and focus return covered where shell/panel-owned.

- [ ] **Step 7: Run lint check for i18n and TypeScript surface**

Run: `pnpm --dir packages/web lint:check`

Expected: PASS with no hardcoded user-facing strings introduced by Phase C shell/panel code.

Run: `pnpm --dir packages/web type-check`

Expected: PASS.

- [ ] **Step 8: Commit checkpoint after coordinator approval**

Commit message: `feat(web): add shell panel accessibility baseline`

### Task 7: Phase-C Integration Gate and Cleanup

**Files:**
- Verification only: no file creation, modification, or deletion is planned in Task 7.
- If any Task 7 command fails, stop and return to the earlier task that owns the failing file; enumerate the exact corrective edit there before changing code.
- Forbidden in this task: Phase A docs, Phase B shared primitives, backend/core files, package manifests, and `middleware.ts`.

**Interfaces:**
- Consumes all Phase C deliverables.
- Produces final implementation evidence for coordinator review.

**Independently testable deliverable:** The full affected Phase C test set, type-check, lint check, file-size inspection, and scope-boundary inspection all pass. Task 7 is verification-only: do not modify files and do not create a checkpoint commit inside this task.

- [ ] **Step 1: Run full affected frontend test set**

Run:

```bash
pnpm --dir packages/web test \
  components/studio/__tests__/ShellOwnership.test.tsx \
  components/studio/shell/StudioWorkspaceShell.test.tsx \
  lib/stores/editorRightPanelState.test.ts \
  components/studio/editor-view/EditorRightPanelSlot.test.tsx \
  components/studio/editor-view/editorRightPanelUrlState.test.ts \
  components/studio/settings/settingsUrlState.test.ts \
  components/studio/planning/planningUrlState.test.ts \
  components/studio/kb/kbUrlState.test.ts \
  components/studio/analysis/analysisUrlState.test.ts \
  components/studio/__tests__/EditorView.test.tsx \
  components/studio/__tests__/SettingsView.test.tsx \
  components/studio/__tests__/WorldBuilding.test.tsx \
  components/studio/planning/__tests__/PlanningPanel.test.tsx \
  components/studio/AnalysisPanel.test.tsx
```

Expected: PASS. The output should show all listed files executed with zero failed tests.

- [ ] **Step 2: Run type-check**

Run: `pnpm --dir packages/web type-check`

Expected: PASS.

- [ ] **Step 3: Run lint check**

Run: `pnpm --dir packages/web lint:check`

Expected: PASS.

- [ ] **Step 4: Inspect file-size and responsibility boundaries**

Run: `python scripts/check_file_sizes.py packages/web/components/studio/EditorView.tsx packages/web/components/studio/editor-view/EditorRightPanelSlot.tsx packages/web/components/studio/shell/StudioWorkspaceShell.tsx`

Expected: exit code 0 and stdout contains no `ERROR`, `FAIL`, or file-size violation rows; each listed feature component is at or below the documented 200-line hard limit.

Run: `git diff -U0 -- packages/web/lib/url-state packages/web/components/studio | rg '^\+.*from "@/components/studio/(SettingsView|WorldBuilding|AnalysisPanel|planning|editor-view)' || true`

Expected: empty stdout; the Phase C diff adds no URL-adapter imports from React feature components.

Inspect `packages/web/components/studio/shell/StudioWorkspaceShell.tsx` and verify these exact ownership conditions:

- It imports `Sidebar`, `FeatureTour`, `Toaster`, `FEATURE_TOUR_STEPS`, `Menu`, `useTranslations`, `useEffect`, and `useState`.
- It does not import `EditorView`, `SettingsView`, `WorldBuilding`, `AnalysisPanel`, `PlanningPanel`, `EditorRightPanelSlot`, or any analysis/editor panel component.
- It renders exactly one `<main>` landmark for `{children}` and owns no feature-specific panel content.

- [ ] **Step 5: Verify Phase-C scope boundaries**

Run: `git diff --name-only -- packages/web apps packages core docs package.json pnpm-lock.yaml middleware.ts packages/web/middleware.ts`

Expected: stdout contains only changed paths listed in the `Create`, `Modify`, or `Delete` sections of Tasks 1–6, plus `docs/superpowers/plans/2026-07-01-ui-ux-phase-c-shell-panels.md` when the plan itself is under review. Stdout must contain no line starting with `apps/`, `packages/core/`, `package.json`, `pnpm-lock.yaml`, `middleware.ts`, or `packages/web/middleware.ts`.

Run: `git diff -U0 -- packages/web/components | rg '^\+.*(export function|function) (IconButton|PanelHeader|PanelShell|PanelTabs|ToolbarButton|SearchInput|StatusMessage)\b' || true`

Expected: empty stdout. This diff-based check ignores pre-existing matches and fails the review if Phase C adds new shared primitive function definitions.

Run: `test ! -f middleware.ts && test ! -f packages/web/middleware.ts`

Expected: exit code 0; no `middleware.ts` exists at the repository root or under `packages/web/`.

Run: `git diff -- package.json pnpm-lock.yaml packages/web/package.json`

Expected: empty output; no package install and no new dependency.

- [ ] **Step 6: Prepare verification handoff without file modifications**

Record the exact passing command outputs from Steps 1–5 in the coordinator handoff message. Do not edit files, stage files, commit, or run formatters in Task 7. If any command fails, stop and return to the earlier task that owns the failing file; the corrective edit must be added to that earlier task before implementation continues.

## Phase B Dependencies Explicitly Not Implemented Here

Phase C may add local shell/panel accessibility behavior where directly tied to ownership, but the following are next-phase dependencies and must not be implemented as new shared primitives in this plan:

- `IconButton` enforcing localized label, `type="button"`, focus styles, disabled/loading state.
- `PanelHeader` for title, description/status slot, close/action slot, and `aria-labelledby` integration.
- `PanelShell` for reusable desktop side-panel and mobile drawer/sheet behavior.
- `PanelTabs` for URL-addressable tab lists.
- `ToolbarButton` for editor toolbar icon+label/tooltip behavior.
- `SearchInput` with label, clear button, and URL sync hook integration.
- `StatusMessage` for non-blocking loading/error/empty/success/live-region patterns.

## Self-Review Checklist for the Implementation Worker

### Spec Coverage

- Shell route ownership: Task 1 gives dashboard no sidebar, wizard/setup no sidebar, and novel workspace sidebar ownership under `/novel/[id]/**`.
- Editor right-panel registry/arbitration: Tasks 2–3 replace boolean state with `EditorRightPanelState` and render a single occupant.
- URL-state policy: Task 4 covers Settings category, Planning open/tab, KB type/mode/search/entry, Analysis panel, and safe editor right panel.
- Responsive baseline: Task 5 covers studio sidebar, editor right panel, KB 3-column transformation, and planning/storyboard scroll containment.
- Accessibility behavior: Task 6 covers Escape close, focus return, landmarks, and shell/panel status where Phase C owns the behavior.
- Phase boundaries: Task 7 verifies no Phase B primitives, no Phase A docs, and no Phase D polish are implemented in this phase.

### Placeholder Scan

- Search the implementation and this plan for unresolved placeholder markers, staged-work comments, copy-forward shortcuts, and vague test instructions; none should remain.
- Assert explicitly before handoff: no placeholder code blocks remain in this plan or in the implementation diff.
- Assert explicitly before handoff: no placeholder JSX comments remain in code blocks, including scaffold comments for existing tab buttons, tab content, pending work, or equivalent markers.
- Assert explicitly before handoff: no vague implementation steps remain; every code-changing step names exact files and either provides complete code or precise replacement instructions around named existing elements.
- Assert explicitly before handoff: every file referenced by a command has an earlier creation/modification step in this plan, or the command is a verification-only command against an existing file.
- Search new code for hardcoded user-facing English strings in JSX and ARIA labels. Any new visible label must be an i18n key in all three locale files.
- Search for `any`, non-null assertions, and `middleware.ts`; none are allowed.

### Type Consistency

- `EditorRightPanelId` values match across `editorRightPanelState.ts`, `editorRightPanelUrlState.ts`, `EditorRightPanelSlot.tsx`, and toolbar callers.
- Assert explicitly before handoff: type names and helper names are consistent; `setOptionalSearchParam` is the canonical search-param helper and `returnFocusTo` is a prop on `EditorRightPanelSlotProps` while `closePanel` remains `(panel?: EditorRightPanelId) => void`.
- `KBMode` values match across `kbUrlState.ts`, `worldBuildingState.ts`, `WorldBuilding.tsx`, and tests.
- `PlanningTab` values match `PlanningPanel.tsx` and `planningUrlState.ts`.
- `SettingsCategory` is imported from `settings-view-config.ts`; no duplicate union is created.
- `AnalysisType` is imported from `analysis-data.ts`; no duplicate union is created.
