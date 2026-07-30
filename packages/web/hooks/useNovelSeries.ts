"use client";

/**
 * Resolves the Series a novel belongs to, or `null` if the novel is standalone.
 *
 * Orchestrates `novelsApi.get` (read the novel's `series_id`) then
 * `seriesApi.get` when one is set. Used by: ScopeToggle (Slice 5),
 * SeriesCard context, and the Bände list.
 *
 * NOTE (contract gap — see task-4-2-3 report §Concerns): the backend
 * `NovelResponse` schema (apps/api/narrare/novels/schemas.py) does not yet
 * expose `series_id`, although the DB column exists (migration 0037) and the
 * frontend `Novel` type carries the field. Until the backend exposes it, this
 * hook resolves every novel to `null` at runtime. The hook itself is correct
 * for the intended contract.
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
