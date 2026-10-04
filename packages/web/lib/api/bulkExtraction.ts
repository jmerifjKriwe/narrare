/**
 * Bulk extraction job API client — KB extraction over many chapters (F2).
 *
 * REST-only JSON endpoints (no SSE, no multipart) driving the background
 * bulk job (ADR-092). Wire shapes are the spec §4 contract; the types below
 * are the RULE-17 EXACT mirror of
 * `apps/api/narrare/kb/bulk_extraction/schemas.py` — field-for-field, so
 * FE/BE drift fails loudly at the seam.
 *
 * Errors: non-OK responses reject with {@link BulkExtractionApiError}
 * carrying the HTTP status. This client is built on `fetchApiRaw` (scoped
 * here — `fetchApi` itself is unchanged globally) because `fetchApi`
 * flattens errors to strings and the poll loop needs the status to detect a
 * 404 interrupted job (spec §8.2).
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

import { fetchApiRaw } from "./client";
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

// --- Corpus pass types (F3, plan Task 4 — RULE-17 mirror of schemas_corpus.py) ---

/** Which D20a cap truncated the corpus selection (`corpus.py` `CapReason`). */
export type CapReason = "chapters" | "words";

/**
 * Honest pre-run estimate — EXACT mirror of `CorpusEstimateView`
 * (`apps/api/narrare/kb/bulk_extraction/schemas_corpus.py`, 8 fields).
 * `ai_calls === chapter_count` (D14a: one call per chapter); totals cover ALL
 * enumerated chapters; truncation is explicit via `capped`/`cap_reason`.
 */
export interface CorpusEstimate {
  /** All chapters enumerated for the novel (not just the selected prefix). */
  total_chapters: number;
  /** Word sum over ALL enumerated chapters. */
  total_word_count: number;
  /** The selected prefix's ids, in position order (what the run will cover). */
  selected_chapter_ids: string[];
  /** Length of the selected prefix. */
  chapter_count: number;
  /** Word sum of the selected prefix (what the run will actually cost). */
  word_count: number;
  /** Extraction calls the run will make — exactly `chapter_count` (D14a). */
  ai_calls: number;
  /** Whether a D20a cap truncated the selection (never silent). */
  capped: boolean;
  /** Which cap truncated the selection — "chapters" | "words" | null. */
  cap_reason: CapReason | null;
}

// --- Status-carrying error + response parsing ---

/** Error from a bulk endpoint carrying the HTTP status (404 = job gone). */
export class BulkExtractionApiError extends Error {
  /** HTTP status code (404 interrupted / 409 conflict / 422 validation / …). */
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "BulkExtractionApiError";
    this.status = status;
  }
}

/**
 * User-displayable message for a bulk client error. The message is the
 * server-AUTHORED job-lifecycle detail (HTTP status text / FastAPI detail,
 * e.g. "A bulk extraction job is already active for this novel") — never
 * raw backend internals (ADR-043 §16.5). Lifecycle/error display hooks use
 * this single mapping so the seam stays consistent.
 */
export function getBulkErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/** True when the typed client error reports HTTP 422 — the corpus pass's split-first degrade. */
export function isSplitFirstBulkError(err: unknown): boolean {
  return err instanceof BulkExtractionApiError && err.status === 422;
}

/**
 * Parse a `fetchApiRaw` response: JSON body on success, typed error with the
 * status otherwise. The detail extraction mirrors `fetchApi`'s error shape
 * (string detail, or FastAPI validation arrays joined from `msg` fields).
 */
async function parseBulkResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = body?.detail;
  const message =
    typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail
            .map((entry) => (typeof entry?.msg === "string" ? entry.msg : String(entry)))
            .join("; ")
        : `HTTP ${response.status}`;
  throw new BulkExtractionApiError(response.status, message);
}

// --- API functions ---

export const bulkExtractionApi = {
  /** Start a bulk job over the given chapters. 201 → job view (status pending). */
  startBulkExtraction: (novelId: string, chapterIds: string[], signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/extract/bulk`, {
      method: "POST",
      body: JSON.stringify({ chapter_ids: chapterIds }),
      signal,
    }).then(parseBulkResponse<BulkExtractionJobView>),

  /** Poll one job: totals plus per-chapter states (spec §4.2). */
  bulkJobStatus: (novelId: string, jobId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/extract/bulk/${jobId}/status`, { signal }).then(
      parseBulkResponse<BulkExtractionStatusView>,
    ),

  /** Full outputs for the review panel — readable in ANY job state (spec §4.3). */
  bulkJobResults: (novelId: string, jobId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/extract/bulk/${jobId}/results`, { signal }).then(
      parseBulkResponse<BulkExtractionResultsView>,
    ),

  /** Cooperative cancel; terminal jobs conflict with 409 (spec §4.4). */
  cancelBulkJob: (novelId: string, jobId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/extract/bulk/${jobId}/cancel`, {
      method: "POST",
      signal,
    }).then(parseBulkResponse<BulkExtractionJobView>),

  /** Reset a cancelled/failed job and re-dispatch its runner (spec §4.5). */
  resumeBulkJob: (novelId: string, jobId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/extract/bulk/${jobId}/resume`, {
      method: "POST",
      signal,
    }).then(parseBulkResponse<BulkExtractionJobView>),

  /**
   * Honest pre-run corpus-pass estimate (F3 §4.3). 200 → `CorpusEstimate`;
   * 422 when the first chapter alone exceeds the word cap (split-first).
   */
  corpusEstimate: (novelId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/extract/bulk/corpus/estimate`, { signal }).then(
      parseBulkResponse<CorpusEstimate>,
    ),

  /**
   * Start a corpus pass over the START-time prefix (F3 §4.4, no body).
   * 201 → job view (kind "corpus"); 409 while another job is active; 422
   * with honest counts when no prefix fits.
   */
  startCorpusPass: (novelId: string, signal?: AbortSignal) =>
    fetchApiRaw(`/novels/${novelId}/kb/extract/bulk/corpus`, {
      method: "POST",
      signal,
    }).then(parseBulkResponse<BulkExtractionJobView>),
};
