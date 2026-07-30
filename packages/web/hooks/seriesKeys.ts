/**
 * TanStack Query keys for the Series domain.
 *
 * Centralized (mirrors `@/lib/hooks/kbKeys.ts`) so invalidations across hooks
 * stay consistent. Key shape:
 *   ["series"]                       — list + wildcard prefix
 *   ["series", seriesId]             — single series detail (prefix for novels/settings)
 *   ["series", seriesId, "novels"]   — novels-in-series list
 *   ["series", seriesId, "settings"] — series settings
 *   ["novel-series", novelId]        — resolved Series for a novel (useNovelSeries)
 */

export const seriesKeys = {
  all: ["series"] as const,
  detail: (seriesId: string) => ["series", seriesId] as const,
  novels: (seriesId: string) => [...seriesKeys.detail(seriesId), "novels"] as const,
  settings: (seriesId: string) => [...seriesKeys.detail(seriesId), "settings"] as const,
  novelSeries: (novelId: string) => ["novel-series", novelId] as const,
};
