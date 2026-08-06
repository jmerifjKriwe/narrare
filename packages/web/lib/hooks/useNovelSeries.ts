"use client";

/**
 * Resolves the Series a novel belongs to, or `null` if the novel is standalone.
 *
 * Orchestrates `novelsApi.get` (read the novel's `series_id`) then
 * `seriesApi.get` when one is set. Used by: ScopeToggle (Slice 5),
 * SeriesCard context, and the Bände list.
 *
 * The backend exposes `series_id` on both `NovelResponse` and
 * `NovelSummaryResponse` (apps/api/narrare/novels/schemas.py), so this resolves
 * the real membership at runtime — `null` for a standalone novel.
 */

import { useQuery } from "@tanstack/react-query";
import { novelsApi } from "@/lib/api/novels";
import { seriesApi } from "@/lib/api/series";
import type { Series } from "@/types";
import { seriesKeys } from "./seriesKeys";

export function useNovelSeries(novelId: string | undefined) {
  return useQuery<Series | null>({
    queryKey: seriesKeys.novelSeries(novelId ?? ""),
    queryFn: async (): Promise<Series | null> => {
      if (!novelId) return null;
      const novel = await novelsApi.get(novelId);
      if (!novel.series_id) return null;
      return seriesApi.get(novel.series_id);
    },
    enabled: !!novelId,
  });
}
