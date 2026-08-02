"use client";

/**
 * TanStack Query hooks for novels-in-a-Series (the "Bände" list + reorder).
 *
 * Series Foundation Spec 1, Slice 4. Mirrors the established Narrare pattern
 * (`useCanonKB`, `useSeries`): reads use `useQuery` (disabled when `seriesId`
 * is empty); mutations use `useMutation` and invalidate the novels-in-series
 * cache via `seriesKeys`. Components import these — never `seriesApi` directly
 * (I-F6 convention fix).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import { seriesKeys } from "./seriesKeys";

/**
 * GET /api/v1/series/{id}/novels — ordered by `series_position`.
 * Disabled when `seriesId` is empty.
 */
export function useSeriesNovels(seriesId: string) {
  return useQuery({
    queryKey: seriesKeys.novels(seriesId),
    queryFn: () => seriesApi.listNovels(seriesId),
    enabled: !!seriesId,
  });
}

/**
 * PATCH /api/v1/series/{id}/novels/reorder — full ordered id list (204).
 * Invalidates the novels-in-series cache on success.
 *
 * Call `.mutate(novelIds)`.
 */
export function useReorderNovels(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (novelIds: string[]) => seriesApi.reorderNovels(seriesId, novelIds),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.novels(seriesId) });
    },
  });
}
