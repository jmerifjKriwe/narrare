/**
 * SSE-backed voice-check analysis stream (WRITE-010).
 *
 * Connects to the backend `POST /api/v1/analysis/voice-check/{chapter_id}`
 * SSE endpoint and parses the structured `VoiceCheckStreamEvent` stream.
 *
 * Voice-check is **chapter-scoped** (like coreference: the path parameter
 * identifies the chapter, no request body) but emits **MULTIPLE per-character
 * results** (like character-voice): the backend emits a type-discriminated
 * event stream — `"progress"`, one `"result"` per speaking character, then a
 * terminal `"done"` (or `"error"`) event — followed by a `data: [DONE]`
 * sentinel. The caller's `onResult` fires once per character.
 *
 * RULE-17 contract parity: the types below mirror the Pydantic models in
 * `apps/api/narrare/analysis/schemas_voice_check.py` exactly (field names,
 * snake_case, optionality). The backend is the SSOT. The checker is read-only
 * (it flags + scores; nothing here is persisted), so every result field is a
 * display-only report artifact (ADR-057 Decision 5).
 *
 * The transport/parser (auth headers, URL prefixing, SSE line parsing,
 * connect timeout, abort handling) lives in {@link ./streaming.ts}.
 *
 * @module voice-check-stream
 */

import { connectSSE } from "./streaming";

// ---------------------------------------------------------------------------
// Result payload types (mirror backend schemas — RULE-17 contract parity)
// ---------------------------------------------------------------------------

/**
 * Severity band of the overall match score (ADR-057 Decision 2 thresholds).
 *
 * RULE-17 contract parity: mirrors the documented `band` values of
 * `VoiceCheckResult` (`green | yellow | fair | red`). `null` when the
 * character is unscorable (no stored profile, or no sub-score available).
 */
export type VoiceCheckBand = "green" | "yellow" | "fair" | "red";

/**
 * The agent's qualitative reading of a character's voice consistency.
 *
 * RULE-17 contract parity: mirrors the documented `match_judgment` values of
 * `VoiceCheckResult`. `null` for characters not judged by the agent (no
 * profile).
 */
export type VoiceCheckJudgment = "consistent" | "mostly_consistent" | "notable_drift" | "off";

/**
 * A single dialogue line flagged as inconsistent with the stored profile.
 *
 * RULE-17 contract parity: mirrors `FlaggedLineResponse` (display-only — never
 * persisted; the checker is read-only).
 */
export interface FlaggedLine {
  /** Verbatim excerpt of the character's dialogue that reads as inconsistent. */
  quote: string;
  /** Concise, profile-grounded explanation of the divergence. */
  reason: string;
}

/**
 * Per-character voice-check result (display-only — never persisted).
 *
 * Carries the blended match score plus the agent's qualitative judgment and
 * flagged lines. RULE-17 contract parity: mirrors `VoiceCheckResult` (field
 * names, snake_case, optionality). `match_score` / `band` are `null` when the
 * character has no stored profile or neither sub-score is available.
 */
export interface VoiceCheckResult {
  /** The character's canonical name (as attributed in the chapter dialogue). */
  character_name: string;
  /** Overall blended match score [0, 100], or null when unscorable. */
  match_score: number | null;
  /** Severity band of `match_score`, or null when `match_score` is null. */
  band: VoiceCheckBand | null;
  /** The agent's qualitative judgment, or null for characters with no profile. */
  match_judgment: VoiceCheckJudgment | null;
  /** Agent qualitative sub-score [0, 100], or null. */
  qualitative_sub_score: number | null;
  /** Deterministic metric-delta sub-score [0, 100], or null. */
  metric_delta_subscore: number | null;
  /** Dialogue lines flagged as inconsistent, each with a profile-grounded reason. */
  flagged_lines: FlaggedLine[];
  /** False iff the character has no stored voice profile (RULE-11 graceful signal). */
  has_profile: boolean;
  /** Number of metrics that contributed to the delta. */
  n_comparable_metrics: number;
}

// ---------------------------------------------------------------------------
// SSE event type
// ---------------------------------------------------------------------------

/**
 * One event in a voice-check SSE stream.
 *
 * RULE-17 contract parity: mirrors `VoiceCheckStreamEvent`. The `event` field
 * discriminates between progress, per-character result, completion, and error:
 *  - `"progress"` — pipeline status update (carried in `progress`).
 *  - `"result"` — carries one character's result in `result` (one per character).
 *  - `"done"` — terminal success event (`is_final === true`).
 *  - `"error"` — terminal error event; `error` carries the message
 *    (`is_final === true`).
 */
export interface VoiceCheckStreamEvent {
  event?: "progress" | "result" | "done" | "error";
  result?: VoiceCheckResult | null;
  progress?: string | null;
  error?: string | null;
  is_final?: boolean;
}

// ---------------------------------------------------------------------------
// Stream API
// ---------------------------------------------------------------------------

export interface VoiceCheckStreamHandlers {
  /** Called for each `"progress"` event (pipeline status). */
  onProgress?: (message: string) => void;
  /** Called once per speaking character when its `"result"` event arrives. */
  onResult: (result: VoiceCheckResult) => void;
  /** Called after the terminal `"done"` event (or stream end). Never after `onError`. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal `"error"` event. */
  onError?: (error: Error) => void;
}

/**
 * Stream a voice-consistency check for a chapter (WRITE-010).
 *
 * POSTs to `/analysis/voice-check/{chapterId}` (chapter-scoped, no request
 * body) and parses the SSE event stream. The backend emits `"progress"`
 * events, one `"result"` per speaking character, then a `"done"` terminal
 * event and a `data: [DONE]` signal. A terminal `"error"` event surfaces a
 * server-side failure through `onError`.
 *
 * @param chapterId  Chapter to check (URL path parameter).
 * @param handlers   Callbacks for progress, per-character results, completion, errors.
 * @param signal     Optional abort signal to cancel the in-flight stream.
 */
export async function streamVoiceCheck(
  chapterId: string,
  handlers: VoiceCheckStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<VoiceCheckStreamEvent>({
    url: `/analysis/voice-check/${chapterId}`,
    method: "POST",
    signal,
    onChunk: (event) => {
      // A terminal server-side error event: surface it and stop.
      if (event.event === "error" || event.error) {
        if (isComplete) return;
        isComplete = true;
        handlers.onError?.(new Error(event.error ?? "Voice-check analysis failed"));
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
