"use client";

/**
 * KB scope-toggle hooks — promote/demote between Series-Canon and Novel-Overlay.
 *
 * Series Foundation Spec 1, Slice 5 (Task 5.1).
 *
 * usePromoteToCanon: POST /novels/{novelId}/kb/{entryId}/promote → SeriesKBEntry.
 *   On success invalidates the novel's KB entries AND the series Canon-KB list
 *   (``series_id`` taken from the response — the overlay's home novel may not
 *   know its series id client-side).
 * useDemoteToOverlay: POST /novels/{novelId}/kb/{entryId}/demote with body
 *   {series_id} → NovelKBEntry. The path ``novelId`` is the overlay target.
 *   On success invalidates the Canon-KB list (``seriesId`` captured at hook
 *   construction) AND the target novel's KB entries (``novel_id`` taken from
 *   the response).
 *
 * Mirrors the useSeries / useKB mutation conventions (real
 * ``queryClient.invalidateQueries`` calls via centralized key factories).
 * Components import these — never ``seriesApi`` directly.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import { kbKeys } from "./kbKeys";
import { seriesKeys } from "./seriesKeys";

/** Arguments for {@link useDemoteToOverlay} — the routing novel id. */
export interface DemoteToOverlayArgs {
  /**
   * Novel used as the URL routing anchor for the demote endpoint. The path
   * novel IS the overlay target (mirrors the promote endpoint).
   */
  novelId: string;
}

/**
 * Promote a Novel-Overlay entry to Series-Canon.
 *
 * Invalidates the overlay's home-novel KB entries and the series Canon-KB list.
 */
export function usePromoteToCanon(novelId: string, entryId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => seriesApi.promoteToCanon(novelId, entryId),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: kbKeys.entries(novelId) });
      void queryClient.invalidateQueries({ queryKey: seriesKeys.canonList(data.series_id) });
    },
  });
}

/**
 * Demote a Series-Canon entry to a Novel-Overlay for the path novel.
 *
 * ``seriesId``/``entryId`` are captured at hook construction; ``novelId`` (the
 * routing anchor, which is also the overlay target) is passed to each ``mutate``
 * call. Invalidates the Canon-KB list (by captured ``seriesId``) and the target
 * novel's KB entries (by response ``novel_id``).
 */
export function useDemoteToOverlay(seriesId: string, entryId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ novelId }: DemoteToOverlayArgs) =>
      seriesApi.demoteToOverlay(novelId, entryId, seriesId),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.canonList(seriesId) });
      void queryClient.invalidateQueries({ queryKey: kbKeys.entries(data.novel_id) });
    },
  });
}
