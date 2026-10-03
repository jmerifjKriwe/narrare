"use client";

/**
 * useBulkExtractionPoll — interval poll loop for one bulk extraction job
 * (F2, ADR-092). Extracted from `useBulkExtraction` (RULE-04 hook size
 * limit): this module owns *when* to poll, the lifecycle hook owns *what*
 * happens with the results.
 *
 * Scheduling contract:
 *
 * - polling begins as soon as a job is adopted (no wait for the first
 *   cadence),
 * - polls never overlap — a cadence tick is skipped while a status request
 *   is still in flight,
 * - polling stops on terminal job statuses (completed | cancelled | failed)
 *   and keeps running through `cancelling` (the cooperative cancel is only
 *   observed via polling, spec §4.4),
 * - the interval is cleared on unmount and on job/epoch changes,
 * - failed polls are reported via `onPollError` without killing the loop.
 *
 * Callbacks are read through a ref, so inline closures never restart the
 * loop; it restarts only on `job` (id/epoch) or `novelId` change.
 *
 * @module useBulkExtractionPoll
 */

import { useEffect, useRef } from "react";
import {
  type BulkExtractionStatusView,
  type BulkJobStatus,
  bulkExtractionApi,
} from "@/lib/api/bulkExtraction";

/** Poll cadence while a bulk job is active (spec §8.2 poll cadence). */
export const BULK_EXTRACTION_POLL_INTERVAL_MS = 3000;

const TERMINAL_JOB_STATUSES: readonly BulkJobStatus[] = [
  "completed",
  "cancelled",
  "failed",
] as const;

/** Terminal job statuses — polling stops once one is observed. */
export function isTerminalJobStatus(status: BulkJobStatus): boolean {
  return TERMINAL_JOB_STATUSES.includes(status);
}

/** The poll loop target: an adopted job plus its restart epoch. */
export interface BulkExtractionPollTarget {
  /** Adopted job id. */
  readonly id: string;
  /**
   * Bumped by the owner on resume so the effect re-runs for the SAME job id
   * (identity-based deps — the id alone cannot express a restart).
   */
  readonly epoch: number;
}

export interface UseBulkExtractionPollCallbacks {
  /** Called with every successful status view (also clears prior errors). */
  readonly onStatus: (view: BulkExtractionStatusView) => void;
  /** Called with the raw error of a failed poll (transient — loop continues). */
  readonly onPollError: (err: unknown) => void;
}

export function useBulkExtractionPoll(
  novelId: string,
  job: BulkExtractionPollTarget | null,
  callbacks: UseBulkExtractionPollCallbacks,
): void {
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  useEffect(() => {
    if (!job) return;

    let stopped = false;
    let inFlight = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    const stop = () => {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
    };

    const poll = async () => {
      if (inFlight || stopped) return; // no overlapping polls
      inFlight = true;
      try {
        const view = await bulkExtractionApi.bulkJobStatus(novelId, job.id);
        if (stopped) return;
        callbacksRef.current.onStatus(view);
        if (isTerminalJobStatus(view.status)) stop();
      } catch (err) {
        // Transient failure: surface it but keep polling the active job.
        if (!stopped) callbacksRef.current.onPollError(err);
      } finally {
        inFlight = false;
      }
    };

    timer = setInterval(() => void poll(), BULK_EXTRACTION_POLL_INTERVAL_MS);
    void poll(); // immediate first poll on (re)start

    return () => {
      stopped = true;
      stop();
    };
  }, [novelId, job]);
}
