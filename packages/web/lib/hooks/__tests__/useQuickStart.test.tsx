/**
 * useQuickStart hook tests (CR-AUFG-07-29).
 *
 * Tests:
 * 1. Defaults to "blank" starter when no starter is provided
 * 2. Uses the provided demo starter when one is passed
 * 3. Resets the wizard store after successful creation
 * 4. Navigates to the novel editor on success
 * 5. Resets isQuickStarting to false on error
 */

import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ---------------------------------------------------------------------------
// Mocks (hoisted so they exist before the hook module imports them)
// ---------------------------------------------------------------------------

const { mockPush, mockComplete, mockReset, mockRequestFeatureTour } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockComplete: vi.fn(),
  mockReset: vi.fn(),
  mockRequestFeatureTour: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api/client", () => ({
  setupApi: { complete: mockComplete },
}));

vi.mock("@/components/ui/feature-tour", () => ({
  requestFeatureTour: mockRequestFeatureTour,
}));

vi.mock("@/lib/stores/wizardStore", () => ({
  useWizardStore: vi.fn((selector?: (s: { reset: typeof mockReset }) => unknown) => {
    const state = { reset: mockReset };
    return selector ? selector(state) : state;
  }),
}));

import { useQuickStart } from "@/lib/hooks/useQuickStart";
import type { WizardState } from "@/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolveComplete(novelId = "novel-123"): void {
  mockComplete.mockResolvedValueOnce({
    novel_id: novelId,
    redirect_to: "/dashboard",
    message: "ok",
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useQuickStart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('defaults to "blank" starter when no starter is provided', async () => {
    resolveComplete();

    const { result } = renderHook(() => useQuickStart());

    await result.current.handleQuickStart("Mein Roman");

    await waitFor(() => {
      expect(mockComplete).toHaveBeenCalled();
    });

    const sentState = mockComplete.mock.calls[0]?.[0] as WizardState;
    expect(sentState.starter).toBe("blank");
  });

  it("uses the provided demo starter when one is passed", async () => {
    resolveComplete();

    const { result } = renderHook(() => useQuickStart());

    await result.current.handleQuickStart("Demo Roman", "demo_fantasy");

    await waitFor(() => {
      expect(mockComplete).toHaveBeenCalled();
    });

    const sentState = mockComplete.mock.calls[0]?.[0] as WizardState;
    expect(sentState.starter).toBe("demo_fantasy");
    expect(sentState.project_name).toBe("Demo Roman");
  });

  it("resets the wizard store after successful creation", async () => {
    resolveComplete();

    const { result } = renderHook(() => useQuickStart());

    await result.current.handleQuickStart("Mein Roman");

    await waitFor(() => {
      expect(mockReset).toHaveBeenCalled();
    });
  });

  it("navigates to the novel editor on success", async () => {
    resolveComplete("novel-abc");

    const { result } = renderHook(() => useQuickStart());

    await result.current.handleQuickStart("Mein Roman");

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/novel/novel-abc");
    });
  });

  it("resets isQuickStarting to false on error", async () => {
    mockComplete.mockRejectedValueOnce(new Error("boom"));

    const { result } = renderHook(() => useQuickStart());

    expect(result.current.isQuickStarting).toBe(false);

    await result.current.handleQuickStart("Mein Roman");

    await waitFor(() => {
      expect(result.current.isQuickStarting).toBe(false);
    });
  });
});
