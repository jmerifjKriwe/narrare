"use client";

/**
 * useBulkExtraction — job lifecycle hook for bulk KB extraction (F2, ADR-092).
 *
 * Owns one bulk job per mount: `start` adopts the returned job id and
 * `cancel`/`resume` act on the adopted job (poll *scheduling* lives in
 * `useBulkExtractionPoll`). Resume bumps the job epoch, which restarts the
 * poll loop on the SAME job id (start would create a new job — spec §4.5).
 *
 * Interrupted degrade (spec §8.2): a 404 poll (job lost to a server restart
 * or foreign/unknown id) flips `isInterrupted`, halts the loop, and
 * `isActive` goes false — recover via a new `start()`. `reset()` halts
 * polling deliberately and clears all job state.
 *
 * The status view is the single source of truth: cancel/resume responses
 * (job views without chapter rows, spec §4.4/§4.5) are merged into it, so
 * the last polled chapter rows survive.
 *
 * Public result types live in {@link useBulkExtraction.types}.
 *
 * @module useBulkExtraction
 */

import { useCallback, useRef, useState } from "react";
import {
  BulkExtractionApiError,
  type BulkExtractionJobView,
  type BulkExtractionStatusView,
  bulkExtractionApi,
} from "@/lib/api/bulkExtraction";
import type { UseBulkExtractionResult } from "@/lib/hooks/useBulkExtraction.types";
import { isTerminalJobStatus, useBulkExtractionPoll } from "@/lib/hooks/useBulkExtractionPoll";

export type { UseBulkExtractionResult } from "@/lib/hooks/useBulkExtraction.types";

function toErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function useBulkExtraction(novelId: string): UseBulkExtractionResult {
  // The epoch bumps on resume so the poll effect re-runs for the SAME job id
  // (identity-based effect deps — the id alone cannot express a restart).
  const [job, setJob] = useState<{ readonly id: string; readonly epoch: number } | null>(null);
  const [status, setStatus] = useState<BulkExtractionStatusView | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isInterrupted, setIsInterrupted] = useState(false);
  const jobId = job?.id ?? null;
  const jobIdRef = useRef<string | null>(null);
  jobIdRef.current = jobId;

  /** Merge a job-view response (start/cancel/resume) into the status view. */
  const mergeJobView = useCallback((view: BulkExtractionJobView) => {
    setStatus((prev) => (prev && prev.job_id === view.job_id ? { ...prev, ...view } : prev));
  }, []);

  const start = useCallback(
    async (chapterIds: string[]): Promise<BulkExtractionJobView | null> => {
      setIsStarting(true);
      setError(null);
      setStatus(null);
      setIsInterrupted(false);
      try {
        const view = await bulkExtractionApi.startBulkExtraction(novelId, chapterIds);
        setJob({ id: view.job_id, epoch: 0 });
        return view;
      } catch (err) {
        setError(toErrorMessage(err));
        return null;
      } finally {
        setIsStarting(false);
      }
    },
    [novelId],
  );

  const cancel = useCallback(async () => {
    const currentJobId = jobIdRef.current;
    if (!currentJobId) return;
    try {
      mergeJobView(await bulkExtractionApi.cancelBulkJob(novelId, currentJobId));
      setError(null);
    } catch (err) {
      setError(toErrorMessage(err));
    }
  }, [mergeJobView, novelId]);

  const resume = useCallback(async () => {
    const currentJobId = jobIdRef.current;
    if (!currentJobId) return;
    try {
      mergeJobView(await bulkExtractionApi.resumeBulkJob(novelId, currentJobId));
      setError(null);
      setIsInterrupted(false);
      setJob((prev) => (prev === null ? prev : { ...prev, epoch: prev.epoch + 1 }));
    } catch (err) {
      setError(toErrorMessage(err));
    }
  }, [mergeJobView, novelId]);

  /** Halt polling deliberately and drop all job state (spec §8.2 restart). */
  const reset = useCallback(() => {
    setJob(null);
    setStatus(null);
    setError(null);
    setIsInterrupted(false);
  }, []);

  useBulkExtractionPoll(novelId, job, {
    onStatus: (view) => {
      setStatus(view);
      setError(null);
    },
    onPollError: (err) => {
      setError(toErrorMessage(err));
      // A 404 means the job is gone (interrupted, spec §8.2); the poll loop
      // has already halted itself for that case.
      if (err instanceof BulkExtractionApiError && err.status === 404) {
        setIsInterrupted(true);
      }
    },
  });

  const isTerminal = status !== null && isTerminalJobStatus(status.status);

  return {
    jobId,
    status,
    chapters: status?.chapters ?? [],
    totals: status?.totals ?? null,
    isStarting,
    isActive: jobId !== null && !isTerminal && !isInterrupted,
    isInterrupted,
    error,
    start,
    cancel,
    resume,
    reset,
  };
}
