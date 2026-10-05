"use client";

/**
 * useBulkExtraction — job lifecycle hook for bulk KB extraction (F2, ADR-092).
 *
 * Composer facade: owns one bulk job per mount and wires three single-
 * responsibility modules (RULE-04/06) —
 *
 * - `useBulkExtractionJobState`: job identity, status view, and every
 *   lifecycle transition (`start`/`adopt`/`cancel`/`resume`/`reset`).
 *   Resume bumps the job epoch, which restarts the poll loop on the SAME
 *   job id (start would create a new job — spec §4.5).
 * - `useDedupPendingGrace`: the bounded post-pass dedup pending window
 *   (F3 fix round 1) driving the card's honest pending/unavailable copy.
 * - `useBulkExtractionPoll`: the interval poll loop (scheduling policy in
 *   `bulkExtractionPollPolicy`).
 *
 * Interrupted degrade (spec §8.2): a 404 poll (job lost to a server restart
 * or foreign/unknown id) flips `isInterrupted`, halts the loop, and
 * `isActive` goes false — recover via a new `start()`. `reset()` halts
 * polling deliberately and clears all job state.
 *
 * Public result types live in {@link useBulkExtraction.types}.
 *
 * @module useBulkExtraction
 */

import { isTerminalJobStatus } from "@/lib/hooks/bulkExtractionPollPolicy";
import type { UseBulkExtractionResult } from "@/lib/hooks/useBulkExtraction.types";
import { useBulkExtractionJobState } from "@/lib/hooks/useBulkExtractionJobState";
import { useBulkExtractionPoll } from "@/lib/hooks/useBulkExtractionPoll";
import { useDedupPendingGrace } from "@/lib/hooks/useDedupPendingGrace";

export type { UseBulkExtractionResult } from "@/lib/hooks/useBulkExtraction.types";

export function useBulkExtraction(novelId: string): UseBulkExtractionResult {
  const { dedupPending, trackDedupPending, clearDedupPending } = useDedupPendingGrace();

  // The state machine owns every transition; the dedup pending window must
  // clear alongside each fresh/adopted-job reset (injected into the machine).
  const jobState = useBulkExtractionJobState(novelId, clearDedupPending);

  useBulkExtractionPoll(novelId, jobState.job, {
    onStatus: (view) => {
      trackDedupPending(view);
      jobState.applyStatus(view);
    },
    onPollError: jobState.applyPollError,
  });

  return {
    jobId: jobState.jobId,
    status: jobState.status,
    chapters: jobState.status?.chapters ?? [],
    totals: jobState.status?.totals ?? null,
    dedupPending,
    isStarting: jobState.isStarting,
    isActive:
      jobState.jobId !== null &&
      jobState.status !== null &&
      !isTerminalJobStatus(jobState.status.status) &&
      !jobState.isInterrupted,
    isInterrupted: jobState.isInterrupted,
    error: jobState.error,
    start: jobState.start,
    adopt: jobState.adopt,
    cancel: jobState.cancel,
    resume: jobState.resume,
    reset: jobState.reset,
  };
}
