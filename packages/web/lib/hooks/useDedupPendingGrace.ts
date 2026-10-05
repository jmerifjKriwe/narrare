"use client";

/**
 * useDedupPendingGrace — bounded post-pass dedup pending window (F3 fix
 * round 1, ADR-092/ADR-085). Extracted from `useBulkExtraction` (RULE-04
 * hook size limit): a completed corpus job whose dedup block is still
 * `{analyzed: false}` may be mid-analysis — the wire cannot tell pending
 * from failed, so the card shows a pending copy (never the false "could
 * not run") until `analyzed` flips or the same `DEDUP_PENDING_GRACE_MS`
 * bound the poll loop enforces has expired.
 *
 * @module useDedupPendingGrace
 */

import { useCallback, useRef, useState } from "react";
import type { BulkExtractionStatusView } from "@/lib/api/bulkExtraction";
import {
  DEDUP_PENDING_GRACE_MS,
  isCompletedWithPendingDedup,
} from "@/lib/hooks/bulkExtractionPollPolicy";

/** Public surface of the dedup pending window (consumed by the lifecycle hook). */
export interface DedupPendingGrace {
  /** True while completed-with-pending-dedup is inside the grace window. */
  readonly dedupPending: boolean;
  /** Feed every successful status view through here (poll `onStatus`). */
  trackDedupPending(view: BulkExtractionStatusView): void;
  /** Clear the window alongside the job state (start/adopt/reset). */
  clearDedupPending(): void;
}

export function useDedupPendingGrace(): DedupPendingGrace {
  // The ref anchors "first seen completed-with-pending" exactly like the
  // poll loop's stop decider does.
  const graceStartRef = useRef<number | null>(null);
  const [dedupPending, setDedupPending] = useState(false);

  const trackDedupPending = useCallback((view: BulkExtractionStatusView) => {
    if (!isCompletedWithPendingDedup(view)) {
      graceStartRef.current = null;
      setDedupPending(false);
      return;
    }
    if (graceStartRef.current === null) graceStartRef.current = Date.now();
    setDedupPending(Date.now() - graceStartRef.current < DEDUP_PENDING_GRACE_MS);
  }, []);

  const clearDedupPending = useCallback(() => {
    graceStartRef.current = null;
    setDedupPending(false);
  }, []);

  return { dedupPending, trackDedupPending, clearDedupPending };
}
