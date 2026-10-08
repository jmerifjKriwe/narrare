"use client";

/**
 * TanStack Query hook for the writing-activity report (STATS-001, spec E-6).
 *
 * GET /api/v1/analytics/writing?novel_id=<uuid> — one cached entry per scope
 * (["analytics", "writing", novelId ?? "all"]). `placeholderData:
 * keepPreviousData` keeps the previous scope's report visible while a novel
 * switch refetches — no loading pulse between selector changes. Response
 * types are re-exported here so the stats panel consumes a single module.
 */

import { keepPreviousData, type UseQueryResult, useQuery } from "@tanstack/react-query";
import { analyticsApi, type WritingReport } from "@/lib/api/analytics";

export type {
  DailyPoint,
  GoalBlock,
  Streaks,
  WritingReport,
} from "@/lib/api/analytics";

/**
 * GET /api/v1/analytics/writing[?novel_id=<uuid>] — writing stats report.
 * Pass a novel id to scope dailies/streaks/totals to one novel (and get the
 * goal block); omit/null for the all-novels view.
 */
export function useAnalyticsWriting(novelId?: string | null): UseQueryResult<WritingReport> {
  return useQuery({
    queryKey: ["analytics", "writing", novelId ?? "all"],
    queryFn: () => analyticsApi.writing(novelId),
    // TanStack v5 pattern (mirrors useAnalyticsCosts): keep the previous
    // scope's report visible while the changed key refetches.
    placeholderData: keepPreviousData,
  });
}
