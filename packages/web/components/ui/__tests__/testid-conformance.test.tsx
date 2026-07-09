/**
 * Rendered-DOM component-marker conformance — the SECOND defense line behind
 * the source-level regex gate (`scripts/check-testid.ts`, ui-principles §18.4).
 *
 * Why a second line: the regex gate scans TSX SOURCE lines for
 * `<button>`/`<input>`/`<select>`/`<a onClick>`/`role="button"` that lack a
 * `data-testid` or `aria-label`. It is fast and ratcheted, but it is blind to
 * anything that only becomes visible once the component is RENDERED:
 *
 *   1. Markers passed via a spread (`<button {...props}>`) — the literal
 *      `data-testid=` is not on the element's own source line.
 *   2. `role="button"` placed on a non-button tag whose attributes are built
 *      dynamically.
 *   3. Markers that flow through COMPOSITION (a primitive rendering another
 *      primitive that carries the marker).
 *
 * This suite renders the shared UI primitives (§17) plus a representative
 * studio component with Testing-Library and inspects the RENDERED DOM,
 * asserting every interactive element carries `data-testid` or `aria-label`
 * per ui-principles §18.1.
 *
 * Scope / intentional exclusions (documented, NOT silently omitted):
 *   - `PanelTabs` tab buttons rely on visible text (`{tab.label}`) for their
 *     accessible name and carry NEITHER `data-testid` NOR `aria-label`. The
 *     regex gate reports `panel-tabs.tsx` as CLEAN (a render-time
 *     false-negative); this suite surfaces that gap but does not enforce a
 *     fix here — it is a pre-existing marker debt tracked for separate
 *     cleanup via the §18.4 ratchet.
 *   - `ConfirmDialog` cancel/confirm buttons likewise rely on visible text.
 *     Same situation. (VolumeCard below composes a CLOSED ConfirmDialog, so
 *     those buttons are absent from its rendered DOM.)
 *   - `<a onClick>` action links are NOT checked here: React attaches click
 *     handlers via event delegation, so they do not appear as a DOM `onclick`
 *     attribute and cannot be reliably detected after render. The source-level
 *     regex gate covers them. This render test focuses on
 *     `button` / text-like `input` / `select` / `[role="button"]`, where
 *     markers reliably appear as DOM attributes.
 */
import { render } from "@testing-library/react";
import { Search } from "lucide-react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { VolumeCard } from "@/components/studio/VolumeCard";
import { IconButton } from "@/components/ui/icon-button";
import { PanelHeader } from "@/components/ui/panel-header";
import { PanelShell } from "@/components/ui/panel-shell";
import { SearchInput } from "@/components/ui/search-input";
import { StatusMessage } from "@/components/ui/status-message";
import { ToolbarButton } from "@/components/ui/toolbar-button";
import type { Volume, VolumeStats } from "@/types";

// VolumeCard's import graph touches the API client at module load; mirror the
// proven mock from VolumeCard.test.tsx so it renders without network calls.
vi.mock("@/lib/api/client", () => ({
  volumesApi: {
    list: vi.fn(),
    getStats: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

// ── Interactive-element types that need a marker (ui-principles §18.1) ───────
// Excluded input types (hidden/checkbox/radio/file/range/color/submit/reset/
// image/button) are governed by §11 accessibility rules, not the marker rule.
const INTERACTIVE_INPUT_TYPES = new Set([
  "text",
  "email",
  "password",
  "search",
  "tel",
  "url",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week",
]);

/**
 * Collect interactive elements in a rendered tree that lack BOTH
 * `data-testid` and `aria-label`. Mirrors the §18.1 definition of
 * "interactive". Returns the offending nodes so a failing assertion can print
 * their HTML for triage.
 */
function collectUnmarkedInteractive(container: HTMLElement): HTMLElement[] {
  const candidates = container.querySelectorAll<HTMLElement>(
    "button, [role='button'], select, input",
  );
  const unmarked: HTMLElement[] = [];
  for (const el of candidates) {
    if (el.tagName === "INPUT") {
      const type = (el.getAttribute("type") ?? "text").toLowerCase();
      if (!INTERACTIVE_INPUT_TYPES.has(type)) continue;
    }
    if (!el.hasAttribute("data-testid") && !el.hasAttribute("aria-label")) {
      unmarked.push(el);
    }
  }
  return unmarked;
}

/** Assertion helper: fail with the offending HTML for fast triage. */
function expectAllMarked(container: HTMLElement): void {
  const unmarked = collectUnmarkedInteractive(container);
  expect(
    unmarked,
    `interactive elements missing data-testid AND aria-label:\n${unmarked
      .map((el) => el.outerHTML)
      .join("\n")}`,
  ).toEqual([]);
}

describe("rendered marker conformance — shared UI primitives", () => {
  it("IconButton renders a button with an aria-label", () => {
    const { container } = render(<IconButton label="Open menu" icon={Search} onClick={() => {}} />);
    expectAllMarked(container);
  });

  it("ToolbarButton renders a button with an aria-label", () => {
    const { container } = render(
      <ToolbarButton label="Refresh" icon={Search} onClick={() => {}} showLabel />,
    );
    expectAllMarked(container);
  });

  it("SearchInput renders a type=search input with an aria-label", () => {
    const { container } = render(
      <SearchInput label="Search knowledge base" value="" onValueChange={() => {}} />,
    );
    expectAllMarked(container);
  });

  it("SearchInput's composed clear control (an inner IconButton) carries an aria-label through composition", () => {
    // The clear button is not a literal <button> in search-input.tsx source —
    // it is <IconButton label={clearLabel} ...>. Its aria-label is only
    // present on the RENDERED node, so the source scanner cannot confirm it.
    const { container } = render(
      <SearchInput
        label="Search knowledge base"
        value="dragons"
        onValueChange={() => {}}
        onClear={() => {}}
        clearLabel="Clear search"
      />,
    );
    expectAllMarked(container);
  });

  it("PanelHeader without onClose renders no interactive element", () => {
    const { container } = render(<PanelHeader title="Consistency" />);
    expectAllMarked(container);
  });

  it("PanelHeader's composed close control (an inner IconButton) carries an aria-label through composition", () => {
    const { container } = render(
      <PanelHeader title="Consistency" closeLabel="Close" onClose={() => {}} />,
    );
    expectAllMarked(container);
  });

  it("PanelShell renders a region (not an interactive element) with an optional data-testid", () => {
    const { container } = render(
      <PanelShell titleId="t1" dialogLabel="Inspector" testId="inspector-shell" onClose={() => {}}>
        <p>body</p>
      </PanelShell>,
    );
    expectAllMarked(container);
  });

  it("StatusMessage (loading) renders no interactive element", () => {
    const { container } = render(<StatusMessage state="loading" message="Working…" />);
    expectAllMarked(container);
  });

  it("StatusMessage's action slot composes a caller-provided marked button", () => {
    const { container } = render(
      <StatusMessage
        state="error"
        message="Something went wrong"
        action={
          <button type="button" data-testid="retry-action">
            Retry
          </button>
        }
      />,
    );
    expectAllMarked(container);
  });
});

describe("rendered marker conformance — studio component", () => {
  it("VolumeCard renders its icon buttons with aria-label and hides ConfirmDialog buttons while closed", () => {
    const volume: Volume = {
      id: "vol-1",
      novel_id: "novel-1",
      title: "Volume 1",
      subtitle: null,
      description: null,
      word_count_target: null,
      is_default: false,
      position: 0,
      created_at: "2026-01-01T00:00:00Z",
    };
    const stats: VolumeStats = {
      word_count: 1000,
      chapter_count: 2,
      word_count_target: null,
      completion_percentage: null,
    };
    const { container } = render(
      <VolumeCard
        volume={volume}
        stats={stats}
        isEditing={false}
        onStartEdit={vi.fn()}
        onCancelEdit={vi.fn()}
        onSave={vi.fn()}
        onDelete={vi.fn()}
        onReorderUp={vi.fn()}
        onReorderDown={vi.fn()}
        isFirst={false}
        isLast={false}
        isSaving={false}
      />,
    );
    expectAllMarked(container);
  });
});

describe("rendered marker check closes regex blind spots", () => {
  // Local fixture: a "composed primitive" that derives its `data-testid` from
  // a `testId` prop and renders a `role="button"` div. Two regex blind spots
  // in one: (1) the marker is not a literal `data-testid=` on the element's
  // own source line (it is built from a prop and spread), and (2) the
  // interactive element is a `role="button"` on a non-button tag. The a11y
  // lint rules below are suppressed deliberately — this IS the
  // incorrect-by-design source pattern that the source-level gate can miss
  // and this render check must catch.
  function RoleButtonDiv({ testId, children }: { testId?: string; children: ReactNode }) {
    return (
      // biome-ignore lint/a11y/useKeyWithClickEvents: deliberate role=button anti-pattern fixture under test
      // biome-ignore lint/a11y/useFocusableInteractive: deliberate role=button anti-pattern fixture under test
      // biome-ignore lint/a11y/useSemanticElements: deliberate role=button anti-pattern fixture under test
      <div role="button" onClick={() => {}} {...(testId ? { "data-testid": testId } : {})}>
        {children}
      </div>
    );
  }

  it("sees a data-testid that arrives only via a spread object (regex blind spot)", () => {
    // A marker passed through `{...props}` is invisible to the line-regex
    // scanner (it looks for the literal `data-testid=` on the element's own
    // source line), but IS present on the rendered DOM node.
    const spreadProps = { "data-testid": "spread-marked-btn" } as const;
    const { container: marked } = render(
      <button type="button" {...spreadProps}>
        marked
      </button>,
    );
    expect(collectUnmarkedInteractive(marked)).toEqual([]);

    // Same element WITHOUT the spread marker is caught by the render check —
    // proving the assertion enforces, not just accommodates, spread markers.
    const { container: bare } = render(<button type="button">bare</button>);
    const caught = collectUnmarkedInteractive(bare);
    expect(caught).toHaveLength(1);
    expect(caught[0]?.textContent).toBe("bare");
  });

  it("sees a data-testid on a role=button div that arrives via a prop (regex blind spot)", () => {
    // The marker is derived from the `testId` prop (not a literal attribute),
    // and the interactive element is a `role="button"` div rather than a
    // <button>. Both are invisible to the line-regex scanner; the render check
    // still sees the marker on the DOM node.
    const { container: marked } = render(
      <RoleButtonDiv testId="spread-role-btn">marked</RoleButtonDiv>,
    );
    expect(collectUnmarkedInteractive(marked)).toEqual([]);

    const { container: bare } = render(<RoleButtonDiv>bare</RoleButtonDiv>);
    const caught = collectUnmarkedInteractive(bare);
    expect(caught).toHaveLength(1);
    expect(caught[0]?.textContent).toBe("bare");
  });
});
