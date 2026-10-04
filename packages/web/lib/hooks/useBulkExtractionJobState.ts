"use client";

/**
 * useBulkExtractionJobState — job state machine for one bulk extraction job
 * (F2, ADR-092). Extracted from `useBulkExtraction` (RULE-04 hook size
 * limit): owns the job identity (id + restart epoch), the status view (the
 * single source of truth — cancel/resume job views are merged into it so
 * the last polled chapter rows survive), the transient flags, and every
 * transition (`start`/`adopt`/`cancel`/`resume`/`reset`) plus the semantic
 * poll-result appliers the lifecycle composer wires into
 * `useBulkExtractionPoll`.
 *
 * Interrupted degrade (spec §8.2): a 404 poll (job lost to a server restart
 * or foreign/unknown id) flips `isInterrupted` — recover via a new
 * `start()`. `reset()` halts polling deliberately and clears all job state.
 *
 * `clearDedupPending` is injected so every fresh/adopted-job transition
 * also clears the caller's dedup pending window (`useDedupPendingGrace`)
 * exactly as the pre-split hook did.
 *
 * @module useBulkExtractionJobState
 */

import { useCallback, useState } from "react";
import {
  type BulkExtractionJobView,
  type BulkExtractionStatusView,
  bulkExtractionApi,
  getBulkErrorMessage,
} from "@/lib/api/bulkExtraction";
import { isLostJobPollError } from "@/lib/hooks/bulkExtractionPollPolicy";

export function useBulkExtractionJobState(novelId: string, clearDedupPending: () => void) {
  // The epoch bumps on resume so the poll effect re-runs for the SAME job id
  // (identity-based effect deps — the id alone cannot express a restart).
  const [job, setJob] = useState<{ readonly id: string; readonly epoch: number } | null>(null);
  const [status, setStatus] = useState<BulkExtractionStatusView | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isInterrupted, setIsInterrupted] = useState(false);
  const jobId = job?.id ?? null;

  /** Clear transient view state whenever a fresh/adopted job replaces the old. */
  const clearTransientState = useCallback(() => {
    setStatus(null);
    setError(null);
    setIsInterrupted(false);
    clearDedupPending();
  }, [clearDedupPending]);

  /** Merge a job-view response (start/cancel/resume) into the status view. */
  const mergeJobView = useCallback((view: BulkExtractionJobView) => {
    setStatus((prev) => (prev && prev.job_id === view.job_id ? { ...prev, ...view } : prev));
  }, []);

  const start = useCallback(
    async (chapterIds: string[]): Promise<BulkExtractionJobView | null> => {
      setIsStarting(true);
      clearTransientState();
      try {
        const view = await bulkExtractionApi.startBulkExtraction(novelId, chapterIds);
        setJob({ id: view.job_id, epoch: 0 });
        return view;
      } catch (err) {
        setError(getBulkErrorMessage(err));
        return null;
      } finally {
        setIsStarting(false);
      }
    },
    [clearTransientState, novelId],
  );

  /**
   * Adopt a PRE-started job id (F3 corpus pass): the job already exists
   * server-side, so no start call is made — state is cleared and the poll
   * loop begins immediately for the adopted id.
   */
  const adopt = useCallback(
    (adoptedId: string) => {
      setJob({ id: adoptedId, epoch: 0 });
      clearTransientState();
    },
    [clearTransientState],
  );

  const cancel = useCallback(async () => {
    if (!jobId) return;
    try {
      mergeJobView(await bulkExtractionApi.cancelBulkJob(novelId, jobId));
      setError(null);
    } catch (err) {
      setError(getBulkErrorMessage(err));
    }
  }, [jobId, mergeJobView, novelId]);

  const resume = useCallback(async () => {
    if (!jobId) return;
    try {
      mergeJobView(await bulkExtractionApi.resumeBulkJob(novelId, jobId));
      setError(null);
      setIsInterrupted(false);
      setJob((prev) => (prev === null ? prev : { ...prev, epoch: prev.epoch + 1 }));
    } catch (err) {
      setError(getBulkErrorMessage(err));
    }
  }, [jobId, mergeJobView, novelId]);

  /** Halt polling deliberately and drop all job state (spec §8.2 restart). */
  const reset = useCallback(() => {
    setJob(null);
    clearTransientState();
  }, [clearTransientState]);

  /** Apply a successful poll: the status view becomes SSOT, errors clear. */
  const applyStatus = useCallback((view: BulkExtractionStatusView) => {
    setStatus(view);
    setError(null);
  }, []);

  /** Apply a failed poll: surface the message; 404 ⇒ interrupted (spec §8.2). */
  const applyPollError = useCallback((err: unknown) => {
    setError(getBulkErrorMessage(err));
    // A 404 means the job is gone (interrupted, spec §8.2); the poll loop
    // has already halted itself for that case.
    if (isLostJobPollError(err)) setIsInterrupted(true);
  }, []);

  return {
    /** Poll loop target (id + epoch) — `null` while no job is adopted. */
    job,
    jobId,
    status,
    isStarting,
    isInterrupted,
    error,
    start,
    adopt,
    cancel,
    resume,
    reset,
    applyStatus,
    applyPollError,
  };
}
