/**
 * Public type contract for {@link useBulkExtraction} (F2, ADR-092).
 *
 * Split from the hook implementation per RULE-04/RULE-06 — same pattern as
 * `use-ai-operation.types.ts` / `useConsistencyStream.types.ts`.
 *
 * @module useBulkExtraction.types
 */

import type {
  BulkChapterStatusView,
  BulkExtractionJobView,
  BulkExtractionStatusView,
  BulkExtractionTotals,
} from "@/lib/api/bulkExtraction";

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
  /** True while a job is adopted, not terminal, and the poll loop is live. */
  isActive: boolean;
  /**
   * True when a poll 404'd — the job is gone (server restart lost the
   * in-memory registry, or foreign/unknown job): interrupted degrade per
   * spec §8.2. The poll loop has halted; recover via a new `start()`.
   */
  isInterrupted: boolean;
  /**
   * True while a COMPLETED corpus job's post-pass dedup block is still
   * `{analyzed: false}` inside the `DEDUP_PENDING_GRACE_MS` window (F3 fix
   * round 1): the analysis may still be running — the wire cannot tell
   * pending from failed. The dedup card shows a pending copy (never the
   * false "could not run") while this is true; after the bound expires the
   * unavailable copy is honest.
   */
  dedupPending: boolean;
  /** Latest start/poll/cancel/resume error message, or null. */
  error: string | null;
  /** Start a job over the given chapters; resolves null on failure. */
  start: (chapterIds: string[]) => Promise<BulkExtractionJobView | null>;
  /**
   * Adopt a PRE-started job id (F3 corpus pass) without a start call —
   * clears state and begins polling the adopted job immediately.
   */
  adopt: (jobId: string) => void;
  /** Cooperatively cancel the adopted job (spec §4.4). */
  cancel: () => Promise<void>;
  /** Resume a cancelled/failed job on the same id and re-poll (spec §4.5). */
  resume: () => Promise<void>;
  /** Halt polling deliberately and clear all job state (T7 restart affordance). */
  reset: () => void;
}
