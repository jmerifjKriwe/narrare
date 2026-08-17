"use client";

/**
 * TanStack Query hooks for the Series Cross-Novel Drift checks (Spec 4 Task 4
 * + Slice 6 / C2 persistence).
 *
 * Three hooks back the drift surface for one series:
 *
 * - ``useSeriesConsistency``  — POST check a band's chapter prose vs the series
 *   Canon KB (returns the canon contradictions found, possibly empty).
 * - ``useSeriesVoiceDrift``   — POST analyse a band's narrator drift against the
 *   series voice baseline (reuses the novel-level response shape).
 * - ``useSeriesDriftSnapshot`` — GET the persisted latest-wins snapshot for the
 *   selected band (C2): both results as one document + the server-computed
 *   stale flag. Nothing persisted → a 200 with an all-null body (never an
 *   error state), so the panel shows the empty state.
 *
 * Since C2 the two run mutations PERSIST their result server-side; each
 * invalidates the per-band snapshot query on success so the panel refetches
 * the saved state (mirrors ``useBandSummary``'s invalidation pattern).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import { seriesKeys } from "./seriesKeys";

/**
 * POST /api/v1/series/{id}/consistency/check.
 * Call `.mutate(novelId)`; the result lands in `.data` (a graceful empty
 * `conflicts` list means no contradictions were found).
 */
export function useSeriesConsistency(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.checkSeriesConsistency(seriesId, novelId),
    onSuccess: (_data, novelId) => {
      void queryClient.invalidateQueries({
        queryKey: seriesKeys.driftSnapshot(seriesId, novelId),
      });
    },
  });
}

/**
 * POST /api/v1/series/{id}/voice-drift/check.
 * Call `.mutate(novelId)`; the result lands in `.data` (exactly one of
 * `result` / `no_profile` is set — `no_profile` is the RULE-11 graceful skip).
 */
export function useSeriesVoiceDrift(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.checkSeriesVoiceDrift(seriesId, novelId),
    onSuccess: (_data, novelId) => {
      void queryClient.invalidateQueries({
        queryKey: seriesKeys.driftSnapshot(seriesId, novelId),
      });
    },
  });
}

/**
 * GET /api/v1/series/{id}/consistency/{novelId} — the persisted drift
 * snapshot (C2). Disabled until a band is selected. Refetches automatically
 * when the band changes (the novelId is part of the query key).
 */
export function useSeriesDriftSnapshot(seriesId: string, novelId: string) {
  return useQuery({
    queryKey: seriesKeys.driftSnapshot(seriesId, novelId),
    queryFn: () => seriesApi.getDriftSnapshot(seriesId, novelId),
    enabled: !!seriesId && !!novelId,
  });
}
