"use client";

/**
 * TanStack Query hooks for the Series Join flow (preview-then-apply).
 *
 * Policy α (see series service + spec): joining a novel to a series is a
 * two-step UI flow —
 *   1. `useJoinPreview` → POST /series/{id}/novels returns a `JoinPreview`
 *      (per-entry treatment list) WITHOUT mutating. The UI renders a dialog.
 *   2. `useApplyJoin`   → POST /series/{id}/novels/{novelId}/apply executes
 *      the join and returns a `JoinResult`; on success it invalidates the
 *      Series detail + list so the new member/counts refresh.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import { seriesKeys } from "./seriesKeys";

/**
 * Preview joining a novel to a Series (non-mutating).
 * Call `.mutate(novelId)` / `.mutateAsync(novelId)`.
 */
export function useJoinPreview(seriesId: string) {
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.previewJoin(seriesId, novelId),
  });
}

/**
 * Apply the join (mutating). Call `.mutate({ novelId, position })`.
 * `position` is the 1-based slot in the series.
 */
export function useApplyJoin(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ novelId, position }: { novelId: string; position: number }) =>
      seriesApi.applyJoin(seriesId, novelId, position),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.detail(seriesId) });
      void queryClient.invalidateQueries({ queryKey: seriesKeys.all });
    },
  });
}
