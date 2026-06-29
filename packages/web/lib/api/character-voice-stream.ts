/**
 * SSE-backed character-voice analysis stream (ANAL-008).
 *
 * Connects to the backend `POST /api/v1/analysis/character-voice/{novel_id}`
 * SSE endpoint and parses the structured `CharacterVoiceStreamEvent` stream.
 *
 * Mirrors the established analysis stream pattern ({@link ./coreference-stream.ts}):
 * the backend emits a type-discriminated event stream — `"progress"`,
 * one `"result"` per profiled character, then a terminal `"done"` (or
 * `"error"`) event — followed by a `data: [DONE]` sentinel. Unlike coreference
 * (a single result event), character-voice emits MULTIPLE per-character
 * results, so the caller's `onResult` fires once per character.
 *
 * RULE-17 contract parity: the types below mirror the Pydantic models in
 * `apps/api/narrare/analysis/schemas_character_voice.py` and the Layer-0
 * `VoiceAnalysis` / `VoiceMetrics` in
 * `packages/core/narrare_core/kb/schemas/character.py` exactly (field names,
 * snake_case, optionality). The backend is the SSOT.
 *
 * The transport/parser (auth headers, URL prefixing, SSE line parsing,
 * connect timeout, abort handling) lives in {@link ./streaming.ts}.
 *
 * @module character-voice-stream
 */

import { connectSSE } from "./streaming";

// ---------------------------------------------------------------------------
// Result payload types (mirror backend schemas — RULE-17 contract parity)
// ---------------------------------------------------------------------------

/**
 * Deterministic numeric voice metrics — for ANAL-009 drift / WRITE-010
 * checking. NEVER rendered into generation. Populated by the deterministic
 * `VoiceMetricsAnalyzer`, never by the LLM agent.
 *
 * RULE-17 contract parity: mirrors `VoiceMetrics` (all fields optional).
 */
export interface VoiceMetrics {
  avg_sentence_length?: number | null;
  sentence_length_std?: number | null;
  type_token_ratio?: number | null;
  avg_syllables_per_word?: number | null;
  contraction_rate?: number | null;
  /** n-gram → rate. */
  verbal_tic_frequency?: Record<string, number> | null;
  /** habit → rate. */
  punctuation_profile?: Record<string, number> | null;
}

/**
 * Machine-derived character voice profile (ADR-055 Decision 1).
 *
 * The descriptive group (formality … voice_examples) renders into generation;
 * the metric group (`voice_metrics`) is comparison-only and never reaches
 * generation.
 *
 * RULE-17 contract parity: mirrors `VoiceAnalysis` (all fields optional).
 */
export interface VoiceAnalysis {
  /** 0.0 casual – 1.0 formal. */
  formality?: number | null;
  /** simple | moderate | complex. */
  vocabulary_level?: string | null;
  /** short | medium | long | varied. */
  sentence_profile?: string | null;
  /** restricted | moderate | expressive. */
  emotional_range?: string | null;
  /** Intrinsic markers that aid generation. */
  cultural_regional_markers?: string | null;
  /** Curated representative quotes. */
  voice_examples?: string[] | null;
  /** Deterministic comparison metrics (never rendered into generation). */
  voice_metrics?: VoiceMetrics | null;
}

/**
 * Per-character voice profiling result.
 *
 * Carries the persisted `voice_analysis` (the summary written to the KB
 * `speech.voice_analysis`) plus the per-run `distinctiveness_notes` — a
 * display-only comparison artifact that is surfaced to the UI but is NOT
 * persisted on the character profile (ADR-055 Decision 1 persistence scope).
 *
 * RULE-17 contract parity: mirrors `CharacterVoiceResult`.
 */
export interface CharacterVoiceResult {
  /** The character's canonical name (matched to a KB entry when one exists). */
  character_name: string;
  /** Persisted voice-analysis summary, or null when no KB entry was found. */
  voice_analysis?: VoiceAnalysis | null;
  /**
   * Relative, per-run comparison vs the other characters analysed in the same
   * invocation. DISPLAY-ONLY — never persisted (ADR-055 Decision 1).
   */
  distinctiveness_notes?: string | null;
  /** KB entry id the analysis was persisted onto, or null when none exists. */
  kb_entry_id?: string | null;
}

// ---------------------------------------------------------------------------
// Request + SSE event types
// ---------------------------------------------------------------------------

/**
 * Request body for `POST /analysis/character-voice/{novel_id}`.
 *
 * RULE-17 contract parity: mirrors `CharacterVoiceRequest`. Omitting
 * `chapter_ids` (or null) means "analyse every chapter in the novel".
 */
export interface CharacterVoiceRequest {
  chapter_ids?: string[] | null;
}

/**
 * One event in a character-voice SSE stream.
 *
 * RULE-17 contract parity: mirrors `CharacterVoiceStreamEvent`. The `event`
 * field discriminates between progress, per-character result, completion, and
 * error:
 *  - `"progress"` — pipeline status update (carried in `progress`).
 *  - `"result"` — carries one character's result in `result` (one per character).
 *  - `"done"` — terminal success event (`is_final === true`).
 *  - `"error"` — terminal error event; `error` carries the message
 *    (`is_final === true`).
 */
export interface CharacterVoiceStreamEvent {
  event?: "progress" | "result" | "done" | "error";
  result?: CharacterVoiceResult | null;
  progress?: string | null;
  error?: string | null;
  is_final?: boolean;
}

// ---------------------------------------------------------------------------
// Stream API
// ---------------------------------------------------------------------------

export interface CharacterVoiceStreamHandlers {
  /** Called for each `"progress"` event (pipeline status / character count). */
  onProgress?: (message: string) => void;
  /** Called once per profiled character when its `"result"` event arrives. */
  onResult: (result: CharacterVoiceResult) => void;
  /** Called after the terminal `"done"` event (or stream end). Never after `onError`. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal `"error"` event. */
  onError?: (error: Error) => void;
}

/**
 * Stream a character-voice analysis for a novel (ANAL-008).
 *
 * POSTs to `/analysis/character-voice/{novelId}` with the `chapter_ids` body
 * and parses the SSE event stream. The backend emits `"progress"` events,
 * one `"result"` per profiled character, then a `"done"` terminal event and a
 * `data: [DONE]` signal. A terminal `"error"` event surfaces a server-side
 * failure through `onError`.
 *
 * @param novelId   Novel to analyse (URL path parameter).
 * @param body      `{ chapter_ids }` — null/omitted analyses every chapter.
 * @param handlers  Callbacks for progress, per-character results, completion, errors.
 * @param signal    Optional abort signal to cancel the in-flight stream.
 */
export async function streamCharacterVoice(
  novelId: string,
  body: CharacterVoiceRequest,
  handlers: CharacterVoiceStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<CharacterVoiceStreamEvent>({
    url: `/analysis/character-voice/${novelId}`,
    method: "POST",
    body,
    signal,
    onChunk: (event) => {
      // A terminal server-side error event: surface it and stop.
      if (event.event === "error" || event.error) {
        if (isComplete) return;
        isComplete = true;
        handlers.onError?.(new Error(event.error ?? "Character-voice analysis failed"));
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
