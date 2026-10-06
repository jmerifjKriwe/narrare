/**
 * useAnalyticsCosts hook tests (STATS-002) — MSW-backed read cycle.
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
import { useAnalyticsCosts } from "./useAnalyticsCosts";

/** Minimal valid CostMonthReport fixture (snake_case per backend contract). */
function makeReport(month: string, costUsd: number) {
  return {
    month,
    totals: {
      calls: 12,
      tokens_in: 1000,
      tokens_out: 500,
      cost_usd: costUsd,
      unpriced_calls: 1,
    },
    by_intent: [{ intent: "summarize", calls: 7, cost_usd: costUsd / 2, unpriced_calls: 0 }],
    by_model: [
      { provider: "openai", model_id: "gpt-5", calls: 12, cost_usd: costUsd, unpriced_calls: 1 },
    ],
    trend: [
      { month: "2026-04", cost_usd: 0.5 },
      { month: "2026-05", cost_usd: 0.75 },
      { month, cost_usd: costUsd },
    ],
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

describe("useAnalyticsCosts", () => {
  it("fetches the monthly cost report for a month", async () => {
    server.use(
      http.get("*/api/v1/analytics/costs", ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("month")).toBe("2026-09");
        return HttpResponse.json(makeReport("2026-09", 1.25));
      }),
    );

    const { result } = renderHook(() => useAnalyticsCosts("2026-09"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.month).toBe("2026-09");
    expect(result.current.data?.totals.calls).toBe(12);
    expect(result.current.data?.totals.tokens_in).toBe(1000);
    expect(result.current.data?.totals.cost_usd).toBe(1.25);
    expect(result.current.data?.totals.unpriced_calls).toBe(1);
    expect(result.current.data?.by_intent[0]?.intent).toBe("summarize");
    expect(result.current.data?.by_model[0]?.model_id).toBe("gpt-5");
    expect(result.current.data?.trend.at(-1)?.month).toBe("2026-09");
  });

  it("refetches when the month changes", async () => {
    const requestedMonths: string[] = [];
    server.use(
      http.get("*/api/v1/analytics/costs", ({ request }) => {
        const month = new URL(request.url).searchParams.get("month") ?? "";
        requestedMonths.push(month);
        return HttpResponse.json(makeReport(month, month === "2026-09" ? 1.25 : 3.5));
      }),
    );

    const { result, rerender } = renderHook(({ month }) => useAnalyticsCosts(month), {
      initialProps: { month: "2026-09" },
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data?.month).toBe("2026-09"));

    rerender({ month: "2026-08" });

    await waitFor(() => expect(result.current.data?.month).toBe("2026-08"));
    expect(result.current.data?.totals.cost_usd).toBe(3.5);
    expect(requestedMonths).toContain("2026-08");
  });

  it("keeps the previous report visible while the next month refetches", async () => {
    server.use(
      http.get("*/api/v1/analytics/costs", ({ request }) => {
        const month = new URL(request.url).searchParams.get("month") ?? "";
        return HttpResponse.json(makeReport(month, month === "2026-09" ? 1.25 : 3.5));
      }),
    );

    const { result, rerender } = renderHook(({ month }) => useAnalyticsCosts(month), {
      initialProps: { month: "2026-09" },
      wrapper: createWrapper(),
    });
    await waitFor(() => expect(result.current.data?.month).toBe("2026-09"));

    rerender({ month: "2026-08" });

    // Synchronously after the key change the OLD report stays visible as
    // placeholder data — no loading pulse between month switches.
    expect(result.current.isPlaceholderData).toBe(true);
    expect(result.current.data?.month).toBe("2026-09");
    await waitFor(() => expect(result.current.data?.month).toBe("2026-08"));
    expect(result.current.isPlaceholderData).toBe(false);
  });
});
