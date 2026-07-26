/**
 * SSE-backed character voice-drift analysis stream (ANAL-009 Phase 1).
 *
 * Connects to the backend `POST /api/v1/analysis/voice-drift/{novel_id}` SSE
 * endpoint and parses the structured `VoiceDriftEvent` stream.
 *
 * Voice-drift is **novel-scoped** (like character-voice: the path parameter
 * identifies the novel, request body carries optional filters) and emits TWO
 * kinds of per-character payloads: a `character_result` (one per analysable
 * character — those with a stored profile + voice_metrics + dialogue) and a
 * graceful `no_profile` skip (one per character that could not be analysed,
 * RULE-11). The backend emits a type-discriminated event stream — `"progress"`,
 * one `"character_result"` / `"no_profile"` per character, then a terminal
 * `"done"` (or `"error"`) event — followed by a `data: [DONE]` sentinel.
 *
 * RULE-17 contract parity: the types below mirror the Pydantic models in
 * `apps/api/narrare/analysis/schemas_voice_drift.py` and the Layer-0 Core
 * value objects in
 * `packages/core/narrare_core/analysis/voice_drift_scoring_types.py`
 * (`TrendPoint` / `JumpPoint`) +
 * `packages/core/narrare_core/agents/character_voice_drift_types.py`
 * (`VoiceDriftResult`) exactly (field names, snake_case, optionality). The
 * backend is the SSOT. The drift analysis is **read-only** (ADR-073 Decision 5):
 * nothing here is persisted; every field is a display-only report artifact.
 *
 * The transport/parser (auth headers, URL prefixing, SSE line parsing,
 * connect timeout, abort handling) lives in {@link ./streaming.ts}.
 *
 * @module voice-drift-stream
 */

import { connectSSE } from "./streaming";

// ---------------------------------------------------------------------------
// Result payload types (mirror backend schemas — RULE-17 contract parity)
// ---------------------------------------------------------------------------

/**
 * Drift severity band of a match score (ADR-073 Decision 4 thresholds —
 * identical to WRITE-010's `band_for_score`).
 *
 * RULE-17 contract parity: mirrors the documented `band` values emitted on
 * `TrendPoint.band` and `VoiceDriftCharacterResult.overall_band`
 * (`"stable" | "minor" | "moderate" | "major"`). `null` on the overall band
 * when the character has no trend (never speaks).
 *
 * Band ↔ match score:
 *  - `"stable"`   — ≥ 90 (green ●)
 *  - `"minor"`    — 70–89 (yellow ▲)
 *  - `"moderate"` — 50–69 (orange ◆)
 *  - `"major"`    — < 50 (red ◇)
 */
export type VoiceDriftBand = "stable" | "minor" | "moderate" | "major";

/**
 * The agent's qualitative longitudinal classification (ADR-073 Decision 3).
 *
 * RULE-17 contract parity: mirrors the `drift_type` Literal on
 * `VoiceDriftResult` (`"evolution" | "context" | "inconsistency"`).
 */
export type VoiceDriftType = "evolution" | "context" | "inconsistency";

/**
 * The reason a character could not be drift-analysed (RULE-11 graceful skip).
 *
 * RULE-17 contract parity: mirrors the documented `reason` values of
 * `VoiceDriftNoProfile`.
 */
export type VoiceDriftNoProfileReason =
  | "no_stored_profile"
  | "no_voice_metrics"
  | "no_dialogue_in_selected_chapters";

/**
 * One point on the per-chapter match trend (signal i output).
 *
 * RULE-17 contract parity: mirrors `TrendPoint`
 * (`packages/core/narrare_core/analysis/voice_drift_scoring_types.py`).
 */
export interface TrendPoint {
  /** The chapter identifier. */
  chapter_id: string;
  /** Per-chapter match sub-score [0, 100] (100 = matches the profile perfectly). */
  match_subscore: number;
  /** Metric name → normalized [0, 1] distance vs the profile. Empty when none comparable. */
  per_metric_deltas: Record<string, number>;
  /** Drift severity label for `match_subscore`. */
  band: VoiceDriftBand;
}

/**
 * An adjacent-chapter jump (signal iii output) — localises where drift began.
 *
 * RULE-17 contract parity: mirrors `JumpPoint`.
 */
export interface JumpPoint {
  /** The earlier chapter of the adjacent pair. */
  from_chapter_id: string;
  /** The later chapter of the adjacent pair. */
  to_chapter_id: string;
  /** Which metric(s) shifted beyond the threshold (≥ 1 entry). */
  jumped_metrics: string[];
  /** Normalized [0, 1] magnitude of the jump (mean of the jumped metrics). */
  magnitude: number;
}

/**
 * A single per-chapter note in the drift result (sparse commentary).
 *
 * RULE-17 contract parity: mirrors `ChapterNote`.
 */
export interface VoiceDriftChapterNote {
  /** The chapter the note refers to. */
  chapter_id: string;
  /** Short note tied to this chapter's data. */
  note: string;
}

/**
 * The agent's structured longitudinal drift classification for one character.
 *
 * RULE-17 contract parity: mirrors `VoiceDriftResult`
 * (`packages/core/narrare_core/agents/character_voice_drift_types.py`).
 */
export interface VoiceDriftResult {
  /** The single best-fitting longitudinal classification. */
  drift_type: VoiceDriftType;
  /** Float 0.0–1.0 — how confident the classification is. */
  confidence: number;
  /** Concrete observations justifying the classification. */
  longitudinal_reasons: string[];
  /** Sparse per-chapter commentary (only chapters with something concrete). */
  per_chapter_notes: VoiceDriftChapterNote[];
  /** Chapter ids most worth the author's review. Empty when the voice is stable. */
  suggested_attention: string[];
}

/**
 * Graceful "not analysable for drift" signal for one character (RULE-11).
 *
 * RULE-17 contract parity: mirrors `VoiceDriftNoProfile`.
 */
export interface VoiceDriftNoProfile {
  /** The character's stored profile character_id, or "" when no profile at all. */
  character_id: string;
  /** The character's canonical name, or "" when unknown. */
  character_name: string;
  /** Why the character was skipped. */
  reason: VoiceDriftNoProfileReason;
}

/**
 * Per-character longitudinal drift result (display-only — never persisted).
 *
 * Carries the deterministic per-chapter match trend (signal i) + the
 * adjacent-chapter jump points (signal iii) + the aggregate match score +
 * the agent's qualitative classification.
 *
 * RULE-17 contract parity: mirrors `VoiceDriftCharacterResult`.
 */
export interface VoiceDriftCharacterResult {
  /** The character's stored profile character_id. */
  character_id: string;
  /** The character's canonical name (as attributed in the chapter dialogue). */
  character_name: string;
  /** Per-chapter match trend (signal i) — one TrendPoint per speaking chapter. */
  trend: TrendPoint[];
  /** Adjacent-chapter jump points (signal iii). Empty when no metric jumped. */
  jumps: JumpPoint[];
  /** Mean per-chapter match sub-score [0, 100], or null when trend is empty. */
  overall_match_score: number | null;
  /** Drift severity label for `overall_match_score`, or null when unscorable. */
  overall_band: VoiceDriftBand | null;
  /** The agent's qualitative longitudinal classification. */
  drift: VoiceDriftResult;
}

/**
 * Accumulated output of one voice-drift run (analysable + skipped characters).
 *
 * Frontend-only composite of the two per-character stream payloads — the
 * `useCharacterVoiceDrift` hook resolves its SSE stream with this shape.
 */
export interface VoiceDriftRunResult {
  /** Analysable characters (stored profile + voice_metrics + dialogue). */
  results: VoiceDriftCharacterResult[];
  /** Characters that could not be analysed (RULE-11 graceful skips). */
  noProfile: VoiceDriftNoProfile[];
}

// ---------------------------------------------------------------------------
// Request + SSE event types
// ---------------------------------------------------------------------------

/**
 * Request body for `POST /analysis/voice-drift/{novel_id}`.
 *
 * RULE-17 contract parity: mirrors `VoiceDriftRequest`. Omitting both filters
 * (or null/empty) means "analyse every profiled character across every chapter".
 */
export interface VoiceDriftRequest {
  /** Scope to one character by profile.character_id, or null for all. */
  character_id?: string | null;
  /** Specific chapter ids to analyse, or null/empty for all chapters. */
  chapter_ids?: string[] | null;
}

/**
 * One event in a voice-drift SSE stream.
 *
 * RULE-17 contract parity: mirrors `VoiceDriftEvent`. The `event` field
 * discriminates between progress, per-character result, graceful no-profile
 * skip, completion, and error:
 *  - `"progress"` — pipeline status update (carried in `progress`).
 *  - `"character_result"` — carries one character's result in `result`.
 *  - `"no_profile"` — graceful skip for a character that cannot be analysed
 *    (RULE-11); carries the skip detail in `no_profile`.
 *  - `"done"` — terminal success event (`is_final === true`).
 *  - `"error"` — terminal error event; `error` carries the message
 *    (`is_final === true`).
 */
export interface VoiceDriftEvent {
  event?: "progress" | "character_result" | "no_profile" | "done" | "error";
  result?: VoiceDriftCharacterResult | null;
  no_profile?: VoiceDriftNoProfile | null;
  progress?: string | null;
  error?: string | null;
  is_final?: boolean;
}

// ---------------------------------------------------------------------------
// Stream API
// ---------------------------------------------------------------------------

export interface VoiceDriftStreamHandlers {
  /** Called for each `"progress"` event (pipeline status / character count). */
  onProgress?: (message: string) => void;
  /** Called once per analysable character when its `"character_result"` arrives. */
  onResult: (result: VoiceDriftCharacterResult) => void;
  /** Called once per skipped character when its `"no_profile"` event arrives. */
  onNoProfile?: (noProfile: VoiceDriftNoProfile) => void;
  /** Called after the terminal `"done"` event (or stream end). Never after `onError`. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal `"error"` event. */
  onError?: (error: Error) => void;
}

/**
 * Stream a character voice-drift analysis for a novel (ANAL-009 Phase 1).
 *
 * POSTs to `/analysis/voice-drift/{novelId}` with the optional filter body and
 * parses the SSE event stream. The backend emits `"progress"` events, one
 * `"character_result"` per analysable character plus one `"no_profile"` per
 * skipped character, then a `"done"` terminal event and a `data: [DONE]`
 * signal. A terminal `"error"` event surfaces a server-side failure through
 * `onError`.
 *
 * @param novelId   Novel to analyse (URL path parameter).
 * @param body      `{ character_id?, chapter_ids? }` — null/omitted = all.
 * @param handlers  Callbacks for progress, per-character results, no-profile skips, completion, errors.
 * @param signal    Optional abort signal to cancel the in-flight stream.
 */
export async function streamVoiceDrift(
  novelId: string,
  body: VoiceDriftRequest,
  handlers: VoiceDriftStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<VoiceDriftEvent>({
    url: `/analysis/voice-drift/${novelId}`,
    method: "POST",
    body,
    signal,
    onChunk: (event) => {
      // A terminal server-side error event: surface it and stop.
      if (event.event === "error" || event.error) {
        if (isComplete) return;
        isComplete = true;
        handlers.onError?.(new Error(event.error ?? "Voice-drift analysis failed"));
        return;
      }

      if (event.event === "progress" && event.progress) {
        handlers.onProgress?.(event.progress);
        return;
      }

      if (event.event === "character_result" && event.result) {
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
