/**
 * The chrome's one read of the library (W4 Task 10): the rail's switcher
 * and the topbar's breadcrumb/word chip answer the same question from the
 * same cached list — one ask, one active book, never a disagreement.
 *
 * The active book is route-aware: on the shelf it is the latest-edited
 * unarchived novel (the hero's rule, `activeNovelFallback`); on the
 * workspace route it is the route's own book. The workspace face reads the
 * ROUTE PARAM (W4 Task 11 — the pathname parse is gone): the generated
 * leaf names the workspace route's id, the router's matches carry its
 * params, and a navigation between two books re-resolves without a
 * pathname string ever being split.
 */
import { useRouterState } from "@tanstack/react-router";

import { activeNovelFallback, useNovelsQuery } from "../lib/query";
import { workspaceRouteId } from "../lib/generated/workspace";
import type { Novel } from "../lib/api/client";
import type { UseQueryResult } from "@tanstack/react-query";

export interface ChromeNovels {
  novels: UseQueryResult<Novel[]>;
  active: Novel | null;
  /** The workspace route's book id, or null on every other surface. */
  bookId: string | null;
}

export function useChromeNovels(): ChromeNovels {
  const novels = useNovelsQuery();
  const bookId = useRouterState({
    select: (state) => {
      if (workspaceRouteId === null) return null;
      const match = state.matches.find((candidate) => candidate.routeId === workspaceRouteId);
      // The match's params are the route's own; the cast is guarded by the
      // route-id comparison above — only the workspace route's novelId is
      // ever read, and only as a non-empty string.
      const value = (match?.params as Record<string, unknown> | undefined)?.novelId;
      return typeof value === "string" && value !== "" ? value : null;
    },
  });
  const rows = novels.data ?? [];
  const active =
    bookId !== null
      ? (rows.find((novel) => novel.id === bookId) ?? null)
      : activeNovelFallback(rows);
  return { novels, active, bookId };
}
