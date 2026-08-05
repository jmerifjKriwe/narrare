/**
 * TanStack Query keys for the Series domain.
 *
 * Centralized (mirrors `@/lib/hooks/kbKeys.ts`) so invalidations across hooks
 * stay consistent. Key shape:
 *   ["series"]                          — list + wildcard prefix
 *   ["series", seriesId]                — single series detail (prefix)
 *   ["series", seriesId, "novels"]      — novels-in-series list
 *   ["series", seriesId, "settings"]    — series settings
 *   ["series", seriesId, "kb"]          — Series-Canon KB list (Slice 5)
 *   ["series", seriesId, "kb", entryId] — single Series-Canon KB entry
 *   ["series", seriesId, "novels", novelId, "bandSummary"] — band summary (Spec 2)
 *   ["series", seriesId, "voice"]                     — series voice (Spec 3)
 *   ["novel-series", novelId]           — resolved Series for a novel (useNovelSeries)
 */

export const seriesKeys = {
  all: ["series"] as const,
  detail: (seriesId: string) => ["series", seriesId] as const,
  novels: (seriesId: string) => [...seriesKeys.detail(seriesId), "novels"] as const,
  settings: (seriesId: string) => [...seriesKeys.detail(seriesId), "settings"] as const,
  /** Series-Canon KB list (mirrors the `["kb", novelId, "entries"]` novel key). */
  canonList: (seriesId: string) => [...seriesKeys.detail(seriesId), "kb"] as const,
  /** Single Series-Canon KB entry detail. */
  canonDetail: (seriesId: string, entryId: string) =>
    [...seriesKeys.canonList(seriesId), entryId] as const,
  /** Band summary for one novel in the series (Spec 2). */
  bandSummary: (seriesId: string, novelId: string) =>
    [...seriesKeys.novels(seriesId), novelId, "bandSummary"] as const,
  /** Series voice profile — the Delta-model foundation (Spec 3). */
  voice: (seriesId: string) => [...seriesKeys.detail(seriesId), "voice"] as const,
  novelSeries: (novelId: string) => ["novel-series", novelId] as const,
};
