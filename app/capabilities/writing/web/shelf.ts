/**
 * The shelf's pure model: which book leads, which follow, and what the
 * progress bar may honestly claim. No React, no i18n, no requests — the
 * rules the page renders, testable on their own (shelf.test.ts).
 *
 * The hero is the latest-edited unarchived novel; the grid is the rest,
 * newest first. Both compare parsed instants, because two ISO strings with
 * different timezone offsets do not order as their moments do (the
 * active-chapter fallback's rule). Strict comparison: on an exact tie the
 * first row keeps the lead, so the choice stays deterministic.
 *
 * A book without a target has no percentage and no sliver — the landing's
 * honest neutral. The bar claims only what the target measures: the label
 * floors the way the draft draws it (3.384/60.000 reads 5%), the fill keeps
 * the exact ratio, and a finished book clamps at 100 rather than overflowing.
 */

import type { Novel } from "@shell/lib/api/client";

/** The latest-edited unarchived novel, or null when the shelf holds none.
 *  Archived books never lead, even when they are the newest row. */
export function pickHero(novels: readonly Novel[]): Novel | null {
  let hero: Novel | null = null;
  for (const novel of novels) {
    if (novel.archived_at != null) continue;
    if (hero === null || Date.parse(novel.updated_at) > Date.parse(hero.updated_at)) {
      hero = novel;
    }
  }
  return hero;
}

/** The grid: every unarchived novel except the hero, newest first. Ties
 *  keep the list's order (a stable sort), so the shelf never reshuffles. */
export function shelfGrid(novels: readonly Novel[], hero: Novel | null): Novel[] {
  return novels
    .filter((novel) => novel.archived_at == null && novel.id !== hero?.id)
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
}

/** The drafted progress, or null when there is nothing to measure against.
 *  `percent` is the floored whole number the label prints; `width` is the
 *  exact clamped ratio the bar fills. A zero or negative target is no
 *  target — the row's own null is the only honest neutral. */
export function progress(
  wordCount: number,
  targetWords: number | null | undefined,
): { percent: number; width: number } | null {
  if (targetWords == null || targetWords <= 0) return null;
  const width = Math.min(100, Math.max(0, (wordCount / targetWords) * 100));
  return { percent: Math.floor(width), width };
}
