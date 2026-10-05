/**
 * Review-walking selection logic for the bulk extraction review (F2 T7,
 * spec §8.2): which done chapters still need a review decision, and the
 * forward-only walk to the next one.
 *
 * @module bulkReviewWalk
 */

import type { BulkChapterStatusView } from "@/lib/api/bulkExtraction";

export function isUnreviewedDone(
  chapter: BulkChapterStatusView,
  applied: ReadonlySet<string>,
  skipped: ReadonlySet<string>,
): boolean {
  return (
    chapter.state === "done" && !applied.has(chapter.chapter_id) && !skipped.has(chapter.chapter_id)
  );
}

/** Next unreviewed done chapter strictly after the active one (forward-only walk). */
export function nextUnreviewedAfter(
  chapters: readonly BulkChapterStatusView[],
  active: BulkChapterStatusView,
  applied: ReadonlySet<string>,
  skipped: ReadonlySet<string>,
): BulkChapterStatusView | null {
  return (
    chapters.find((c) => isUnreviewedDone(c, applied, skipped) && c.position > active.position) ??
    null
  );
}
