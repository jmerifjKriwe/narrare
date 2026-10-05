"use client";

/**
 * useBulkReviewWalk — review-walking state for the bulk review mode (F2 T7,
 * spec §8.2): applied/skipped marks are keyed by chapter id and kept across
 * a resume; a restart (new job) starts with a clean slate via `reset()`.
 *
 * Extracted from BulkExtractionPanel (RULE-04): the pure walking helpers
 * live in {@link ./bulkReviewWalk}, this hook owns the walking STATE.
 *
 * @module useBulkReviewWalk
 */

import { type Dispatch, type SetStateAction, useState } from "react";
import type { BulkChapterStatusView } from "@/lib/api/bulkExtraction";
import { isUnreviewedDone, nextUnreviewedAfter } from "./bulkReviewWalk";

export function useBulkReviewWalk(chapters: readonly BulkChapterStatusView[]) {
  const [appliedIds, setAppliedIds] = useState<ReadonlySet<string>>(() => new Set());
  const [skippedIds, setSkippedIds] = useState<ReadonlySet<string>>(() => new Set());
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null);

  const unreviewedDone = chapters.filter((c) => isUnreviewedDone(c, appliedIds, skippedIds));
  const activeChapter =
    chapters.find((c) => c.chapter_id === activeChapterId) ?? unreviewedDone[0] ?? null;
  const nextChapter =
    activeChapter !== null
      ? nextUnreviewedAfter(chapters, activeChapter, appliedIds, skippedIds)
      : null;

  const markReviewed =
    (setter: Dispatch<SetStateAction<ReadonlySet<string>>>) => (chapterId: string) =>
      setter((prev) => new Set(prev).add(chapterId));

  /** Restart (new job): marks and walking state start clean. */
  const reset = () => {
    setAppliedIds(new Set());
    setSkippedIds(new Set());
    setActiveChapterId(null);
  };

  return {
    appliedIds,
    skippedIds,
    activeChapter,
    nextChapter,
    unreviewedDone,
    setActiveChapterId,
    markApplied: markReviewed(setAppliedIds),
    markSkipped: markReviewed(setSkippedIds),
    reset,
  };
}
