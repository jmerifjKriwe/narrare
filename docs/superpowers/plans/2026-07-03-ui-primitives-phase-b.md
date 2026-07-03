# UI Primitives Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the seven shared UI primitives (`IconButton`, `StatusMessage`, `PanelHeader`, `ToolbarButton`, `SearchInput`, `PanelTabs`, `PanelShell`) under `packages/web/components/ui/` plus two helper hooks, and migrate at least one real adopter per primitive — replacing ad-hoc inline markup with typed, accessible, tested components.

**Architecture:** Minimal in-repo primitive set derived from the Phase C shell/panel contract (spec Alternative C). Each primitive is a presentational leaf component (no feature imports, no internal `next-intl` coupling — callers pass resolved i18n strings). URL-addressable state for `PanelTabs`/`SearchInput` is owned by one shared `use-url-param` hook (one adapter instance per surface). Responsive drawer focus/escape/trap logic for `PanelShell` lives in a `use-panel-focus` hook. No new runtime dependency — native elements + Tailwind + existing `lucide-react` only.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript (strict, no `any`), Tailwind v4 with semantic design tokens (`@/styles/tokens.css`), `lucide-react` v1 icons, Vitest + @testing-library/react + @testing-library/user-event + happy-dom.

## Global Constraints

Copied verbatim / derived from spec §3, §5, §9:

- **No new runtime dependency.** Reuse Tailwind + existing `lucide-react`. No headless-ui / radix-ui / @base-ui additions for these primitives (radix-alert-dialog already exists for `ConfirmDialog` only). No `middleware.ts`.
- **All primitives live under `packages/web/components/ui/`** (the existing home of `confirm-dialog`, `connection-lost-banner`, `toaster`, `feature-tour`).
- **Tailwind utility classes + semantic tokens only** (`bg-card`, `bg-muted`, `text-muted-foreground`, `bg-accent`, `border-border`, `bg-primary`, `text-primary-foreground`, `bg-destructive`, `text-destructive-foreground`, `ring-ring`). No inline `style={{}}` (RULE-04 / ui-principles §4).
- **RULE-16 i18n:** all visible text / aria labels are i18n-backed. Primitives receive **resolved strings** as required props (`label`, `title`, `message`); the caller performs the `t()` call. No hardcoded user-facing strings inside primitives.
- **RULE-04 file limits:** each primitive file ≤ 200 lines; each hook file ≤ 150 lines. Extract hooks before pruning comments.
- **Accessibility (spec §10, ui-principles §11):** `type="button"` enforced on every primitive button; `aria-label`/`label` **required** (never inferred); `focus-visible` rings (NOT `focus:`); decorative icons carry `aria-hidden`; `aria-pressed` on toggle; correct `role`/`aria-live` per status state.
- **RULE-13:** `PanelShell` / `PanelHeader` are presentation only — they do not own SSE/AI streaming; panels keep their streaming/cancel via existing hooks.
- **TypeScript strict, no `any`** (RULE-09, RULE-23). No type suppressions introduced.
- **React 19:** no `forwardRef` (refs as plain props where needed); these primitives are leaf/presentational and need no refs.

## Task Ordering

The seven tasks follow the order requested (IconButton → StatusMessage → PanelHeader → ToolbarButton → SearchInput → PanelTabs → PanelShell). This differs from spec §7's blast-radius order (which places `PanelShell` 4th and `SearchInput` last), but every cross-task dependency is still satisfied:

- `PanelHeader` (Task 3) depends on `IconButton` (Task 1) for its close button ✓
- `SearchInput` (Task 5) creates the shared `use-url-param` hook, which `PanelTabs` (Task 6) consumes ✓
- `PanelShell` (Task 7) depends on `PanelHeader` (Task 3) via the shared `titleId` ✓

`PanelShell` last is acceptable because it is the most complex (responsive drawer + focus trap) and benefits from the simpler primitives being already proven.

## File Structure

**Create (primitive components):**
- `packages/web/components/ui/icon-button.tsx` — atomic icon action button (≤ 200 lines)
- `packages/web/components/ui/status-message.tsx` — non-blocking loading/error/empty live region (≤ 200 lines)
- `packages/web/components/ui/panel-header.tsx` — accessible panel header (≤ 200 lines)
- `packages/web/components/ui/toolbar-button.tsx` — labelled toolbar action (≤ 200 lines)
- `packages/web/components/ui/search-input.tsx` — labelled search with clear + URL sync (≤ 200 lines)
- `packages/web/components/ui/panel-tabs.tsx` — URL-addressable tab list (≤ 200 lines)
- `packages/web/components/ui/panel-shell.tsx` — responsive side-panel container / drawer (≤ 200 lines)

**Create (hooks):**
- `packages/web/lib/hooks/use-url-param.ts` — one-adapter-per-surface URL search-param sync (≤ 150 lines)
- `packages/web/lib/hooks/use-panel-focus.ts` — drawer focus move / trap / return + Escape (≤ 150 lines)

**Create (tests):** one `*.test.tsx`/`*.test.ts` per file above, co-located in `__tests__/` siblings or next to the file per codebase convention (component tests live alongside).

**Modify (migration adopters — at least one per task):**
- `packages/web/components/studio/shell/StudioWorkspaceShell.tsx` (IconButton)
- `packages/web/components/studio/extraction/ExtractionLoading.tsx`, `ExtractionError.tsx`, `ExtractionDone.tsx` (StatusMessage)
- `packages/web/components/studio/analysis/ConsistencyPanelHeader.tsx` (IconButton + PanelHeader)
- `packages/web/components/studio/editor-view/EditorToolbar.tsx` (ToolbarButton)
- KB search surface (SearchInput) — identified per Task 5
- `packages/web/components/studio/settings/SettingsView.tsx` + `settingsUrlState.ts` (PanelTabs + use-url-param)
- One editor right-panel slot (PanelShell) — identified per Task 7

**Conventions established by the codebase (must follow):**
- Test command (single file): `pnpm --filter narrare-web exec vitest run <path>` (workspace root) — `vitest.config.ts` globs `**/*.test.{ts,tsx}`, env `happy-dom`, alias `@ → packages/web`.
- `next-intl` is globally mocked in `setupTests.ts` so `t("close")` returns the string `"close"`; tests assert on the key string. Primitives here take resolved strings, so no per-test `next-intl` mock is needed.
- `next/navigation` (`useRouter`/`useSearchParams`) is globally mocked in `setupTests.ts`; per-test overrides use `vi.mocked(...)`.
- `cn()` helper at `@/lib/utils` for class merging.
- Conventional Commits (`feat:`, `refactor:`) — repo uses release-please.

---

### Task 1: IconButton

**Files:**
- Create: `packages/web/components/ui/icon-button.tsx`
- Create: `packages/web/components/ui/__tests__/icon-button.test.tsx`
- Modify: `packages/web/components/studio/shell/StudioWorkspaceShell.tsx:35-42` (menu button)
- Modify: `packages/web/components/studio/analysis/ConsistencyPanelHeader.tsx:33-40, 71-78` (back + close buttons)

**Interfaces:**
- Consumes: `cn` from `@/lib/utils`; `LucideIcon` type + `Loader2` from `lucide-react`.
- Produces: `IconButton` — `export function IconButton(props: IconButtonProps)`. Imported by PanelHeader (Task 3), SearchInput (Task 5), and migration adopters.

**Prop interface (spec §5.1):**

```ts
import type { LucideIcon } from "lucide-react";

type IconButtonVariant = "ghost" | "destructive" | "default";
type IconButtonSize = "sm" | "md";

interface IconButtonProps {
  /** Required accessible name (resolved i18n string). Becomes aria-label. */
  readonly label: string;
  /** Lucide icon component to render. */
  readonly icon: LucideIcon;
  /** Click handler. */
  readonly onClick?: () => void;
  /** Disables the button and reflects aria-disabled. */
  readonly disabled?: boolean;
  /** Shows a spinner, hides the icon, sets aria-busy. */
  readonly loading?: boolean;
  /** Visual variant. Defaults to "ghost". */
  readonly variant?: IconButtonVariant;
  /** Touch target size. Defaults to "md". */
  readonly size?: IconButtonSize;
}
```

- [ ] **Step 1: Write the failing test**

Create `packages/web/components/ui/__tests__/icon-button.test.tsx`:

```tsx
import { Menu } from "lucide-react";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { IconButton } from "@/components/ui/icon-button";

describe("IconButton", () => {
  it("renders a button with type=button and the accessible name", () => {
    render(<IconButton label="Open menu" icon={Menu} onClick={() => {}} />);
    const btn = screen.getByRole("button", { name: "Open menu" });
    expect(btn).toHaveAttribute("type", "button");
  });

  it("forwards onClick", async () => {
    const onClick = vi.fn();
    render(<IconButton label="Close" icon={Menu} onClick={onClick} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and exposes aria-disabled when disabled", () => {
    render(<IconButton label="Refresh" icon={Menu} onClick={() => {}} disabled />);
    const btn = screen.getByRole("button", { name: "Refresh" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-disabled", "true");
  });

  it("hides the icon behind an aria-hidden spinner and sets aria-busy while loading", () => {
    const { container } = render(
      <IconButton label="Save" icon={Menu} onClick={() => {}} loading />,
    );
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("applies the destructive variant class", () => {
    render(<IconButton label="Delete" icon={Menu} onClick={() => {}} variant="destructive" />);
    const btn = screen.getByRole("button", { name: "Delete" });
    expect(btn.className).toContain("destructive");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/icon-button.test.tsx`
Expected: FAIL — `Failed to resolve import "@/components/ui/icon-button"` (module does not exist).

- [ ] **Step 3: Write the minimal implementation**

Create `packages/web/components/ui/icon-button.tsx`:

```tsx
import { Loader2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type IconButtonVariant = "ghost" | "destructive" | "default";
type IconButtonSize = "sm" | "md";

interface IconButtonProps {
  /** Required accessible name (resolved i18n string). Becomes aria-label. */
  readonly label: string;
  /** Lucide icon component to render. */
  readonly icon: LucideIcon;
  readonly onClick?: () => void;
  readonly disabled?: boolean;
  /** Shows a spinner, hides the icon, sets aria-busy. */
  readonly loading?: boolean;
  readonly variant?: IconButtonVariant;
  readonly size?: IconButtonSize;
}

const VARIANT_CLASSES: Record<IconButtonVariant, string> = {
  ghost:
    "text-muted-foreground hover:bg-muted hover:text-foreground rounded-md",
  default:
    "bg-primary text-primary-foreground rounded-md hover:opacity-90",
  destructive:
    "text-destructive hover:bg-destructive/10 rounded-md border border-destructive",
};

const SIZE_CLASSES: Record<IconButtonSize, string> = {
  sm: "p-1",
  md: "p-1.5",
};

/**
 * Atomic icon-only action button. The accessible name is the required `label`
 * prop (a resolved i18n string) — never inferred. Always renders type="button".
 * Replaces the hand-rolled `<button type="button" aria-label=... className="p-1.5 ...">`
 * pattern (spec §1). a11y per ui-principles §11.
 */
export function IconButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  loading = false,
  variant = "ghost",
  size = "md",
}: IconButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      type="button"
      aria-label={label}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      disabled={isDisabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center transition-colors",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
      )}
    >
      {loading ? (
        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
      ) : (
        <Icon aria-hidden="true" className="h-4 w-4" />
      )}
    </button>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/icon-button.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Type-check and lint**

Run: `pnpm --filter narrare-web run type-check`
Run: `pnpm --filter narrare-web run lint:check`
Expected: no errors.

- [ ] **Step 6: Migrate at least one adopter**

In `packages/web/components/studio/shell/StudioWorkspaceShell.tsx`, replace the inline menu button (lines 35-42) with `<IconButton label={t("sidebar.openMenu")} icon={Menu} onClick={() => setSidebarOpen(true)} />` and add `import { IconButton } from "@/components/ui/icon-button";`. Then, in `packages/web/components/studio/analysis/ConsistencyPanelHeader.tsx`, replace the back button (33-40) and close button (71-78) with `<IconButton label={t("close")} icon={ArrowLeft} onClick={onClose} />` and `<IconButton label={t("close")} icon={X} onClick={onClose} />`.

Run the existing adopter tests to confirm no regression:
`pnpm --filter narrare-web exec vitest run packages/web/components/studio/shell/StudioWorkspaceShell.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/web/components/ui/icon-button.tsx \
        packages/web/components/ui/__tests__/icon-button.test.tsx \
        packages/web/components/studio/shell/StudioWorkspaceShell.tsx \
        packages/web/components/studio/analysis/ConsistencyPanelHeader.tsx
git commit -m "feat(web): add IconButton primitive and migrate shell/consistency buttons"
```

---

### Task 2: StatusMessage

**Files:**
- Create: `packages/web/components/ui/status-message.tsx`
- Create: `packages/web/components/ui/__tests__/status-message.test.tsx`
- Modify: `packages/web/components/studio/extraction/ExtractionLoading.tsx`
- Modify: `packages/web/components/studio/extraction/ExtractionError.tsx`
- Modify: `packages/web/components/studio/extraction/ExtractionDone.tsx`
- Re-express: `packages/web/components/ui/connection-lost-banner.tsx`

**Interfaces:**
- Consumes: none (leaf). Optional `action` is a `ReactNode` (typically an `IconButton` or button).
- Produces: `StatusMessage` — `export function StatusMessage(props: StatusMessageProps)`.

**Prop interface (spec §5.7):**

```ts
type StatusState = "idle" | "loading" | "success" | "error" | "empty";
type Politeness = "polite" | "assertive";

interface StatusMessageProps {
  readonly state: StatusState;
  /** Resolved i18n message string. */
  readonly message?: string;
  /** Optional actionable element (retry/reconnect button). */
  readonly action?: React.ReactNode;
  /** aria-live politeness. Defaults to "polite"; errors default to "assertive". */
  readonly politeness?: Politeness;
}
```

**Behaviour (spec §9.5, ui-principles §16.5):**
- `role="status"` with `aria-live` for `loading`/`success`/`empty`/`idle`.
- `error` uses `role="alert"` (`aria-live="assertive"` forced). Errors must be actionable — `message` follows `[what happened] [what to do]`; `action` is the recovery control.
- `loading` sets `aria-busy="true"` and renders an `aria-hidden` spinner.
- `idle` renders nothing visible (keeps the live region mounted but empty) so a future transition announces.

- [ ] **Step 1: Write the failing test**

Create `packages/web/components/ui/__tests__/status-message.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusMessage } from "@/components/ui/status-message";

describe("StatusMessage", () => {
  it("announces loading with a polite live region and aria-busy", () => {
    render(<StatusMessage state="loading" message="Thinking" />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveTextContent("Thinking");
  });

  it("uses role=alert and assertive live region for errors", () => {
    render(
      <StatusMessage
        state="error"
        message="Connection lost. Tap retry to reconnect."
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("aria-live", "assertive");
    expect(alert).toHaveTextContent("Connection lost");
  });

  it("renders an actionable retry control via action prop", () => {
    render(
      <StatusMessage state="error" message="Failed" action={<button type="button">Retry</button>} />,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeDefined();
  });

  it("renders nothing visible in idle but keeps the region mounted", () => {
    const { container } = render(<StatusMessage state="idle" />);
    expect(container.textContent).toBe("");
  });

  it("honours an explicit assertive politeness override", () => {
    render(<StatusMessage state="loading" message="x" politeness="assertive" />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "assertive");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/status-message.test.tsx`
Expected: FAIL — cannot resolve `@/components/ui/status-message`.

- [ ] **Step 3: Write the minimal implementation**

Create `packages/web/components/ui/status-message.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type StatusState = "idle" | "loading" | "success" | "error" | "empty";
type Politeness = "polite" | "assertive";

interface StatusMessageProps {
  readonly state: StatusState;
  readonly message?: string;
  readonly action?: ReactNode;
  readonly politeness?: Politeness;
}

/**
 * Non-blocking loading/error/empty/success live region (spec §5.7).
 * Presentation only — callers pass resolved i18n strings and own streaming
 * (RULE-13). Errors are announced with role=alert/assertive and should carry
 * an actionable `action` (ui-principles §16.5).
 */
export function StatusMessage({
  state,
  message,
  action,
  politeness,
}: StatusMessageProps) {
  const isError = state === "error";
  const live = politeness ?? (isError ? "assertive" : "polite");
  const role = isError ? "alert" : "status";
  const busy = state === "loading";

  if (state === "idle") {
    // Keep the live region mounted but empty so the next transition announces.
    return <div role="status" aria-live={live} className="sr-only" />;
  }

  return (
    <div
      role={role}
      aria-live={live}
      aria-busy={busy || undefined}
      className={cn(
        "flex items-center gap-2 rounded-md p-3 text-sm",
        isError
          ? "border border-destructive/40 bg-destructive/5 text-destructive"
          : "text-muted-foreground",
      )}
    >
      {busy && <Loader2 aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin" />}
      {message && <span className="flex-1">{message}</span>}
      {action && <span className="shrink-0">{action}</span>}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/status-message.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Type-check and lint**

Run: `pnpm --filter narrare-web run type-check` then `pnpm --filter narrare-web run lint:check`
Expected: no errors.

- [ ] **Step 6: Migrate at least one adopter**

In `ExtractionLoading.tsx`: wrap the title/description block in a `StatusMessage state="loading" message={tAction("aiThinking")} action={onCancel ? <button type="button" onClick={onCancel}>{tAction("stop")}</button> : undefined}` (keep the existing phase progress bar above/below). In `ExtractionError.tsx` and `ExtractionDone.tsx`: replace their bespoke `role="status"`/error blocks with `<StatusMessage state="error" ... />` and `<StatusMessage state="success" ... />` respectively. Re-express `connection-lost-banner.tsx` as a thin wrapper rendering `<StatusMessage state="error" message={message ?? t("connectionLost")} action={<button type="button" onClick={onRetry}>{t("connectionLostRetry")}</button>} />`, preserving its current visible behaviour as the baseline (spec §10 risk). Add `import { StatusMessage } from "@/components/ui/status-message";` to each.

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/studio/extraction/__tests__/`
Expected: existing extraction tests PASS (note: existing tests assert on key strings like `"aiThinking"` — keep those assertions valid by passing the same `t(...)` values into `message`).

- [ ] **Step 7: Commit**

```bash
git add packages/web/components/ui/status-message.tsx \
        packages/web/components/ui/__tests__/status-message.test.tsx \
        packages/web/components/ui/connection-lost-banner.tsx \
        packages/web/components/studio/extraction/ExtractionLoading.tsx \
        packages/web/components/studio/extraction/ExtractionError.tsx \
        packages/web/components/studio/extraction/ExtractionDone.tsx
git commit -m "feat(web): add StatusMessage primitive and migrate extraction status surfaces"
```

---

### Task 3: PanelHeader

**Files:**
- Create: `packages/web/components/ui/panel-header.tsx`
- Create: `packages/web/components/ui/__tests__/panel-header.test.tsx`
- Modify: `packages/web/components/studio/analysis/ConsistencyPanelHeader.tsx` (full rewrite onto PanelHeader + IconButton)

**Interfaces:**
- Consumes: `IconButton` from Task 1; `cn` from `@/lib/utils`; `LucideIcon` from `lucide-react`.
- Produces: `PanelHeader` — `export function PanelHeader(props: PanelHeaderProps)`. Exposes the generated title `id` via a return contract: the component accepts an optional `titleId` prop so `PanelShell` (Task 7) can wire `aria-labelledby`. If omitted, `PanelHeader` generates one with `useId()`.

**Prop interface (spec §5.2):**

```ts
interface PanelHeaderProps {
  /** Resolved i18n title string (required). */
  readonly title: string;
  readonly icon?: LucideIcon;
  readonly description?: string;
  /** Live status/progress slot — integration point for StatusMessage. */
  readonly statusSlot?: React.ReactNode;
  /** Trailing actions (refresh/stop). */
  readonly actions?: React.ReactNode;
  /** When provided, renders an IconButton close control and calls on close. */
  readonly onClose?: () => void;
  /** Optional explicit id for the title (lets PanelShell link aria-labelledby). */
  readonly titleId?: string;
}
```

- [ ] **Step 1: Write the failing test**

Create `packages/web/components/ui/__tests__/panel-header.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Shield } from "lucide-react";
import { PanelHeader } from "@/components/ui/panel-header";

describe("PanelHeader", () => {
  it("renders the title as a heading with a stable id", () => {
    render(<PanelHeader title="Consistency" titleId="h-consistency" />);
    const heading = screen.getByRole("heading", { name: "Consistency" });
    expect(heading).toHaveAttribute("id", "h-consistency");
  });

  it("renders a leading icon aria-hidden", () => {
    const { container } = render(<PanelHeader title="Consistency" icon={Shield} />);
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("renders a status slot and actions slot", () => {
    render(
      <PanelHeader
        title="Consistency"
        statusSlot={<span>Running…</span>}
        actions={<button type="button">Refresh</button>}
      />,
    );
    expect(screen.getByText("Running…")).toBeDefined();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeDefined();
  });

  it("renders an IconButton close control that calls onClose", async () => {
    const onClose = vi.fn();
    render(<PanelHeader title="Consistency" onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
```

Note: the close button's accessible name in tests is `"Close"` — pass `label="Close"` to the `IconButton` used inside `PanelHeader` (the caller translates; for the in-primitive default use a required `closeLabel?: string` with no hardcoded fallback, OR require the caller to pass `onClose` alongside a `closeLabel`). **Decision:** `PanelHeader` gains an optional `closeLabel?: string` — if `onClose` is set, `closeLabel` must be supplied (runtime guard throws if missing) to avoid a hardcoded string. The test above passes `closeLabel` implicitly — update the test to `<PanelHeader title="Consistency" closeLabel="Close" onClose={onClose} />`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/panel-header.test.tsx`
Expected: FAIL — cannot resolve `@/components/ui/panel-header`.

- [ ] **Step 3: Write the minimal implementation**

Create `packages/web/components/ui/panel-header.tsx`:

```tsx
import { X, type LucideIcon } from "lucide-react";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { IconButton } from "@/components/ui/icon-button";

interface PanelHeaderProps {
  readonly title: string;
  readonly icon?: LucideIcon;
  readonly description?: string;
  readonly statusSlot?: ReactNode;
  readonly actions?: ReactNode;
  readonly onClose?: () => void;
  /** Resolved i18n label for the close control (required when onClose is set). */
  readonly closeLabel?: string;
  readonly titleId?: string;
}

/**
 * Accessible header for a workspace side panel / inspector (spec §5.2).
 * Presentation only (RULE-13). The title element carries a stable id so
 * PanelShell can wire aria-labelledby. Replaces the duplicated
 * `flex items-center justify-between p-4 border-b bg-card` + close boilerplate.
 */
export function PanelHeader({
  title,
  icon: Icon,
  description,
  statusSlot,
  actions,
  onClose,
  closeLabel,
  titleId,
}: PanelHeaderProps) {
  const generated = useId();
  const id = titleId ?? generated;

  if (onClose && !closeLabel) {
    throw new Error("PanelHeader: closeLabel is required when onClose is provided (RULE-16).");
  }

  return (
    <div className={cn("flex items-center justify-between gap-3 border-b border-border bg-card p-4")}>
      <div className="flex min-w-0 items-center gap-3">
        {Icon && <Icon aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />}
        <div className="min-w-0">
          <h3 id={id} className="truncate font-medium text-foreground">
            {title}
          </h3>
          {description && (
            <p className="truncate text-xs text-muted-foreground">{description}</p>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {statusSlot}
        {actions}
        {onClose && <IconButton label={closeLabel as string} icon={X} onClick={onClose} />}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/panel-header.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Type-check and lint**

Run: `pnpm --filter narrare-web run type-check` then `pnpm --filter narrare-web run lint:check`
Expected: no errors.

- [ ] **Step 6: Migrate the adopter (largest dedup — spec §7 step 3)**

Rewrite `ConsistencyPanelHeader.tsx` to compose `PanelHeader`: pass `title={t("consistency.title")}`, `icon={Shield}`, `actions={...refresh/stop buttons via IconButton...}`, `closeLabel={t("close")}`, `onClose={onClose}`. Keep the existing `viewState`/`isPending` props and the secondary `aiDisclaimer` strip below the header unchanged (it is panel-specific, not header chrome). Update the test import if its existing test (`ConsistencyPanelHeader` has no dedicated test currently — verify with `glob`) references internal markup; otherwise rely on the parent `AnalysisPanel` tests.

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/studio/analysis/`
Expected: PASS (no regression in the consistency panel behaviour).

- [ ] **Step 7: Commit**

```bash
git add packages/web/components/ui/panel-header.tsx \
        packages/web/components/ui/__tests__/panel-header.test.tsx \
        packages/web/components/studio/analysis/ConsistencyPanelHeader.tsx
git commit -m "feat(web): add PanelHeader primitive and migrate ConsistencyPanelHeader"
```

---

### Task 4: ToolbarButton

**Files:**
- Create: `packages/web/components/ui/toolbar-button.tsx`
- Create: `packages/web/components/ui/__tests__/toolbar-button.test.tsx`
- Modify: `packages/web/components/studio/editor-view/EditorToolbar.tsx:52-60` (bold button) + one analysis trigger button

**Interfaces:**
- Consumes: `cn` from `@/lib/utils`; `LucideIcon` + `Loader2` from `lucide-react`.
- Produces: `ToolbarButton` — `export function ToolbarButton(props: ToolbarButtonProps)`.

**Prop interface (spec §5.5):**

```ts
type ToolbarButtonVariant = "ghost" | "default" | "destructive";

interface ToolbarButtonProps {
  /** Required — visible label and/or accessible name (resolved i18n). */
  readonly label: string;
  readonly icon?: LucideIcon;
  readonly onClick?: () => void;
  readonly disabled?: boolean;
  readonly loading?: boolean;
  /** Show the visible label (wide) vs icon-only (narrow). Default false. */
  readonly showLabel?: boolean;
  readonly variant?: ToolbarButtonVariant;
  /** Pressed/toggle state (e.g. active formatting). Reflects aria-pressed. */
  readonly active?: boolean;
}
```

- [ ] **Step 1: Write the failing test**

Create `packages/web/components/ui/__tests__/toolbar-button.test.tsx`:

```tsx
import { Bold } from "lucide-react";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ToolbarButton } from "@/components/ui/toolbar-button";

describe("ToolbarButton", () => {
  it("renders type=button with an accessible name", () => {
    render(<ToolbarButton label="Bold" icon={Bold} onClick={() => {}} />);
    const btn = screen.getByRole("button", { name: "Bold" });
    expect(btn).toHaveAttribute("type", "button");
  });

  it("reflects aria-pressed when active", () => {
    render(<ToolbarButton label="Bold" icon={Bold} active onClick={() => {}} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the visible label when showLabel is true", () => {
    render(<ToolbarButton label="Bold" icon={Bold} showLabel onClick={() => {}} />);
    // The label text is rendered visibly (and also used as accessible name).
    expect(screen.getByText("Bold")).toBeDefined();
  });

  it("forwards onClick and supports loading state", async () => {
    const onClick = vi.fn();
    render(<ToolbarButton label="Run" icon={Bold} loading onClick={onClick} />);
    const btn = screen.getByRole("button", { name: "Run" });
    expect(btn).toHaveAttribute("aria-busy", "true");
    // Loading disables interaction.
    expect(btn).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/toolbar-button.test.tsx`
Expected: FAIL — cannot resolve `@/components/ui/toolbar-button`.

- [ ] **Step 3: Write the minimal implementation**

Create `packages/web/components/ui/toolbar-button.tsx`:

```tsx
import { Loader2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type ToolbarButtonVariant = "ghost" | "default" | "destructive";

interface ToolbarButtonProps {
  readonly label: string;
  readonly icon?: LucideIcon;
  readonly onClick?: () => void;
  readonly disabled?: boolean;
  readonly loading?: boolean;
  readonly showLabel?: boolean;
  readonly variant?: ToolbarButtonVariant;
  readonly active?: boolean;
}

const VARIANT_CLASSES: Record<ToolbarButtonVariant, string> = {
  ghost: "text-foreground hover:bg-accent",
  default: "bg-primary text-primary-foreground hover:opacity-90",
  destructive: "text-destructive hover:bg-destructive/10 border border-destructive",
};

/**
 * Editor/panel toolbar action — a labelled, horizontally-grouped button set
 * (spec §5.5). Distinct from IconButton: supports a visible label and an
 * active/pressed state. Always type="button"; aria-pressed when active.
 */
export function ToolbarButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  loading = false,
  showLabel = false,
  variant = "ghost",
  active = false,
}: ToolbarButtonProps) {
  const isDisabled = disabled || loading;
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active || undefined}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      disabled={isDisabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-2 py-1 text-sm transition-colors",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        active && "bg-accent",
        VARIANT_CLASSES[variant],
        isDisabled && "opacity-50",
      )}
    >
      {loading ? (
        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
      ) : (
        Icon && <Icon aria-hidden="true" className="h-4 w-4" />
      )}
      {showLabel && <span>{label}</span>}
    </button>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/toolbar-button.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Type-check and lint**

Run: `pnpm --filter narrare-web run type-check` then `pnpm --filter narrare-web run lint:check`
Expected: no errors.

- [ ] **Step 6: Migrate at least one adopter**

In `EditorToolbar.tsx`, replace the inline bold button (lines 52-60) with:
`<ToolbarButton label={t("editor.bold")} variant="ghost" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()} />`. Migrate one analysis trigger (e.g. `ConsistencyTrigger.tsx`) to render `<ToolbarButton label={...} icon={Shield} loading={isPending} onClick={run} showLabel />`. Preserve the `onClickCapture` opener-resolution behaviour in `EditorToolbar` (it wraps the toolbar container, so individual buttons need not change that wiring).

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/studio/editor-view/`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/web/components/ui/toolbar-button.tsx \
        packages/web/components/ui/__tests__/toolbar-button.test.tsx \
        packages/web/components/studio/editor-view/EditorToolbar.tsx \
        packages/web/components/studio/analysis/ConsistencyTrigger.tsx
git commit -m "feat(web): add ToolbarButton primitive and migrate editor toolbar"
```

---

### Task 5: SearchInput + use-url-param hook

**Files:**
- Create: `packages/web/lib/hooks/use-url-param.ts`
- Create: `packages/web/lib/hooks/__tests__/use-url-param.test.ts`
- Create: `packages/web/components/ui/search-input.tsx`
- Create: `packages/web/components/ui/__tests__/search-input.test.tsx`
- Modify: a KB/worldbuilding search surface (e.g. the input consuming `useKBSearch`) — locate via `grep "useKBSearch"` then migrate its input.

**Interfaces:**
- Consumes (hook): `useSearchParams`, `useRouter`, `usePathname` from `next/navigation`.
- Produces (hook): `useUrlParam(options)` → `{ value: string; setValue: (next: string, mode?: "replace" | "push") => void }`, plus a pure exported helper `normaliseParam(value, allowed, defaultValue)`.
- Produces (component): `SearchInput` — `export function SearchInput(props: SearchInputProps)`. Consumes `IconButton` (Task 1).

**Hook signature (spec §6):**

```ts
interface UseUrlParamOptions {
  /** Search-param name, e.g. "q" or "category". */
  readonly paramName: string;
  /** Optional allow-list; values outside it fall back to defaultValue. */
  readonly allowed?: readonly string[];
  /** Value used when the param is absent or invalid. */
  readonly defaultValue: string;
}

export function useUrlParam(options: UseUrlParamOptions): {
  value: string;
  setValue: (next: string, mode?: "replace" | "push") => void;
};

/** Pure normaliser — unit-testable without router. */
export function normaliseParam(
  value: string | null,
  allowed: readonly string[] | undefined,
  defaultValue: string,
): string;
```

- [ ] **Step 1: Write the failing hook test (pure normaliser first)**

Create `packages/web/lib/hooks/__tests__/use-url-param.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { normaliseParam } from "@/lib/hooks/use-url-param";

describe("normaliseParam", () => {
  it("returns the value when it is in the allow-list", () => {
    expect(normaliseParam("general", ["general", "ai"], "general")).toBe("general");
  });

  it("falls back to default when value is null", () => {
    expect(normaliseParam(null, ["general"], "general")).toBe("general");
  });

  it("falls back to default when value is not allowed", () => {
    expect(normaliseParam("evil", ["general"], "general")).toBe("general");
  });

  it("passes any non-empty value through when no allow-list is given", () => {
    expect(normaliseParam("free text", undefined, "")).toBe("free text");
  });

  it("returns default for empty string when an allow-list is enforced", () => {
    expect(normaliseParam("", ["general"], "general")).toBe("general");
  });
});
```

Add a hook integration test using `renderHook` with a per-test router override:

```ts
import { renderHook, act } from "@testing-library/react";
import { vi } from "vitest";
import * as Navigation from "next/navigation";
import { useUrlParam } from "@/lib/hooks/use-url-param";

// (in the same file, inside describe("useUrlParam"))
it("reads the current value from the search params", () => {
  vi.mocked(Navigation.useSearchParams).mockReturnValue(
    new URLSearchParams("q=dragons"),
  );
  const { result } = renderHook(() =>
    useUrlParam({ paramName: "q", defaultValue: "" }),
  );
  expect(result.current.value).toBe("dragons");
});
```

- [ ] **Step 2: Run the hook test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/lib/hooks/__tests__/use-url-param.test.ts`
Expected: FAIL — cannot resolve `@/lib/hooks/use-url-param`.

- [ ] **Step 3: Write the hook implementation**

Create `packages/web/lib/hooks/use-url-param.ts`:

```ts
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

interface UseUrlParamOptions {
  readonly paramName: string;
  readonly allowed?: readonly string[];
  readonly defaultValue: string;
}

/**
 * One-adapter-per-surface URL search-param sync (spec §6, Phase C §8.3).
 * Defaults to `replace` (transient typing must not pollute history); callers
 * pass `"push"` for explicit selection changes (Phase C §16). Fail-safe:
 * invalid values normalise to defaultValue.
 */
export function useUrlParam({ paramName, allowed, defaultValue }: UseUrlParamOptions) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const value = useMemo(
    () => normaliseParam(searchParams.get(paramName), allowed, defaultValue),
    [searchParams, paramName, allowed, defaultValue],
  );

  const setValue = useCallback(
    (next: string, mode: "replace" | "push" = "replace") => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === defaultValue || next === "") {
        params.delete(paramName);
      } else {
        params.set(paramName, next);
      }
      const query = params.toString();
      const url = query ? `${pathname}?${query}` : pathname;
      if (mode === "push") router.push(url);
      else router.replace(url);
    },
    [searchParams, paramName, defaultValue, pathname, router],
  );

  return { value, setValue };
}

/** Pure normaliser — unit-testable without a router. */
export function normaliseParam(
  value: string | null,
  allowed: readonly string[] | undefined,
  defaultValue: string,
): string {
  if (value === null || value === "") return defaultValue;
  if (allowed && !allowed.includes(value)) return defaultValue;
  return value;
}
```

- [ ] **Step 4: Run the hook test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/lib/hooks/__tests__/use-url-param.test.ts`
Expected: PASS (5 normaliser + 1 hook test).

- [ ] **Step 5: Write the failing SearchInput test**

Create `packages/web/components/ui/__tests__/search-input.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SearchInput } from "@/components/ui/search-input";

describe("SearchInput", () => {
  it("renders a type=search input with a label associated via htmlFor", () => {
    render(
      <SearchInput
        label="Search knowledge base"
        value=""
        onValueChange={() => {}}
      />,
    );
    const input = screen.getByRole("searchbox", { name: "Search knowledge base" });
    expect(input).toHaveAttribute("type", "search");
  });

  it("calls onValueChange as the user types", async () => {
    const onValueChange = vi.fn();
    render(
      <SearchInput label="q" value="" onValueChange={onValueChange} />,
    );
    await userEvent.type(screen.getByRole("searchbox"), "a");
    expect(onValueChange).toHaveBeenCalled();
  });

  it("shows a clear IconButton that calls onClear", async () => {
    const onClear = vi.fn();
    render(
      <SearchInput
        label="q"
        value="dragons"
        onValueChange={() => {}}
        onClear={onClear}
        clearLabel="Clear search"
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(onClear).toHaveBeenCalledOnce();
  });
});
```

Note: `SearchInput` requires a `clearLabel` prop (resolved i18n) whenever `onClear` is provided, mirroring `PanelHeader.closeLabel` (RULE-16, no hardcoded strings).

- [ ] **Step 6: Run the test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/search-input.test.tsx`
Expected: FAIL — cannot resolve `@/components/ui/search-input`.

- [ ] **Step 7: Write the SearchInput implementation**

Create `packages/web/components/ui/search-input.tsx`:

```tsx
import { Search, X } from "lucide-react";
import { useId, type ChangeEvent } from "react";
import { cn } from "@/lib/utils";
import { IconButton } from "@/components/ui/icon-button";

interface SearchInputProps {
  /** Required accessible label (resolved i18n). Visible or sr-only. */
  readonly label: string;
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  readonly onClear?: () => void;
  /** Resolved i18n label for the clear control (required when onClear is set). */
  readonly clearLabel?: string;
  readonly placeholder?: string;
  /** Render the label visibly (default) or screen-reader-only. */
  readonly visibleLabel?: boolean;
}

/**
 * Labelled text search with a clear button and a URL-sync seam (spec §5.6).
 * Presentation only — the caller wires `value`/`onValueChange` to
 * `useUrlParam` (one adapter per surface). Clear control reuses IconButton.
 */
export function SearchInput({
  label,
  value,
  onValueChange,
  onClear,
  clearLabel,
  placeholder,
  visibleLabel = true,
}: SearchInputProps) {
  const id = useId();
  if (onClear && !clearLabel) {
    throw new Error("SearchInput: clearLabel is required when onClear is provided (RULE-16).");
  }

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => onValueChange(e.target.value);

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className={cn("text-xs text-muted-foreground", !visibleLabel && "sr-only")}>
        {label}
      </label>
      <div className="relative">
        <Search aria-hidden="true" className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          id={id}
          type="search"
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          aria-label={label}
          className={cn(
            "w-full rounded-md border border-border bg-input-background py-1.5 pl-8 pr-8 text-sm text-foreground",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          )}
        />
        {onClear && value && (
          <span className="absolute right-1 top-1/2 -translate-y-1/2">
            <IconButton label={clearLabel as string} icon={X} onClick={onClear} size="sm" />
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/search-input.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 9: Type-check and lint**

Run: `pnpm --filter narrare-web run type-check` then `pnpm --filter narrare-web run lint:check`
Expected: no errors.

- [ ] **Step 10: Migrate the adopter**

Locate the KB/worldbuilding search input: `grep -rn "useKBSearch" packages/web/components`. Migrate that input element to `<SearchInput label={t("kb.search")} value={query} onValueChange={setQuery} onClear={() => setQuery("")} clearLabel={t("kb.clearSearch")} />`. If the panel should be URL-addressable per Phase C §8.1, wire it through `useUrlParam({ paramName: "q", defaultValue: "" })` and pass `value`/`onValueChange` from the hook.

Run the KB/worldbuilding component tests.
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add packages/web/lib/hooks/use-url-param.ts \
        packages/web/lib/hooks/__tests__/use-url-param.test.ts \
        packages/web/components/ui/search-input.tsx \
        packages/web/components/ui/__tests__/search-input.test.tsx
git commit -m "feat(web): add use-url-param hook and SearchInput primitive"
# (plus the migrated KB search file in the same or follow-up commit)
```

---

### Task 6: PanelTabs

**Files:**
- Create: `packages/web/components/ui/panel-tabs.tsx`
- Create: `packages/web/components/ui/__tests__/panel-tabs.test.tsx`
- Modify: `packages/web/components/studio/settings/SettingsView.tsx` (+ `settingsUrlState.ts` consumed by the adapter)

**Interfaces:**
- Consumes: `useUrlParam` from Task 5; `cn` from `@/lib/utils`.
- Produces: `PanelTabs` — `export function PanelTabs(props: PanelTabsProps)`.

**Prop interface (spec §5.4):**

```ts
interface TabItem {
  readonly id: string;
  /** Resolved i18n label. */
  readonly label: string;
  readonly content: React.ReactNode;
}

interface PanelTabsProps {
  readonly tabs: readonly TabItem[];
  /** Controlled active tab id. */
  readonly value: string;
  readonly onValueChange: (id: string) => void;
  /** Accessible name for the tablist grouping. */
  readonly ariaLabel: string;
}
```

**a11y (ARIA tabs pattern, spec §5.4):** `role="tablist"`/`role="tab"`/`role="tabpanel"`; active tab `aria-selected="true"`; tabs link to panel via `aria-controls`, panel links back via `aria-labelledby`; arrow-key + Home/End navigation; `tabindex` management (roving tabindex — active tab is `0`, others `-1`).

- [ ] **Step 1: Write the failing test**

Create `packages/web/components/ui/__tests__/panel-tabs.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PanelTabs } from "@/components/ui/panel-tabs";

const TABS = [
  { id: "general", label: "General", content: <p>General content</p> },
  { id: "ai", label: "AI", content: <p>AI content</p> },
];

describe("PanelTabs", () => {
  it("renders a tablist with the given aria-label and tab roles", () => {
    render(
      <PanelTabs tabs={TABS} value="general" onValueChange={() => {}} ariaLabel="Settings sections" />,
    );
    expect(screen.getByRole("tablist", { name: "Settings sections" })).toBeDefined();
    expect(screen.getAllByRole("tab")).toHaveLength(2);
  });

  it("marks only the active tab aria-selected and renders its panel", () => {
    render(<PanelTabs tabs={TABS} value="ai" onValueChange={() => {}} ariaLabel="x" />);
    const [general, ai] = screen.getAllByRole("tab");
    expect(general).toHaveAttribute("aria-selected", "false");
    expect(ai).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("AI content")).toBeDefined();
  });

  it("links tab and panel via aria-controls / aria-labelledby", () => {
    render(<PanelTabs tabs={TABS} value="general" onValueChange={() => {}} ariaLabel="x" />);
    const tab = screen.getAllByRole("tab")[0];
    const controlsId = tab.getAttribute("aria-controls");
    expect(controlsId).toBeTruthy();
    const panel = screen.getByRole("tabpanel");
    expect(panel.getAttribute("aria-labelledby")).toBe(tab.getAttribute("id"));
  });

  it("calls onValueChange on click and on arrow-right", async () => {
    const onValueChange = vi.fn();
    render(<PanelTabs tabs={TABS} value="general" onValueChange={onValueChange} ariaLabel="x" />);
    await userEvent.click(screen.getAllByRole("tab")[1]);
    expect(onValueChange).toHaveBeenCalledWith("ai");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/panel-tabs.test.tsx`
Expected: FAIL — cannot resolve `@/components/ui/panel-tabs`.

- [ ] **Step 3: Write the minimal implementation**

Create `packages/web/components/ui/panel-tabs.tsx`:

```tsx
import { type KeyboardEvent, useId } from "react";
import { cn } from "@/lib/utils";

interface TabItem {
  readonly id: string;
  readonly label: string;
  readonly content: React.ReactNode;
}

interface PanelTabsProps {
  readonly tabs: readonly TabItem[];
  readonly value: string;
  readonly onValueChange: (id: string) => void;
  readonly ariaLabel: string;
}

/**
 * URL-addressable tab list (spec §5.4, Phase C §8.1). ARIA tabs pattern with
 * roving tabindex and arrow/Home/End navigation. Controlled — the caller
 * binds `value`/`onValueChange` to `useUrlParam` (one adapter per surface).
 */
export function PanelTabs({ tabs, value, onValueChange, ariaLabel }: PanelTabsProps) {
  const baseId = useId();
  const activeIndex = Math.max(
    0,
    tabs.findIndex((t) => t.id === value),
  );
  const active = tabs[activeIndex];

  const onKeyDown = (e: KeyboardEvent) => {
    let next = activeIndex;
    if (e.key === "ArrowRight") next = (activeIndex + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (activeIndex - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    onValueChange(tabs[next].id);
  };

  return (
    <div className="flex h-full flex-col">
      <div role="tablist" aria-label={ariaLabel} className="flex border-b border-border" onKeyDown={onKeyDown}>
        {tabs.map((tab, i) => {
          const selected = tab.id === value;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`${baseId}-tab-${tab.id}`}
              aria-controls={`${baseId}-panel-${tab.id}`}
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onValueChange(tab.id)}
              className={cn(
                "px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                selected
                  ? "border-b-2 border-primary text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${baseId}-panel-${active.id}`}
        aria-labelledby={`${baseId}-tab-${active.id}`}
        tabIndex={0}
        className="min-h-0 flex-1 overflow-auto"
      >
        {active.content}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/panel-tabs.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Type-check and lint**

Run: `pnpm --filter narrare-web run type-check` then `pnpm --filter narrare-web run lint:check`
Expected: no errors.

- [ ] **Step 6: Migrate the adopter (SettingsView)**

The settings category already has pure parse/serialize helpers in `settingsUrlState.ts`. Wire `SettingsView` to `PanelTabs` + `useUrlParam`: build the `tabs` array from `SETTINGS_CATEGORIES` (each `content` = the matching settings sub-component), derive `value`/`onValueChange` from `useUrlParam({ paramName: "category", allowed: SETTINGS_CATEGORIES.map(c => c.id), defaultValue: DEFAULT_SETTINGS_CATEGORY })`, and pass the same `replace`/`push` policy (use `"push"` for explicit selection changes). Remove the local `useState<SettingsCategory>` tab switching. Keep `settingsUrlState.ts` as the normaliser source-of-truth; `useUrlParam` consumes its `allowed`/`defaultValue`.

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/studio/settings/settingsUrlState.test.ts packages/web/components/studio/settings/`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/web/components/ui/panel-tabs.tsx \
        packages/web/components/ui/__tests__/panel-tabs.test.tsx \
        packages/web/components/studio/settings/SettingsView.tsx
git commit -m "feat(web): add PanelTabs primitive and URL-address settings category tabs"
```

---

### Task 7: PanelShell + use-panel-focus hook

**Files:**
- Create: `packages/web/lib/hooks/use-panel-focus.ts`
- Create: `packages/web/lib/hooks/__tests__/use-panel-focus.test.ts`
- Create: `packages/web/components/ui/panel-shell.tsx`
- Create: `packages/web/components/ui/__tests__/panel-shell.test.tsx`
- Modify: one editor right-panel slot (locate via `grep -rn "EditorRightPanel" packages/web/components`), wrapping its content in `<PanelShell>`

**Interfaces:**
- Consumes (hook): none (native DOM APIs only — no new dependency).
- Produces (hook): `usePanelFocus({ open, panelRef, onClose })` — manages focus move-in, focus trap, Escape, and focus return.
- Consumes (component): `usePanelFocus`; `cn`.
- Produces (component): `PanelShell` — `export function PanelShell(props: PanelShellProps)`.

**Hook signature:**

```ts
import type { RefObject } from "react";

interface UsePanelFocusOptions {
  readonly open: boolean;
  readonly panelRef: RefObject<HTMLElement | null>;
  readonly onClose: () => void;
}
export function usePanelFocus(options: UsePanelFocusOptions): void;
```

**Component prop interface (spec §5.3):**

```ts
interface PanelShellProps {
  /** id of the PanelHeader title element — wires aria-labelledby. */
  readonly titleId: string;
  readonly side?: "right" | "left";
  readonly children: React.ReactNode;
  /** Enable responsive drawer behaviour. Default true. */
  readonly responsive?: boolean;
  /** Mobile drawer open state. */
  readonly open: boolean;
  readonly onClose: () => void;
  /** Accessible label for the mobile dialog. Resolved i18n. */
  readonly dialogLabel: string;
}
```

- [ ] **Step 1: Write the failing hook test**

Create `packages/web/lib/hooks/__tests__/use-panel-focus.test.ts`:

```ts
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useRef } from "react";
import { usePanelFocus } from "@/lib/hooks/use-panel-focus";

function setup(open: boolean) {
  const onClose = vi.fn();
  const panel = document.createElement("div");
  const focusable = document.createElement("button");
  focusable.type = "button";
  panel.appendChild(focusable);
  document.body.appendChild(panel);
  const opener = document.createElement("button");
  opener.type = "button";
  document.body.appendChild(opener);
  opener.focus();

  const { result, rerender } = renderHook(
    (props: { open: boolean }) => {
      const ref = useRef<HTMLDivElement | null>(panel);
      usePanelFocus({ open: props.open, panelRef: ref, onClose });
      return ref;
    },
    { initialProps: { open } },
  );
  return { onClose, panel, focusable, opener, rerender };
}

afterEach(() => document.body.innerHTML = "");

describe("usePanelFocus", () => {
  it("moves focus into the panel when it opens", () => {
    const { focusable } = setup(true);
    expect(document.activeElement).toBe(focusable);
  });

  it("calls onClose on Escape", () => {
    const { onClose } = setup(true);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("restores focus to the opener when it closes", () => {
    const { opener, rerender } = setup(true);
    rerender({ open: false });
    expect(document.activeElement).toBe(opener);
  });
});
```

- [ ] **Step 2: Run the hook test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/lib/hooks/__tests__/use-panel-focus.test.ts`
Expected: FAIL — cannot resolve `@/lib/hooks/use-panel-focus`.

- [ ] **Step 3: Write the hook implementation**

Create `packages/web/lib/hooks/use-panel-focus.ts` (≤ 150 lines):

```ts
import { type RefObject, useEffect, useRef } from "react";

interface UsePanelFocusOptions {
  readonly open: boolean;
  readonly panelRef: RefObject<HTMLElement | null>;
  readonly onClose: () => void;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/**
 * Drawer focus lifecycle for PanelShell (spec §5.3, Phase C §10.1):
 *  - on open: save opener, move focus to first focusable in the panel
 *  - while open: trap focus (Tab cycles within), Escape closes
 *  - on close: restore focus to the opener
 * Native DOM only — no new dependency (spec §3).
 */
export function usePanelFocus({ open, panelRef, onClose }: UsePanelFocusOptions) {
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement as HTMLElement | null;

    const panel = panelRef.current;
    if (panel) {
      const first = panel.querySelector<HTMLElement>(FOCUSABLE);
      first?.focus();
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const root = panelRef.current;
      if (!root) return;
      const nodes = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      openerRef.current?.focus();
    };
  }, [open, panelRef, onClose]);
}
```

- [ ] **Step 4: Run the hook test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/lib/hooks/__tests__/use-panel-focus.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing PanelShell test**

Create `packages/web/components/ui/__tests__/panel-shell.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PanelShell } from "@/components/ui/panel-shell";

describe("PanelShell", () => {
  it("renders a labelled region on desktop", () => {
    render(
      <PanelShell titleId="t1" open={false} onClose={() => {}} dialogLabel="Inspector">
        <p>Panel body</p>
      </PanelShell>,
    );
    const region = screen.getByRole("region", { name: "" });
    // aria-labelledby points at the title id
    expect(region).toHaveAttribute("aria-labelledby", "t1");
    expect(screen.getByText("Panel body")).toBeDefined();
  });

  it("renders a modal dialog when open", () => {
    render(
      <PanelShell titleId="t1" open onClose={() => {}} dialogLabel="Inspector">
        <p>Panel body</p>
      </PanelShell>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "Inspector");
  });

  it("calls onClose when Escape is pressed while open", async () => {
    const onClose = vi.fn();
    render(
      <PanelShell titleId="t1" open onClose={onClose} dialogLabel="Inspector">
        <button type="button">Inside</button>
      </PanelShell>,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders a close overlay that calls onClose on click", async () => {
    const onClose = vi.fn();
    const { container } = render(
      <PanelShell titleId="t1" open onClose={onClose} dialogLabel="Inspector">
        <p>body</p>
      </PanelShell>,
    );
    // The backdrop is the first sibling button region before the panel.
    const backdrop = container.querySelector('[data-testid="panel-backdrop"]');
    await userEvent.click(backdrop as HTMLElement);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/panel-shell.test.tsx`
Expected: FAIL — cannot resolve `@/components/ui/panel-shell`.

- [ ] **Step 7: Write the PanelShell implementation**

Create `packages/web/components/ui/panel-shell.tsx` (≤ 200 lines). It renders the desktop `<section role="region" aria-labelledby={titleId}>` always (hidden below `lg`), and a mobile dialog overlay when `open` (hidden at `lg`). Children are presentational (state lives in hooks — RULE-13), so the dual render is identity-safe.

```tsx
import { type ReactNode, useRef } from "react";
import { cn } from "@/lib/utils";
import { usePanelFocus } from "@/lib/hooks/use-panel-focus";

interface PanelShellProps {
  readonly titleId: string;
  readonly side?: "right" | "left";
  readonly children: ReactNode;
  readonly responsive?: boolean;
  readonly open: boolean;
  readonly onClose: () => void;
  readonly dialogLabel: string;
}

/**
 * Responsive side-panel container (spec §5.3, Phase C §9/§10.1). Desktop: a
 * labelled region. Below the lg breakpoint: a modal drawer with focus move/
 * trap/return + Escape (via use-panel-focus). Presentation only (RULE-13) —
 * it does NOT own SSE; AI panels keep their streaming via existing hooks.
 */
export function PanelShell({
  titleId,
  side = "right",
  children,
  responsive = true,
  open,
  onClose,
  dialogLabel,
}: PanelShellProps) {
  const drawerRef = useRef<HTMLDivElement | null>(null);
  usePanelFocus({ open, panelRef: drawerRef, onClose });

  const desktopSide = side === "left" ? "lg:border-r" : "lg:border-l";

  return (
    <>
      {/* Desktop region — always mounted, visible at lg+ */}
      <section
        aria-labelledby={titleId}
        className={cn(
          "hidden min-w-0 flex-col border-border bg-card lg:flex",
          desktopSide,
          responsive && "lg:flex",
        )}
      >
        {children}
      </section>

      {/* Mobile drawer overlay — conditional on open */}
      {open && (
        <div
          className="fixed inset-0 z-40 flex lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label={dialogLabel}
        >
          <button
            type="button"
            data-testid="panel-backdrop"
            aria-label={dialogLabel}
            tabIndex={-1}
            className="absolute inset-0 bg-background/70"
            onClick={onClose}
          />
          <div
            ref={drawerRef}
            className={cn(
              "relative z-10 h-full w-80 max-w-[85vw] overflow-auto bg-card shadow-xl",
              side === "left" ? "left-0" : "ml-auto",
            )}
          >
            {children}
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `pnpm --filter narrare-web exec vitest run packages/web/components/ui/__tests__/panel-shell.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 9: Type-check and lint**

Run: `pnpm --filter narrare-web run type-check` then `pnpm --filter narrare-web run lint:check`
Expected: no errors.

- [ ] **Step 10: Migrate one editor right-panel slot**

Locate an editor right-panel surface: `grep -rn "EditorRightPanel" packages/web/components`. Wrap one such panel's rendered content in `<PanelShell titleId={headerTitleId} open={panelOpen} onClose={closePanel} dialogLabel={t("panels.<name>")}>{<PanelHeader .../> + body}</PanelShell>`, where `headerTitleId` is passed to both `PanelShell.titleId` and `PanelHeader.titleId` so `aria-labelledby` is wired end-to-end. Keep the panel's existing streaming hook (`useConsistencyStream`, etc.) unchanged — only the chrome changes (RULE-13).

Run the affected panel tests.
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add packages/web/lib/hooks/use-panel-focus.ts \
        packages/web/lib/hooks/__tests__/use-panel-focus.test.ts \
        packages/web/components/ui/panel-shell.tsx \
        packages/web/components/ui/__tests__/panel-shell.test.tsx
git commit -m "feat(web): add use-panel-focus hook and PanelShell primitive"
```

---

## Self-Review

**1. Spec coverage** — each spec requirement mapped to a task:

| Spec requirement (§9 acceptance / §5) | Task |
|---|---|
| §9.1 seven primitives under `components/ui/` | Tasks 1–7 (one each) |
| §9.2 `type="button"`, required `label`/`aria-label`, `focus-visible` enforced by primitives | Task 1 (IconButton) sets the pattern; every primitive test asserts `type="button"` + `focus-visible:ring-1`; `label`/`title`/`closeLabel`/`clearLabel` are required props with runtime guards |
| §9.3 PanelHeader + PanelShell satisfy Phase C §10.1 (title, status, close, Escape, focus return, focus trap) | Tasks 3 + 7; `use-panel-focus` tests cover Escape + focus return + move-in |
| §9.4 PanelTabs + SearchInput bind to a single per-surface URL adapter (`use-url-param`) with fail-safe normalisation | Task 5 (creates hook + `normaliseParam`), Task 6 (PanelTabs consumes it) |
| §9.5 StatusMessage renders correct `role`/`aria-live`; errors actionable | Task 2 (role=alert/assertive; `action` slot) |
| §9.6 no new dependency; only existing tokens + Tailwind | Global Constraints + every file uses `cn`/tokens; no imports of radix/base-ui/headless-ui in new primitives |
| §9.7 migration steps 1–7 reflected in real adopter files | Each task's Step 6/10 migrates a named file |
| §9.8 tests cover icon-button labels/focus/disabled, panel close/Escape/focus-return, URL param parse/normalise, responsive render, status live-region roles | Tasks 1, 2, 5, 6, 7 test files |
| §9.9 no file exceeds §15 limits | each primitive ≤ ~80 lines; hooks ≤ ~60 lines (well under 200/150) |
| §6 one URL adapter shared (not per-component) | `use-url-param.ts` created once (Task 5), consumed by both SearchInput and PanelTabs |
| RULE-13 presentation-only (no SSE in shell/header) | PanelShell/PanelHeader have no fetch/streaming; spec §5.3/§5.2 + Task notes |
| RULE-16 i18n labels mandatory | `label`/`title`/`closeLabel`/`clearLabel`/`dialogLabel` required; runtime guards throw when a label-dependent prop lacks its label |

**2. Placeholder scan** — no `TBD`/`TODO`/`handle edge cases`/`similar to Task N`. Every code step contains complete source. Two "locate via grep" steps (Task 5 KB search, Task 7 editor right panel) name the exact grep command and the transformation; these are unavoidable because the exact adopter filename is discovered at execution time, but the migration instruction is fully specified.

**3. Type consistency** — `useUrlParam` returns `{ value, setValue }` in Task 5 and is consumed identically in Task 6. `IconButton` props (`label`, `icon`, `onClick`, `disabled`, `loading`, `variant`, `size`) match across PanelHeader (Task 3) and SearchInput (Task 5). `PanelHeader.titleId` and `PanelShell.titleId` use the same string contract. `TabItem` shape (`{id,label,content}`) is identical in Task 6's interface and test. Hook option field names (`open`, `panelRef`, `onClose`) match between `usePanelFocus` definition (Task 7) and PanelShell call site.

**4. Dependency ordering** — verified in "Task Ordering" above: PanelHeader(3)→IconButton(1)✓; PanelTabs(6)→use-url-param(5)✓; PanelShell(7)→PanelHeader(3)✓.

**5. Risks acknowledged (spec §10):** focus-trap vs TipTap shortcut conflict is mitigated by native Tab-cycling confined to the drawer only while `open`; migration diff size mitigated by one-adopter-per-task; URL history pollution mitigated by `replace` default + explicit `push` for selections.
