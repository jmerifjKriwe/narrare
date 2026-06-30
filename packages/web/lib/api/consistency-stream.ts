/**
 * SSE-backed consistency check stream (ADR-044).
 *
 * Connects to the backend `POST /api/v1/consistency/check/stream?novel_id={novelId}`
 * SSE endpoint and parses the structured two-stage event stream.
 *
 * The backend emits type-discriminated events:
 *  1. `{"type": "stage", ...ConsistencyStageEvent fields...}` — stage progression
 *  2. `{"type": "result", ...ConsistencyResponse fields...}` — terminal result
 *  3. `data: [DONE]` — sentinel
 *
 * Stage 1 (`extracting_facts`) emits progress updates plus `facts_extracted`.
 * Stage 2 (`checking_consistency`) emits progress updates plus `issues_found`
 * and progressive `issue` objects via `onIssue`.
 * The terminal stage (`complete`) signals pipeline end before the result event.
 *
 * RULE-17 contract parity: the types below mirror the Pydantic models in
 * `apps/api/narrare/consistency/stage_schemas.py` and `schemas.py` exactly
 * (field names, snake_case, optionality). The backend is the SSOT.
 *
 * The transport/parser (auth headers, URL prefixing, SSE line parsing,
 * connect timeout, abort handling) lives in {@link ./streaming.ts}.
 *
 * @module consistency-stream
 */

import type { ConsistencyCheckType, ConsistencyIssue } from "./analysis";
import { connectSSE } from "./streaming";

// ---------------------------------------------------------------------------
// Request type (mirrors ConsistencyRequest from schemas.py — RULE-17)
// ---------------------------------------------------------------------------

/**
 * Request body for `POST /consistency/check/stream`.
 *
 * RULE-17 contract parity: mirrors `ConsistencyRequest` in
 * `apps/api/narrare/consistency/schemas.py`.
 */
export interface ConsistencyCheckRequest {
  /** Chapters to check. Empty array checks all chapters. */
  chapter_ids?: string[];
  /** Which check types to run. Empty array runs all. */
  check_types?: ConsistencyCheckType[];
  /** Whether to include KB data for context. Default true. */
  include_kb?: boolean;
}

// ---------------------------------------------------------------------------
// SSE event types (mirror backend schemas — RULE-17 contract parity)
// ---------------------------------------------------------------------------

/**
 * Stage name matching the Python Literal in `ConsistencyStageEvent`.
 */
export type ConsistencyStageName = "extracting_facts" | "checking_consistency" | "complete";

/**
 * Stage status matching the Python Literal in `ConsistencyStageEvent`.
 */
export type ConsistencyStageStatus = "start" | "progress" | "issue" | "complete";

/**
 * Result payload matching the terminal `ConsistencyResponse` in schemas.py.
 *
 * RULE-17 contract parity: mirrors all display-relevant fields from
 * `ConsistencyResponse` (novel_id, issues, severity counts, assessment).
 */
export interface ConsistencyResultPayload {
  novel_id: string;
  chapter_ids: string[];
  check_types: ConsistencyCheckType[];
  issues: ConsistencyIssue[];
  error_count: number;
  warning_count: number;
  info_count: number;
  total_issues: number;
  overall_assessment: string;
  analyzed_at: string;
}

/**
 * One event in a consistency-check SSE stream.
 *
 * The `type` field discriminates:
 *  - `"stage"` — staged pipeline progress (carries stage, status, progress, etc.)
 *  - `"result"` — terminal result event carrying the full `ConsistencyResponse`
 *  - `"error"` — terminal error event; `error` carries the message
 *
 * When `type === "stage"` and `status === "issue"`, the `issue` field carries
 * a progressive `ConsistencyIssue` emitted during the checking phase.
 */
export interface ConsistencyStreamEvent {
  type?: "stage" | "result" | "error";
  // Stage fields (when type === "stage")
  stage?: ConsistencyStageName;
  status?: ConsistencyStageStatus;
  progress?: number;
  message?: string;
  facts_extracted?: number | null;
  issues_found?: number | null;
  issue?: ConsistencyIssue | null;
  // Result fields (when type === "result")
  issues?: ConsistencyIssue[];
  summary?: Record<string, number>;
  entity_count?: number;
  checked_at?: string;
  novel_id?: string;
  chapter_ids?: string[];
  check_types?: ConsistencyCheckType[];
  error_count?: number;
  warning_count?: number;
  info_count?: number;
  total_issues?: number;
  overall_assessment?: string;
  analyzed_at?: string;
  // Error fields
  error?: string;
}

// ---------------------------------------------------------------------------
// Stream API
// ---------------------------------------------------------------------------

export interface ConsistencyStreamHandlers {
  /**
   * Called on each stage event for progressive UI updates.
   *
   * @param stage         Current pipeline stage name.
   * @param status        Stage event status (start, progress, issue, complete).
   * @param progress      Normalised progress within the stage (0.0-1.0).
   * @param message       Human-readable progress description.
   * @param factsExtracted  Number of facts extracted (populated after stage 1).
   * @param issuesFound     Number of issues found so far (populated during stage 2).
   */
  onStage?: (
    stage: ConsistencyStageName,
    status: ConsistencyStageStatus,
    progress: number,
    message: string,
    factsExtracted: number | null,
    issuesFound: number | null,
  ) => void;
  /**
   * Called when a progressive issue is emitted during the
   * `checking_consistency` stage (status === "issue").
   */
  onIssue?: (issue: ConsistencyIssue) => void;
  /** Called after the terminal result event arrives with the full response. */
  onComplete?: (result: ConsistencyResultPayload) => void;
  /** Called on transport failure or a terminal `"error"` event. */
  onError?: (error: Error) => void;
}

/**
 * Stream a staged consistency check for a novel (ADR-044).
 *
 * POSTs to `/consistency/check/stream?novel_id=${novelId}` with the request
 * body and parses the SSE event stream. The backend emits `"stage"` events
 * for pipeline progression, a terminal `"result"` event with the full
 * consistency response, and a `data: [DONE]` sentinel. A terminal `"error"`
 * event surfaces a server-side failure through `onError`.
 *
 * @param novelId   Novel to check (URL query parameter).
 * @param request   Request body (chapter_ids, check_types, include_kb).
 * @param handlers  Callbacks for stage updates, progressive issues, result, errors.
 * @param signal    Optional abort signal to cancel the in-flight stream.
 */
export async function streamConsistencyCheck(
  novelId: string,
  request: ConsistencyCheckRequest,
  handlers: ConsistencyStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.(undefined as unknown as ConsistencyResultPayload);
  }

  await connectSSE<ConsistencyStreamEvent>({
    url: `/consistency/check/stream?novel_id=${novelId}`,
    method: "POST",
    body: request,
    signal,
    onChunk: (event) => {
      // A terminal server-side error event: surface it and stop.
      if (event.type === "error" || event.error) {
        if (isComplete) return;
        isComplete = true;
        handlers.onError?.(new Error(event.error ?? "Consistency check failed"));
        return;
      }

      if (event.type === "stage") {
        // Emit progressive issue during checking_consistency stage
        if (event.status === "issue" && event.issue) {
          handlers.onIssue?.(event.issue);
        }

        handlers.onStage?.(
          event.stage ?? "extracting_facts",
          event.status ?? "progress",
          event.progress ?? 0,
          event.message ?? "",
          event.facts_extracted ?? null,
          event.issues_found ?? null,
        );
        return;
      }

      if (event.type === "result") {
        if (isComplete) return;
        isComplete = true;
        const result: ConsistencyResultPayload = {
          novel_id: event.novel_id ?? "",
          chapter_ids: event.chapter_ids ?? [],
          check_types: event.check_types ?? [],
          issues: event.issues ?? [],
          error_count: event.error_count ?? 0,
          warning_count: event.warning_count ?? 0,
          info_count: event.info_count ?? 0,
          total_issues: event.total_issues ?? 0,
          overall_assessment: event.overall_assessment ?? "",
          analyzed_at: event.analyzed_at ?? "",
        };
        handlers.onComplete?.(result);
      }
    },
    onComplete: complete,
    onError: (error) => {
      if (isComplete) return;
      isComplete = true;
      handlers.onError?.(error);
    },
  });
}
