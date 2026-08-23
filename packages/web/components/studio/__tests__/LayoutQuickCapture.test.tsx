/**
 * Quick-capture placement regression (NOTES-001 §7, T29b): the provider
 * mounts ONCE in the (studio) layout — inside AuthGate and the root layout's
 * QueryProvider — so capture is live on EVERY studio page, not only
 * shell-mounted ones. /scratchpad renders ScratchpadWorkspace directly (no
 * StudioWorkspaceShell), which dead-ended Ctrl/⌘+Shift+U while the provider
 * lived in the shell (T29). A second provider in the shell would double-fire
 * the shortcut and double-render panels, so the shell test asserts exactly
 * one panel behind a single shortcut press.
 *
 * Conventions: the probe mirrors QuickCapture.test.tsx; the QueryClient
 * wrapper mirrors the repo-standard renderWithProviders
 * (Sidebar.scratchpad.test.tsx) because the opened panel mounts
 * useCreateNote. AuthGate resolves against the default MSW auth/me handler
 * after setAccessToken (lib/api test convention).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import StudioLayout from "@/app/(studio)/layout";
import { useQuickCapture } from "@/components/notes/QuickCaptureProvider";
import { StudioWorkspaceShell } from "@/components/studio/shell/StudioWorkspaceShell";
import { setAccessToken } from "@/lib/api/client";

vi.mock("@/components/studio/Sidebar", () => ({
  Sidebar: () => <aside data-testid="workspace-sidebar">Sidebar</aside>,
}));
vi.mock("@/components/ui/toaster", () => ({ Toaster: () => null }));
vi.mock("@/components/ui/feature-tour", () => ({ FeatureTour: () => null }));
vi.mock("@/lib/config/feature-tour-steps", () => ({ FEATURE_TOUR_STEPS: [] }));

/** Stands in for a non-shell studio page (e.g. /scratchpad). */
function QuickCaptureProbe() {
  const { open } = useQuickCapture();
  return (
    <button type="button" data-testid="layout-probe-open" onClick={open}>
      open quick capture
    </button>
  );
}

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("studio layout quick-capture placement", () => {
  it("is live on non-shell pages: useQuickCapture().open() reveals the panel", async () => {
    setAccessToken("test-access-token");
    renderWithQueryClient(
      <StudioLayout>
        <QuickCaptureProbe />
      </StudioLayout>,
    );

    fireEvent.click(await screen.findByTestId("layout-probe-open"));
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
  });

  it("reveals exactly one panel behind the shortcut when the shell renders inside the layout", async () => {
    setAccessToken("test-access-token");
    renderWithQueryClient(
      <StudioLayout>
        <StudioWorkspaceShell>
          <QuickCaptureProbe />
        </StudioWorkspaceShell>
      </StudioLayout>,
    );

    await screen.findByTestId("workspace-sidebar");
    // If the shell ever re-mounts its own provider, both window listeners
    // fire on one press and two panels mount — this must stay at one.
    fireEvent.keyDown(window, { metaKey: true, shiftKey: true, key: "U" });
    expect(screen.getAllByTestId("quick-capture-panel")).toHaveLength(1);
  });
});
