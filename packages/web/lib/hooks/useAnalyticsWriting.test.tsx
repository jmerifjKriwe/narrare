/**
 * useAnalyticsWriting hook tests (STATS-001) — MSW-backed read cycle.
 *
 * Conventions: centralized setupTests.ts neutralizes motion and returns
 * i18n keys; the MSW guard requires handlers for every request made.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { server } from "@/mocks/server";
import { useAnalyticsWriting } from "./useAnalyticsWriting";

const NOVEL_A = "11111111-1111-1111-1111-111111111111";
const NOVEL_B = "22222222-2222-2222-2222-222222222222";

/** Minimal valid WritingReport fixture (snake_case per backend contract). */
function makeReport(
  goal: { target_words: number; current_words: number; progress_pct: number } | null,
) {
  return {
    dailies: [
      { date: "2026-10-07", words: 0 },
      { date: "2026-10-08", words: 320 },
    ],
    streaks: { current: 3, longest: 12 },
    today_words: 320,
    total_words: 48210,
    goal,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useAnalyticsWriting", () => {
  it("fetches the writing report for a novel scope (goal block present)", async () => {
    server.use(
      http.get("*/api/v1/analytics/writing", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("novel_id")).toBe(NOVEL_A);
        return HttpResponse.json(
          makeReport({ target_words: 50000, current_words: 12345, progress_pct: 24.7 }),
        );
      }),
    );

    const { result } = renderHook(() => useAnalyticsWriting(NOVEL_A), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.dailies).toHaveLength(2);
    expect(result.current.data?.dailies[0]?.date).toBe("2026-10-07");
    expect(result.current.data?.dailies[0]?.words).toBe(0);
    expect(result.current.data?.dailies[1]?.words).toBe(320);
    expect(result.current.data?.streaks.current).toBe(3);
    expect(result.current.data?.streaks.longest).toBe(12);
    expect(result.current.data?.today_words).toBe(320);
    expect(result.current.data?.total_words).toBe(48210);
    expect(result.current.data?.goal?.target_words).toBe(50000);
    expect(result.current.data?.goal?.current_words).toBe(12345);
    expect(result.current.data?.goal?.progress_pct).toBe(24.7);
  });

  it("changes the query key with novelId and refetches the new scope", async () => {
    const requestedNovelIds: string[] = [];
    server.use(
      http.get("*/api/v1/analytics/writing", ({ request }) => {
        const novelId = new URL(request.url).searchParams.get("novel_id");
        requestedNovelIds.push(novelId ?? "all");
        return HttpResponse.json(
          makeReport(
            novelId === NOVEL_A ? { target_words: 50000, current_words: 1, progress_pct: 0 } : null,
          ),
        );
      }),
    );

    const { result, rerender } = renderHook(({ novelId }) => useAnalyticsWriting(novelId), {
      initialProps: { novelId: NOVEL_A as string | null },
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data?.goal).not.toBeNull());

    rerender({ novelId: NOVEL_B });

    // Synchronously after the key change the OLD report stays visible as
    // placeholder data — no loading pulse between novel switches.
    expect(result.current.isPlaceholderData).toBe(true);
    expect(result.current.data?.goal).not.toBeNull();

    await waitFor(() => expect(result.current.data?.goal).toBeNull());
    expect(result.current.isPlaceholderData).toBe(false);
    expect(requestedNovelIds).toContain(NOVEL_A);
    expect(requestedNovelIds).toContain(NOVEL_B);
  });

  it("omits the novel_id query param entirely when no novel is selected", async () => {
    server.use(
      http.get("*/api/v1/analytics/writing", ({ request }) => {
        const url = new URL(request.url);
        expect(url.pathname).toBe("/api/v1/analytics/writing");
        expect(url.searchParams.has("novel_id")).toBe(false);
        return HttpResponse.json(makeReport(null));
      }),
    );

    const { result } = renderHook(() => useAnalyticsWriting(null), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.goal).toBeNull();
  });
});
