/**
 * useAIRating hook tests (CR-AUFG-07-24).
 *
 * Verifies the idle → loading → success | error | skipped state machine and
 * that rating failures are non-blocking (the original AI output is unaffected;
 * the host decides whether to surface error/retry).
 *
 * Test strategy: the hook wraps the real `useRecordFeedback` TanStack
 * mutation, which calls the real `memoryApi.recordFeedback` → `fetchApi`
 * → MSW. We use the project's shared MSW `server` (from `@/mocks/server`) —
 * the same pattern as `lib/api/__tests__/memory.test.ts` — and override the
 * feedback handler per-test via `server.use(...)`.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { AIRatingViewModel } from "@/lib/ai-rating/contracts";
import { setAccessToken } from "@/lib/api/core";
import { useAIRating } from "@/lib/hooks/useAIRating";
import { server } from "@/mocks/server";

const vm: AIRatingViewModel = {
  sourceType: "kb_enhance_field",
  sourceId: "field-role",
  projectId: "proj-1",
  intent: "kb_enhance",
  suggestionText: "Wise mentor",
  action: "accept",
  chapterId: null,
  genre: null,
  mode: null,
};

const FEEDBACK_URL = "*/api/v1/memory/feedback";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => {
  // Access token avoids the 401-refresh redirect path inside fetchApi.
  setAccessToken("test-access-token");
});

afterEach(() => {
  cleanup();
});

describe("useAIRating", () => {
  it("starts in idle state and exposes submit + skip + reset", () => {
    const { result } = renderHook(() => useAIRating(vm), { wrapper: createWrapper() });
    expect(result.current.state).toBe("idle");
    expect(typeof result.current.submit).toBe("function");
    expect(typeof result.current.skip).toBe("function");
    expect(typeof result.current.reset).toBe("function");
  });

  it("transitions idle → loading → success on a successful POST", async () => {
    server.use(
      http.post(FEEDBACK_URL, () =>
        HttpResponse.json({ id: "evt-1", action: "accept", created_at: "2026-06-22T00:00:00Z" }),
      ),
    );

    const { result } = renderHook(() => useAIRating(vm), { wrapper: createWrapper() });
    act(() => {
      result.current.submit({ rating: 5 });
    });
    expect(result.current.state).toBe("loading");
    await waitFor(() => expect(result.current.state).toBe("success"));
  });

  it("skip() transitions to skipped without firing the POST", () => {
    const { result } = renderHook(() => useAIRating(vm), { wrapper: createWrapper() });
    act(() => result.current.skip());
    expect(result.current.state).toBe("skipped");
  });

  it("reset() returns to idle from a terminal state", () => {
    const { result } = renderHook(() => useAIRating(vm), { wrapper: createWrapper() });
    act(() => result.current.skip());
    expect(result.current.state).toBe("skipped");
    act(() => result.current.reset());
    expect(result.current.state).toBe("idle");
  });

  it("transitions to error on a failed POST (non-blocking)", async () => {
    server.use(
      http.post(FEEDBACK_URL, () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );

    const { result } = renderHook(() => useAIRating(vm), { wrapper: createWrapper() });
    act(() => result.current.submit({ rating: 3 }));
    await waitFor(() => expect(result.current.state).toBe("error"));
  });

  it("can retry after an error by resetting and submitting again", async () => {
    // First attempt fails
    server.use(
      http.post(FEEDBACK_URL, () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    const { result } = renderHook(() => useAIRating(vm), { wrapper: createWrapper() });
    act(() => result.current.submit({ rating: 2 }));
    await waitFor(() => expect(result.current.state).toBe("error"));

    // Reset and retry succeeds
    server.use(
      http.post(FEEDBACK_URL, () =>
        HttpResponse.json({ id: "evt-2", action: "accept", created_at: "2026-06-22T00:00:00Z" }),
      ),
    );
    act(() => result.current.reset());
    expect(result.current.state).toBe("idle");
    act(() => result.current.submit({ rating: 4 }));
    await waitFor(() => expect(result.current.state).toBe("success"));
  });
});
