/**
 * AdaptiveStatusIndicator — editor toolbar status signal (ADR-069 Decision 14).
 *
 * Tests the 3-state contract (active / paused / no-data) derived from the
 * canonical adaptive context, plus the accessible popover (deep-link + focus
 * management). MSW + QueryClientProvider are required because the indicator
 * reads `useAdaptiveContext` (TanStack Query); the global next-intl mock in
 * setupTests.ts returns the bare key, so queries use the leaf key
 * ("indicator.active") — matching the AdaptiveDashboard.test.tsx convention.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { AdaptiveStatusIndicator } from "@/components/studio/editor-view/AdaptiveStatusIndicator";
import { server } from "@/mocks/server";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
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

afterEach(() => server.resetHandlers());

describe("AdaptiveStatusIndicator (3 states)", () => {
  it("is active when enabled and has signal", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(base({}))));
    render(<AdaptiveStatusIndicator novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "indicator.active" })).toBeInTheDocument(),
    );
  });

  it("is paused when disabled but still has signal", async () => {
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () =>
        HttpResponse.json(base({ enabled: false })),
      ),
    );
    render(<AdaptiveStatusIndicator novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "indicator.paused" })).toBeInTheDocument(),
    );
  });

  it("is no-data when there is no signal", async () => {
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () =>
        HttpResponse.json(base({ has_any_signal: false, enabled: false })),
      ),
    );
    render(<AdaptiveStatusIndicator novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "indicator.noData" })).toBeInTheDocument(),
    );
  });
});

describe("AdaptiveStatusIndicator popover", () => {
  it("opens a dialog with the manage deep-link on click", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(base({}))));
    render(<AdaptiveStatusIndicator novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });

    const trigger = await screen.findByRole("button", { name: "indicator.active" });
    fireEvent.click(trigger);

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    const manage = screen.getByRole("link", { name: "indicator.manage" });
    expect(manage).toHaveAttribute("href", "/novel/proj-1/settings?category=learning");
  });

  it("closes the dialog on Escape and returns focus to the trigger", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(base({}))));
    render(<AdaptiveStatusIndicator novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });

    const trigger = await screen.findByRole("button", { name: "indicator.active" });
    fireEvent.click(trigger);
    const dialog = await screen.findByRole("dialog");
    fireEvent.keyDown(dialog, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("closes the dialog on outside click", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(base({}))));
    render(
      <div>
        <span data-testid="outside">elsewhere</span>
        <AdaptiveStatusIndicator novelId="proj-1" />
      </div>,
      { wrapper: wrapper(new QueryClient()) },
    );

    const trigger = await screen.findByRole("button", { name: "indicator.active" });
    fireEvent.click(trigger);
    await screen.findByRole("dialog");

    fireEvent.mouseDown(screen.getByTestId("outside"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
