"use client";

/**
 * TanStack Query hook for the monthly AI cost report (STATS-002, ADR-093).
 *
 * GET /api/v1/analytics/costs?month=YYYY-MM — one cached entry per month
 * (["analytics", "costs", month]). `placeholderData: keepPreviousData` keeps
 * the previous month's report visible while a changed month refetches — no
 * loading pulse between month switches. Response types are re-exported here
 * so the stats panel consumes a single module.
 */

import { keepPreviousData, type UseQueryResult, useQuery } from "@tanstack/react-query";
import { analyticsApi, type CostMonthReport } from "@/lib/api/analytics";

export type {
  CostIntentRow,
  CostModelRow,
  CostMonthReport,
  CostTotals,
  CostTrendPoint,
} from "@/lib/api/analytics";

/** GET /api/v1/analytics/costs?month=YYYY-MM — monthly AI cost report. */
export function useAnalyticsCosts(month: string): UseQueryResult<CostMonthReport> {
  return useQuery({
    queryKey: ["analytics", "costs", month],
    queryFn: () => analyticsApi.costs(month),
    // TanStack v5 pattern (mirrors useNotes): keep the previous month's
    // report visible while the changed key refetches.
    placeholderData: keepPreviousData,
  });
}
