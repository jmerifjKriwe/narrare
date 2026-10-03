"use client";

/**
 * useBulkExtraction — job lifecycle hook for bulk KB extraction (F2, ADR-092).
 *
 * Owns one bulk job per mount: `start` adopts the returned job id and
 * `cancel`/`resume` act on the adopted job (poll *scheduling* lives in
 * `useBulkExtractionPoll`). Resume bumps the job epoch, which restarts the
 * poll loop on the SAME job id (start would create a new job — spec §4.5).
 *
 * The status view is the single source of truth: cancel/resume responses
 * (job views without chapter rows, spec §4.4/§4.5) are merged into it, so
 * the last polled chapter rows survive.
 *
 * @module useBulkExtraction
 */

import { useCallback, useRef, useState } from "react";
import {
  type BulkChapterStatusView,
  type BulkExtractionJobView,
  type BulkExtractionStatusView,
  type BulkExtractionTotals,
  bulkExtractionApi,
} from "@/lib/api/bulkExtraction";
import { isTerminalJobStatus, useBulkExtractionPoll } from "@/lib/hooks/useBulkExtractionPoll";

export interface UseBulkExtractionResult {
  /** Adopted job id, or null before the first successful start. */
  jobId: string | null;
  /** Latest polled status view (totals + per-chapter rows), or null. */
  status: BulkExtractionStatusView | null;
  /** Per-chapter rows of the latest poll, in position order. */
  chapters: BulkChapterStatusView[];
  /** Aggregated counts of the latest poll, or null. */
  totals: BulkExtractionTotals | null;
  /** True while the start request is in flight. */
  isStarting: boolean;
  /** True while a job is adopted and not yet terminal (poll loop running). */
  isActive: boolean;
  /** Latest start/poll/cancel/resume error message, or null. */
  error: string | null;
  /** Start a job over the given chapters; resolves null on failure. */
  start: (chapterIds: string[]) => Promise<BulkExtractionJobView | null>;
  /** Cooperatively cancel the adopted job (spec §4.4). */
  cancel: () => Promise<void>;
  /** Resume a cancelled/failed job on the same id and re-poll (spec §4.5). */
  resume: () => Promise<void>;
}

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
      setJob((prev) => (prev === null ? prev : { ...prev, epoch: prev.epoch + 1 }));
    } catch (err) {
      setError(toErrorMessage(err));
    }
  }, [mergeJobView, novelId]);

  useBulkExtractionPoll(novelId, job, {
    onStatus: (view) => {
      setStatus(view);
      setError(null);
    },
    onPollError: (err) => setError(toErrorMessage(err)),
  });

  const isTerminal = status !== null && isTerminalJobStatus(status.status);

  return {
    jobId,
    status,
    chapters: status?.chapters ?? [],
    totals: status?.totals ?? null,
    isStarting,
    isActive: jobId !== null && !isTerminal,
    error,
    start,
    cancel,
    resume,
  };
}
