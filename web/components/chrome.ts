/**
 * The chrome's one read of the library (W4 Task 10): the rail's switcher
 * and the topbar's breadcrumb/word chip answer the same question from the
 * same cached list — one ask, one active book, never a disagreement.
 *
 * The active book is route-aware: on the shelf it is the latest-edited
 * unarchived novel (the hero's rule, `activeNovelFallback`); on a workspace
 * route (`/novels/$id`, Task 11) it is the route's own book. Until the
 * workspace route lands, only the shelf face is live — the book face is
 * structurally ready, and its resolution already reads the param.
 */
import { useRouterState } from "@tanstack/react-router";

import { activeNovelFallback, useNovelsQuery } from "../lib/query";
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
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const bookId = pathname.startsWith("/novels/") ? (pathname.split("/")[2] ?? null) : null;
  const rows = novels.data ?? [];
  const active =
    bookId !== null
      ? (rows.find((novel) => novel.id === bookId) ?? null)
      : activeNovelFallback(rows);
  return { novels, active, bookId };
}
