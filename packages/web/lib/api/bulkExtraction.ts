/**
 * Bulk extraction job API client — KB extraction over many chapters (F2).
 *
 * REST-only JSON endpoints (no SSE, no multipart) driving the background
 * bulk job (ADR-092). Wire shapes are the spec §4 contract; the types below
 * are the RULE-17 EXACT mirror of
 * `apps/api/narrare/kb/bulk_extraction/schemas.py` — field-for-field, so
 * FE/BE drift fails loudly at the seam.
 *
 * Types are declared inline following the `extraction.ts` precedent
 * (documented deviation from the `importing.ts` types/-file pattern, plan
 * Task 6): the bulk surface and its mirror belong to the same seam as the
 * single-chapter extraction client and reuse its `ExtractionOutput` type.
 *
 * Job statuses (normative): pending | running | cancelling | completed |
 * cancelled | failed. Chapter states: pending | running | done | failed.
 * `item_count` is set iff state = done (status view); full outputs live in
 * the results view only (payload-size boundary, spec §4.2/§4.3).
 */

import { fetchApi } from "./client";
import type { ExtractionOutput } from "./extraction";

// --- Types (RULE-17 mirror of bulk_extraction/schemas.py) ---

export type BulkJobStatus =
  | "pending"
  | "running"
  | "cancelling"
  | "completed"
  | "cancelled"
  | "failed";

export type BulkChapterState = "pending" | "running" | "done" | "failed";

export interface BulkExtractionTotals {
  total: number;
  done: number;
  failed: number;
  remaining: number;
}

export interface BulkChapterStatusView {
  chapter_id: string;
  title: string;
  position: number;
  state: BulkChapterState;
  /** Extracted item count — set (≥ 0) iff state = "done", else null. */
  item_count: number | null;
  /** Chapter-level failure reason — expected on "failed" rows. */
  error: string | null;
}

export interface BulkExtractionJobView {
  job_id: string;
  novel_id: string;
  status: BulkJobStatus;
  created_at: string;
  updated_at: string;
  totals: BulkExtractionTotals;
  /** Job-level failure/terminal reason — expected on "failed"/"cancelled". */
  error: string | null;
}

export interface BulkExtractionStatusView extends BulkExtractionJobView {
  /** Every job chapter in position (server-sorted) order. */
  chapters: BulkChapterStatusView[];
}

export interface BulkExtractionResultChapter {
  chapter_id: string;
  title: string;
  position: number;
  state: BulkChapterState;
  /** Full extraction output — present iff state = "done", else null. */
  output: ExtractionOutput | null;
}

export interface BulkExtractionResultsView {
  job_id: string;
  novel_id: string;
  status: BulkJobStatus;
  chapters: BulkExtractionResultChapter[];
}

// --- API functions ---

export const bulkExtractionApi = {
  /** Start a bulk job over the given chapters. 201 → job view (status pending). */
  startBulkExtraction: (novelId: string, chapterIds: string[], signal?: AbortSignal) =>
    fetchApi<BulkExtractionJobView>(`/novels/${novelId}/kb/extract/bulk`, {
      method: "POST",
      body: JSON.stringify({ chapter_ids: chapterIds }),
      signal,
    }),

  /** Poll one job: totals plus per-chapter states (spec §4.2). */
  bulkJobStatus: (novelId: string, jobId: string, signal?: AbortSignal) =>
    fetchApi<BulkExtractionStatusView>(`/novels/${novelId}/kb/extract/bulk/${jobId}/status`, {
      signal,
    }),

  /** Full outputs for the review panel — readable in ANY job state (spec §4.3). */
  bulkJobResults: (novelId: string, jobId: string, signal?: AbortSignal) =>
    fetchApi<BulkExtractionResultsView>(`/novels/${novelId}/kb/extract/bulk/${jobId}/results`, {
      signal,
    }),

  /** Cooperative cancel; terminal jobs conflict with 409 (spec §4.4). */
  cancelBulkJob: (novelId: string, jobId: string, signal?: AbortSignal) =>
    fetchApi<BulkExtractionJobView>(`/novels/${novelId}/kb/extract/bulk/${jobId}/cancel`, {
      method: "POST",
      signal,
    }),

  /** Reset a cancelled/failed job and re-dispatch its runner (spec §4.5). */
  resumeBulkJob: (novelId: string, jobId: string, signal?: AbortSignal) =>
    fetchApi<BulkExtractionJobView>(`/novels/${novelId}/kb/extract/bulk/${jobId}/resume`, {
      method: "POST",
      signal,
    }),
};
