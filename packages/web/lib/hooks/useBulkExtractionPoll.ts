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
 * - a 404 poll error means the job is GONE (in-memory registry lost to a
 *   restart, or a foreign/unknown job — foreign ≡ unknown) → the loop HALTS
 *   and the typed `BulkExtractionApiError` is reported via `onPollError`
 *   (interrupted degrade, spec §8.2); every other error is transient and
 *   only reported,
 * - the interval is cleared on unmount and on job/epoch changes,
 * - failed polls are reported via `onPollError` with the RAW error; only a
 *   404 kills the loop (interrupted), every other failure stays transient.
 *
 * Callbacks are read through a ref, so inline closures never restart the
 * loop; it restarts only on `job` (id/epoch) or `novelId` change.
 *
 * @module useBulkExtractionPoll
 */

import { useEffect, useRef } from "react";
import {
  BulkExtractionApiError,
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

/**
 * A 404 poll error means the job is GONE (registry lost to a restart, or a
 * foreign/unknown id) — interrupted per spec §8.2. Single classification
 * for the loop's halt decision AND the owner's interrupted flag.
 */
export function isLostJobPollError(err: unknown): boolean {
  return err instanceof BulkExtractionApiError && err.status === 404;
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
  /**
   * Called with the RAW error of a failed poll — a `BulkExtractionApiError`
   * with `status === 404` means the job is gone (interrupted, spec §8.2);
   * the loop has already halted for that case. Any other error is transient
   * and the loop keeps running.
   */
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
        if (stopped) return;
        // 404 = job gone (restart/foreign job) — interrupted per spec §8.2:
        // halt the loop instead of polling forever; the owner reads the
        // typed error from onPollError. Everything else stays transient.
        if (isLostJobPollError(err)) stop();
        callbacksRef.current.onPollError(err);
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
