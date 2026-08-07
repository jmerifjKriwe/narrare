"use client";

/**
 * TanStack Query hook for the all-novels list.
 *
 * Mirrors the established Narrare pattern (`useSeries`, `useKB`): reads use
 * `useQuery`; the centralized key factory (`novelsKeys`) keeps invalidations
 * consistent. Components import this — never `novelsApi` with a literal
 * `["novels"]` query key (I-F6 convention fix).
 */

import { useQuery } from "@tanstack/react-query";
import { novelsApi } from "@/lib/api/novels";
import { novelsKeys } from "./novelsKeys";

/** GET /api/v1/novels — all novels for the current user. */
export function useNovels() {
  return useQuery({
    queryKey: novelsKeys.all,
    queryFn: () => novelsApi.list(),
  });
}
