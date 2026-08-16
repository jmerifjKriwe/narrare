"use client";

/**
 * TanStack Query hooks for band summaries (Spec 2 — Series Generation Context).
 *
 * Four hooks back the band-summary lifecycle for one novel in a series:
 *
 * - ``useBandSummary``                       — GET (read; disabled while loading).
 * - ``useGenerateBandSummary``               — POST (re)generate.
 * - ``useUpdateBandSummaryOverride``         — PATCH set the user override.
 * - ``useClearBandSummaryOverride``          — DELETE clear the override.
 *
 * The three mutations invalidate the per-novel band-summary query on success so
 * the ``BandSummaryCard`` re-fetches immediately, plus the C1 settings-preview
 * query (which derives its preview from summaries, so it goes stale on edit).
 * Mirrors the established Narrare pattern (``useSeriesNovels``): reads use
 * ``useQuery`` (disabled when ``seriesId`` is empty); mutations use
 * ``useMutation`` + ``seriesKeys``.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import { seriesKeys } from "./seriesKeys";

/**
 * GET /api/v1/series/{id}/novels/{novelId}/band-summary.
 * Disabled when `seriesId` is empty.
 */
export function useBandSummary(seriesId: string, novelId: string) {
  return useQuery({
    queryKey: seriesKeys.bandSummary(seriesId, novelId),
    queryFn: () => seriesApi.getBandSummary(seriesId, novelId),
    enabled: !!seriesId && !!novelId,
  });
}

/** POST /api/v1/series/{id}/novels/{novelId}/band-summary — (re)generate. */
export function useGenerateBandSummary(seriesId: string, novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => seriesApi.generateBandSummary(seriesId, novelId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.bandSummary(seriesId, novelId) });
      void queryClient.invalidateQueries({ queryKey: seriesKeys.settingsPreview(seriesId) });
    },
  });
}

/** PATCH /api/v1/series/{id}/novels/{novelId}/band-summary — set override. */
export function useUpdateBandSummaryOverride(seriesId: string, novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (override: string) =>
      seriesApi.updateBandSummaryOverride(seriesId, novelId, override),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.bandSummary(seriesId, novelId) });
      void queryClient.invalidateQueries({ queryKey: seriesKeys.settingsPreview(seriesId) });
    },
  });
}

/** DELETE /api/v1/series/{id}/novels/{novelId}/band-summary/override — clear. */
export function useClearBandSummaryOverride(seriesId: string, novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => seriesApi.clearBandSummaryOverride(seriesId, novelId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.bandSummary(seriesId, novelId) });
      void queryClient.invalidateQueries({ queryKey: seriesKeys.settingsPreview(seriesId) });
    },
  });
}
