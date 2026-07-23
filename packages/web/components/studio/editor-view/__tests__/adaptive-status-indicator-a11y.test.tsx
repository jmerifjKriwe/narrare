/**
 * axe-core a11y tests for AdaptiveStatusIndicator (ADR-069 §26 + §28; Task 12).
 *
 * The behavioural contract (3 states, Escape-to-close, outside-click, focus
 * return) is covered by `AdaptiveStatusIndicator.test.tsx`. This file adds the
 * a11y gate on top:
 *  - axe scan per state (active / paused / no-data) for the closed indicator.
 *  - axe scan of the OPEN non-modal popover (labelled `role="dialog"` + a
 *    named deep-link).
 *  - reduced-motion: the active-state pulse is gated behind `motion-safe:`
 *    (web-design-guidelines) — asserted structurally since happy-dom cannot
 *    evaluate the `prefers-reduced-motion` media query.
 *  - focus visibility: the trigger carries a `focus-visible` ring class.
 *
 * `color-contrast` + `region` are disabled in the shared {@link runAxe} runner
 * (see `lib/test/axe.ts`).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { AdaptiveStatusIndicator } from "@/components/studio/editor-view/AdaptiveStatusIndicator";
import { runAxe } from "@/lib/test/axe";
import { server } from "@/mocks/server";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

function testQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

const base = (overrides: Record<string, unknown>) => ({
  project_id: "proj-1",
  enabled: true,
  has_any_signal: true,
  weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
  sources: {
    preference_text: "",
    voice_profiles_text: "",
    style_constraints_text: "",
    avoidance_patterns_text: "",
  },
  ...overrides,
});

function renderIndicator(overrides: Record<string, unknown> = {}) {
  server.use(
    http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(base(overrides))),
  );
  return render(<AdaptiveStatusIndicator novelId="proj-1" />, {
    wrapper: wrapper(testQueryClient()),
  });
}

afterEach(() => server.resetHandlers());

// ---------------------------------------------------------------------------
// Closed indicator — per-state axe scan.
// ---------------------------------------------------------------------------

describe("AdaptiveStatusIndicator a11y (states)", () => {
  it("active state: icon + label, no violations", async () => {
    const { container } = renderIndicator(base({}));
    const trigger = await screen.findByRole("button", { name: "indicator.active" });
    // Colour-not-alone: state is conveyed by icon + text label, not colour.
    expect(trigger).toHaveTextContent("indicator.active");
    // Focus visibility: the trigger exposes a focus-visible ring.
    expect(trigger.className).toContain("focus-visible:ring");
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("paused state: muted, no violations", async () => {
    const { container } = renderIndicator({ enabled: false });
    await screen.findByRole("button", { name: "indicator.paused" });
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("no-data state: dashed icon, no violations", async () => {
    const { container } = renderIndicator({ enabled: false, has_any_signal: false });
    await screen.findByRole("button", { name: "indicator.noData" });
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("active-state pulse is gated behind prefers-reduced-motion", async () => {
    // The icon must animate ONLY under motion-safe (no-preference); a bare
    // animate-pulse would ignore vestibular users' reduced-motion setting.
    renderIndicator(base({}));
    const trigger = await screen.findByRole("button", { name: "indicator.active" });
    const icon = trigger.querySelector("[aria-hidden='true']");
    expect(icon).not.toBeNull();
    const cls = icon?.className ?? "";
    expect(cls).toContain("motion-safe:animate-pulse");
    expect(cls).not.toMatch(/(^|\s)animate-pulse(\s|$)/);
  });
});

// ---------------------------------------------------------------------------
// Open popover — dialog semantics + deep-link.
// ---------------------------------------------------------------------------

describe("AdaptiveStatusIndicator popover a11y", () => {
  it("open popover is a labelled dialog with a named link, no violations", async () => {
    const { container } = renderIndicator(base({}));
    const trigger = await screen.findByRole("button", { name: "indicator.active" });
    fireEvent.click(trigger);

    const dialog = await screen.findByRole("dialog");
    // The dialog has an accessible name (aria-label) — axe `aria-dialog-name`.
    expect(dialog).toHaveAttribute("aria-label", "indicator.popoverLabel");
    // The trigger exposes the expanded + controls relationship.
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveAttribute("aria-haspopup", "dialog");
    // Deep-link is a named, reachable link.
    const manage = screen.getByRole("link", { name: "indicator.manage" });
    expect(manage).toHaveAttribute("href", "/novel/proj-1/settings?category=learning");
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("Escape closes the popover and returns focus to the trigger", async () => {
    renderIndicator(base({}));
    const trigger = await screen.findByRole("button", { name: "indicator.active" });
    fireEvent.click(trigger);
    const dialog = await screen.findByRole("dialog");
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // Focus management (web-design-guidelines: restore focus on dismiss).
    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
});
