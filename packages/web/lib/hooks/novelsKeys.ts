/**
 * TanStack Query keys for the Novels domain.
 *
 * Centralized (mirrors `@/lib/hooks/seriesKeys.ts` / `kbKeys.ts`) so cross-hook
 * invalidations stay consistent. Components/hooks import these — never literal
 * `["novels"]` arrays (I-F6 convention fix).
 *
 * Key shape:
 *   ["novels"] — all-novels list + wildcard prefix
 */

export const novelsKeys = {
  all: ["novels"] as const,
};
