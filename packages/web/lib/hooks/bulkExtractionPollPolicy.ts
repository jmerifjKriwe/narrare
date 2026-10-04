/**
 * Pure scheduling policy for the bulk extraction poll loop (F2/F3, ADR-092).
 * Extracted from `useBulkExtractionPoll` (RULE-04 hook size limit): the
 * constants, classifications, and the per-poll stop decision live here —
 * no React, no I/O, fully unit-testable. The poll loop owns *when* to run
 * this policy; the lifecycle hook owns *what* happens with the results.
 *
 * @module bulkExtractionPollPolicy
 */

import {
  BulkExtractionApiError,
  type BulkExtractionStatusView,
  type BulkJobStatus,
} from "@/lib/api/bulkExtraction";

/** Poll cadence while a bulk job is active (spec §8.2 poll cadence). */
export const BULK_EXTRACTION_POLL_INTERVAL_MS = 3000;

/**
 * Grace window (F3 fix round 1) AFTER a `completed` poll during which the
 * loop KEEPS POLLING while the post-pass dedup analysis is still pending:
 * the runner marks the job completed BEFORE the ADR-085 analysis lands, and
 * the wire cannot distinguish "pending" from "failed" (both are
 * `{analyzed: false, suggestion_count: null}`). Once the window expires the
 * loop stops and the dedup card's unavailable copy is honest. Must stay in
 * sync with the card's pending/unavailable copy decision
 * (`useDedupPendingGrace` → `dedupPending`).
 */
export const DEDUP_PENDING_GRACE_MS = 60_000;

const TERMINAL_JOB_STATUSES: readonly BulkJobStatus[] = [
  "completed",
  "cancelled",
  "failed",
] as const;

/** Terminal job statuses — polling stops once one is observed. */
export function isTerminalJobStatus(status: BulkJobStatus): boolean {
  return TERMINAL_JOB_STATUSES.includes(status);
}

/**
 * A 404 poll error means the job is GONE (registry lost to a restart, or a
 * foreign/unknown id) — interrupted per spec §8.2. Single classification
 * for the loop's halt decision AND the owner's interrupted flag.
 */
export function isLostJobPollError(err: unknown): boolean {
  return err instanceof BulkExtractionApiError && err.status === 404;
}

/**
 * A `completed` corpus job whose dedup block is still unanalyzed: the
 * post-pass dedup analysis may still be running (the wire cannot tell
 * pending from failed). Shared by the poll loop's stop decision and the
 * owner's dedup-pending window (`useDedupPendingGrace`) so the two can
 * never drift apart.
 */
export function isCompletedWithPendingDedup(view: BulkExtractionStatusView): boolean {
  return view.status === "completed" && view.dedup !== null && !view.dedup.analyzed;
}

/** Per-poll stop decision, stateful across the polls of ONE loop run. */
export interface PollStopDecider {
  /**
   * Stop decision per poll (F3 fix round 1): terminal statuses stop the
   * loop — EXCEPT `completed` whose dedup block is still unanalyzed, which
   * keeps polling until the grace bound expires (the analysis may still be
   * running; the wire cannot tell pending from failed). The bound is
   * measured from the FIRST completed-with-pending poll.
   */
  shouldStopAfter(view: BulkExtractionStatusView): boolean;
}

export function createPollStopDecider(): PollStopDecider {
  // First-seen timestamp of the completed-with-pending-dedup window (the
  // grace bound is measured from when `completed` was FIRST observed).
  let dedupPendingSince: number | null = null;
  return {
    shouldStopAfter(view: BulkExtractionStatusView): boolean {
      if (!isTerminalJobStatus(view.status)) {
        dedupPendingSince = null;
        return false;
      }
      if (!isCompletedWithPendingDedup(view)) {
        dedupPendingSince = null;
        return true;
      }
      const now = Date.now();
      if (dedupPendingSince === null) dedupPendingSince = now;
      if (now - dedupPendingSince >= DEDUP_PENDING_GRACE_MS) {
        dedupPendingSince = null;
        return true;
      }
      return false;
    },
  };
}
