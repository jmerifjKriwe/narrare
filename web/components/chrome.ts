/**
 * The chrome's one read of the library (W4 Task 10): the rail's switcher
 * and the topbar's breadcrumb/word chip answer the same question from the
 * same cached list — one ask, one active book, never a disagreement.
 *
 * The active book is route-aware: on the shelf it is the latest-edited
 * unarchived novel (the hero's rule, `activeNovelFallback`); on a book-scoped
 * route it is the route's own book. The book face reads the ROUTE PARAM (W4
 * Task 11 — the pathname parse is gone): any match carrying a `novelId` param
 * names its book, so the workspace, its dock children and the knowledge
 * pages (W5 Task 3's graph, parented at the root with a book-scoped path)
 * all resolve their own book without a pathname string ever being split.
 */
import { useRouterState } from "@tanstack/react-router";

import { activeNovelFallback, useNovelsQuery } from "../lib/query";
import type { Novel } from "../lib/api/client";
import type { UseQueryResult } from "@tanstack/react-query";

export interface ChromeNovels {
  novels: UseQueryResult<Novel[]>;
  active: Novel | null;
  /** The book-scoped route's book id, or null on every other surface. */
  bookId: string | null;
}

/**
 * The initials the chrome's two user blocks wear (the rail's avatar, the
 * topbar's menu tile): the first and last word's initial of the author
 * name, or of the email's local part — „H. Calder" and „h.calder@…" both
 * read HC. No source, no initials (the person glyph answers). One
 * definition here, because two faces rendering different initials for one
 * row would be a lie one of them tells.
 */
export function initialsFrom(source: string | null): string | null {
  if (source === null) return null;
  const words = source.trim().split(/[\s._-]+/).filter((word) => word.length > 0);
  if (words.length === 0) return null;
  const first = Array.from(words[0].toUpperCase())[0] ?? "";
  const last = words.length > 1 ? (Array.from(words[words.length - 1].toUpperCase())[0] ?? "") : "";
  return first + last || null;
}

export function useChromeNovels(): ChromeNovels {
  const novels = useNovelsQuery();
  const bookId = useRouterState({
    select: (state) => {
      // The first match whose own params carry a non-empty novelId is the
      // book the surface stands on. The workspace route and its dock
      // children carry the same id; a root-parented knowledge page carries
      // its own. The cast is guarded by the typeof check — only a non-empty
      // string novelId is ever read.
      for (const match of state.matches) {
        const value = (match.params as Record<string, unknown> | undefined)?.novelId;
        if (typeof value === "string" && value !== "") return value;
      }
      return null;
    },
  });
  const rows = novels.data ?? [];
  const active =
    bookId !== null
      ? (rows.find((novel) => novel.id === bookId) ?? null)
      : activeNovelFallback(rows);
  return { novels, active, bookId };
}
