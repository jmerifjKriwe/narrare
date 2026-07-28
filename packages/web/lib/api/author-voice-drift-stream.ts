/**
 * SSE-backed author-voice-drift analysis stream (ANAL-009 Phase 2B).
 *
 * Connects to the backend `POST /api/v1/analysis/author-voice-drift/{novel_id}`
 * SSE endpoint and parses the structured `AuthorVoiceDriftEvent` stream.
 *
 * The author-voice analogue of Phase 1's {@link ./voice-drift-stream.ts}. Where
 * Phase 1 carries PER-CHARACTER results (a list), author drift carries a SINGLE
 * narrator result (one author voice per novel) — so the wire schema is singular:
 * ONE `"result"` event OR ONE `"no_profile"` event per stream, never both,
 * never repeated. The backend emits a type-discriminated event stream —
 * `"progress"`, the single `"result"` / `"no_profile"`, then a terminal `"done"`
 * (or `"error"`) event — followed by a `data: [DONE]` sentinel.
 *
 * RULE-17 contract parity: the types below mirror the Pydantic models in
 * `apps/api/narrare/analysis/schemas_author_voice_drift.py`. The shared Core
 * value objects (`TrendPoint` / `JumpPoint` / `VoiceDriftResult`) + their band /
 * drift-type Literals are REUSED directly from {@link ./voice-drift-stream} —
 * the OUTPUT shape is the locked ADR-073 D3 shape applied to the narrator trend
 * (RULE-22 — no duplication). The backend is the SSOT.
 *
 * The drift analysis is **read-only** (ADR-073 Decision 5): nothing here is
 * persisted; every field is a display-only report artifact.
 *
 * The transport/parser (auth headers, URL prefixing, SSE line parsing,
 * connect timeout, abort handling) lives in {@link ./streaming.ts}.
 *
 * @module author-voice-drift-stream
 */

import { connectSSE } from "./streaming";
import type { JumpPoint, TrendPoint, VoiceDriftBand, VoiceDriftResult } from "./voice-drift-stream";

// ---------------------------------------------------------------------------
// Result payload types (mirror backend schemas — RULE-17 contract parity)
// ---------------------------------------------------------------------------

/**
 * Graceful "narrator not analysable for drift" signal (RULE-11).
 *
 * Emitted when the stored author-voice profile cannot be drift-analysed. Author
 * voice is ONE narrator per novel, so the skip carries no character identity —
 * only the `reason` (contrast Phase 1's per-character `VoiceDriftNoProfile`
 * which also carries character_id / character_name).
 *
 * RULE-17 contract parity: mirrors `AuthorVoiceDriftNoProfile.reason`. The
 * documented `reason` values:
 *  - `"no_stored_profile"` — no `AuthorVoiceProfile` stored yet.
 *  - `"no_profile_metrics"` — profile stored but missing the `voice_metrics` /
 *    `author_metrics` blocks the trend needs.
 *  - `"no_chapters_with_prose"` — profile + metrics exist but no selected
 *    chapter has prose to measure.
 */
export type AuthorVoiceDriftNoProfileReason =
  | "no_stored_profile"
  | "no_profile_metrics"
  | "no_chapters_with_prose";

export interface AuthorVoiceDriftNoProfile {
  /** Why the narrator was skipped (author voice is one narrator per novel). */
  reason: AuthorVoiceDriftNoProfileReason | string;
}

/**
 * Longitudinal author-voice drift result (display-only — never persisted).
 *
 * Carries the deterministic per-chapter match trend (signal i, with author-
 * metric deltas MERGED into each `TrendPoint.per_metric_deltas`) + the
 * adjacent-chapter jump points (signal iii) + the aggregate match score +
 * the agent's qualitative `VoiceDriftResult` classification. Singular (one
 * narrator per novel — contrast Phase 1's per-character list).
 *
 * RULE-17 contract parity: mirrors `AuthorVoiceDriftResult`. The shared
 * `TrendPoint` / `JumpPoint` / `VoiceDriftResult` are reused from
 * {@link ./voice-drift-stream} (the Core SSOT types mirrored there).
 */
export interface AuthorVoiceDriftResult {
  /** The novel analysed (str for JSON safety). */
  novel_id?: string;
  /** Per-chapter match trend (signal i) — one `TrendPoint` per chapter with prose. */
  trend: TrendPoint[];
  /** Adjacent-chapter jump points (signal iii). Empty when no metric jumped. */
  jumps: JumpPoint[];
  /** Mean per-chapter match sub-score [0, 100], or null when trend is empty. */
  overall_match_score: number | null;
  /** Drift severity label for `overall_match_score`, or null when unscorable. */
  overall_band: VoiceDriftBand | null;
  /** The agent's qualitative longitudinal classification (reused Phase 1 shape). */
  drift: VoiceDriftResult;
}

// ---------------------------------------------------------------------------
// Request + SSE event types
// ---------------------------------------------------------------------------

/**
 * Request body for `POST /analysis/author-voice-drift/{novel_id}`.
 *
 * RULE-17 contract parity: mirrors `AuthorVoiceDriftRequest`. Omitting
 * `chapter_ids` (or null/empty) means "analyse every chapter in the novel"
 * (author voice is one narrator per novel, so there is no per-character filter).
 */
export interface AuthorVoiceDriftRequest {
  /** Specific chapter ids to analyse, or null/empty for all chapters. */
  chapter_ids?: string[] | null;
}

/**
 * One event in an author-voice-drift SSE stream.
 *
 * RULE-17 contract parity: mirrors `AuthorVoiceDriftEvent`. The `event` field
 * discriminates between progress, the single result, the graceful no-profile
 * skip, completion, and error:
 *  - `"progress"` — pipeline status update (carried in `progress`).
 *  - `"result"` — carries the narrator drift result in `result` (ONE per run).
 *  - `"no_profile"` — graceful skip when the narrator cannot be analysed
 *    (RULE-11); carries the skip detail in `no_profile`.
 *  - `"done"` — terminal success event (`is_final === true`).
 *  - `"error"` — terminal error event; `error` carries the message
 *    (`is_final === true`).
 */
export interface AuthorVoiceDriftEvent {
  event?: "progress" | "result" | "no_profile" | "done" | "error";
  result?: AuthorVoiceDriftResult | null;
  no_profile?: AuthorVoiceDriftNoProfile | null;
  progress?: string | null;
  error?: string | null;
  is_final?: boolean;
}

// ---------------------------------------------------------------------------
// Stream API
// ---------------------------------------------------------------------------

export interface AuthorVoiceDriftStreamHandlers {
  /** Called for each `"progress"` event (pipeline status / chapter count). */
  onProgress?: (message: string) => void;
  /** Called once with the narrator drift result when the `"result"` event arrives. */
  onResult: (result: AuthorVoiceDriftResult) => void;
  /** Called when the graceful `"no_profile"` event arrives (RULE-11). */
  onNoProfile?: (noProfile: AuthorVoiceDriftNoProfile) => void;
  /** Called after the terminal `"done"` event (or stream end). Never after `onError`. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal `"error"` event. */
  onError?: (error: Error) => void;
}

/**
 * Stream an author-voice-drift analysis for a novel (ANAL-009 Phase 2B).
 *
 * POSTs to `/analysis/author-voice-drift/{novelId}` with the optional chapter
 * filter body and parses the SSE event stream. The backend emits `"progress"`
 * events, ONE `"result"` event carrying the narrator drift result (or ONE
 * `"no_profile"` graceful skip), then a `"done"` terminal event and a
 * `data: [DONE]` signal. A terminal `"error"` event surfaces a server-side
 * failure through `onError`.
 *
 * @param novelId   Novel to analyse (URL path parameter).
 * @param body      `{ chapter_ids? }` — null/omitted/empty analyses every chapter.
 * @param handlers  Callbacks for progress, the single result, the no-profile skip, completion, errors.
 * @param signal    Optional abort signal to cancel the in-flight stream.
 */
export async function streamAuthorVoiceDrift(
  novelId: string,
  body: AuthorVoiceDriftRequest,
  handlers: AuthorVoiceDriftStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<AuthorVoiceDriftEvent>({
    url: `/analysis/author-voice-drift/${novelId}`,
    method: "POST",
    body,
    signal,
    onChunk: (event) => {
      // A terminal server-side error event: surface it and stop.
      if (event.event === "error" || event.error) {
        if (isComplete) return;
        isComplete = true;
        handlers.onError?.(new Error(event.error ?? "Author-voice-drift analysis failed"));
        return;
      }

      if (event.event === "progress" && event.progress) {
        handlers.onProgress?.(event.progress);
        return;
      }

      if (event.event === "result" && event.result) {
        handlers.onResult(event.result);
        return;
      }

      if (event.event === "no_profile" && event.no_profile) {
        handlers.onNoProfile?.(event.no_profile);
        return;
      }

      if (event.event === "done" || event.is_final) {
        complete();
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
