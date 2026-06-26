/**
 * NameGenerator lifecycle test — exercises the REAL useAIOperation hook.
 *
 * Unlike NameGenerator.test.tsx (which mocks useAIOperation), this file lets
 * the real hook run so it catches lifecycle bugs in the component/hook
 * integration. The companion suite cannot see such bugs because a mocked
 * hook returns a stable object that never triggers effect cleanups.
 *
 * Regression target: the unmount-cleanup effect must depend on the STABLE
 * `aiOp.cancel` reference, not on `aiOp` itself. `aiOp` is a fresh memo on
 * every state transition (idle → loading → complete), so a `[aiOp]`
 * dependency re-runs the cleanup on each transition and calls `cancel()`,
 * which bumps the operation's id. The in-flight `execute()` then resolves
 * against a stale id and `onSuccess` is skipped (ai-operation-execute.ts
 * guards `operationId !== operationIdRef.current`) — the operation never
 * completes and results never appear.
 *
 * Mirrors the approach in CharacterArcPanel.test.tsx (deferred-promise
 * pattern + real hook).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Deferred-promise handle so we can resolve the in-flight operation on demand.
let resolveGenerate: (value: unknown) => void;

vi.mock("@/lib/api/client", () => ({
  novelsApi: {
    get: vi.fn().mockResolvedValue({
      id: "novel-1",
      title: "Test Novel",
      writing_language: "en",
    }),
  },
  generationApi: {
    generateNames: vi.fn(
      () =>
        new Promise((resolve) => {
          resolveGenerate = resolve;
        }),
    ),
  },
}));

vi.mock("@/components/studio/generation/NameResults", () => ({
  NameResults: ({
    results,
    isLoading,
  }: {
    results: { count: number } | null;
    isLoading: boolean;
  }) => (
    <div data-testid="name-results">
      {isLoading ? "Loading..." : results ? `${results.count} results` : "No results"}
    </div>
  ),
}));

import { NameGenerator } from "@/components/studio/generation/NameGenerator";
import { generationApi } from "@/lib/api/client";

const MOCK_NAME_RESPONSE = {
  names: [
    {
      name: "Aelindra",
      type: "character",
      name_style: "Fantasy",
      pronunciation: "ay-LIN-dra",
      meaning: "Star light",
      is_duplicate: false,
      confidence: 0.95,
    },
  ],
  count: 1,
  name_style: "Fantasy",
  name_type: "character",
};

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

async function waitForFormReady() {
  await waitFor(() => {
    expect(screen.getByText("generation.generateNames")).toBeDefined();
  });
}

describe("NameGenerator lifecycle (real useAIOperation)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("completes a full generate → loading → results cycle (cleanup must not cancel on state transition)", async () => {
    renderWithProviders(<NameGenerator novelId="novel-1" />);
    await waitForFormReady();

    // Kick off a generation. handleGenerate sets requestRef then calls start().
    await act(async () => {
      fireEvent.click(screen.getByText("generation.generateNames"));
    });

    // The API was invoked once with the novel id + a name request.
    await waitFor(() => {
      expect(generationApi.generateNames).toHaveBeenCalledTimes(1);
    });
    expect(
      (generationApi.generateNames as ReturnType<typeof vi.fn>).mock.calls[0][0],
    ).toMatchObject({ project_id: "novel-1", name_type: "character" });

    // The button reflects the pending state ("generating").
    await waitFor(() => {
      expect(screen.getByText("generating")).toBeDefined();
    });

    // Resolve the in-flight operation.
    await act(async () => {
      resolveGenerate(MOCK_NAME_RESPONSE);
    });

    // Results render — proving the operation completed. With the buggy
    // `[aiOp]` cleanup dependency, cancel() fires on the idle→loading
    // transition, bumps the operation id, and onSuccess is skipped — so this
    // assertion fails and the results read "No results".
    await waitFor(() => {
      expect(screen.getByTestId("name-results").textContent).toBe("1 results");
    });
  });
});
