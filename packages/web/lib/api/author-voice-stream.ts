/**
 * SSE-backed author-voice analysis stream (ANAL-007 / ADR-074).
 *
 * Connects to the backend `POST /api/v1/analysis/author-voice/{novel_id}`
 * SSE endpoint and parses the structured `AuthorVoiceStreamEvent` stream.
 *
 * Mirrors the established analysis stream pattern
 * ({@link ./character-voice-stream.ts}, {@link ./coreference-stream.ts}):
 * the backend emits a type-discriminated event stream — `"progress"`, ONE
 * `"result"` event carrying the assembled profile (author voice is one
 * profile per novel, not per-character), then a terminal `"done"` (or
 * `"error"`) event — followed by a `data: [DONE]` sentinel.
 *
 * RULE-17 contract parity: the types below mirror the Pydantic models in
 * `apps/api/narrare/analysis/schemas_author_voice.py` and the Core
 * `AuthorVoiceProfile` / `AuthorMetrics` in
 * `packages/core/narrare_core/profiles/author_voice.py` +
 * `packages/core/narrare_core/analysis/author_metrics.py` exactly (field
 * names, snake_case, optionality). The voice-generic `VoiceAnalysis` /
 * `VoiceMetrics` are shared with character voice (ADR-074 type-reuse). The
 * backend is the SSOT.
 *
 * The transport/parser (auth headers, URL prefixing, SSE line parsing,
 * connect timeout, abort handling) lives in {@link ./streaming.ts}.
 *
 * @module author-voice-stream
 */

import { connectSSE } from "./streaming";

// ---------------------------------------------------------------------------
// Result payload types (mirror backend schemas — RULE-17 contract parity)
// ---------------------------------------------------------------------------

/**
 * Deterministic voice-GENERIC metrics — for ANAL-009 Phase 2 author drift.
 * NEVER rendered into generation. Computed by `VoiceMetricsAnalyzer.analyze_text`
 * over the narrator's full prose; populated deterministically, never by the LLM.
 *
 * RULE-17 contract parity: mirrors `VoiceMetrics` (all fields optional). Same
 * type as character voice (ADR-074 type-reuse) — duplicated here only because
 * the TS mirrors live next to their stream client (no shared TS voice module
 * exists; the Python types are SSOT).
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
 * Voice-GENERIC descriptive group (renders into generation) + nested metric
 * block (comparison-only). Same shape as character voice.
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
  /** Curated representative quotes (voice-generic slot; author voice uses author_examples). */
  voice_examples?: string[] | null;
  /** Deterministic comparison metrics (never rendered into generation). */
  voice_metrics?: VoiceMetrics | null;
}

/**
 * Author-specific PROSE-LEVEL metrics — comparison ONLY (ANAL-009 Phase 2
 * author drift). NEVER rendered into generation. Computed deterministically
 * by `AuthorMetricsAnalyzer`. Provisional set (ADR-074).
 *
 * RULE-17 contract parity: mirrors `AuthorMetrics` (all fields `float | None`,
 * 0.0–1.0).
 */
export interface AuthorMetrics {
  /** 0.0–1.0 (quoted words / total words). */
  dialogue_ratio?: number | null;
  /** 0.0–1.0 sparse..rich (modifier density proxy). */
  description_density?: number | null;
  /** 0.0–1.0 action..introspection proxy. */
  action_introspection_ratio?: number | null;
  /** 0.0–1.0 (simile-cue proxy — PROVISIONAL). */
  metaphor_density?: number | null;
}

/**
 * Machine-derived author-voice profile (ANAL-007 / ADR-074).
 *
 * Persisted as `ProjectSettings.author_voice` JSONB. Novel-scoped (one profile
 * per novel). The descriptive group (`voice_analysis` descriptive fields +
 * `author_examples`) renders into `{{author_voice}}` by the Core
 * `render_author_voice_for_generation`; the metric groups
 * (`voice_analysis.voice_metrics` + `author_metrics`) NEVER reach generation.
 *
 * The descriptive/metric boundary is enforced at the Core consumer contract,
 * NOT at the wire schema: the SSE `result` carries the FULL profile so the
 * panel can display the composition metrics (Phase 2B drift comparison aid).
 *
 * RULE-17 contract parity: mirrors `AuthorVoiceProfile`.
 */
export interface AuthorVoiceProfile {
  /** Voice-generic descriptive block (also carries voice-generic voice_metrics). */
  voice_analysis?: VoiceAnalysis | null;
  /** Author-specific curated representative prose passages. */
  author_examples?: string[] | null;
  /** Author-specific prose-level metrics. Comparison-only. */
  author_metrics?: AuthorMetrics | null;
  /** ISO timestamp of the last profile build (freshness signal). */
  updated_at?: string | null;
  /** Freshness flag (mirrors character-voice profiles/_freshness). */
  is_fresh?: boolean;
}

/**
 * Author-voice profiling result (one profile per novel).
 *
 * Carries the persisted `AuthorVoiceProfile`. `profile` is `null` only on the
 * empty-chapters graceful path (no profile built).
 *
 * RULE-17 contract parity: mirrors `AuthorVoiceResult`.
 */
export interface AuthorVoiceResult {
  /** The novel the profile belongs to (str for JSON safety). */
  novel_id?: string;
  /** The assembled + persisted author-voice profile, or null when none was built. */
  profile?: AuthorVoiceProfile | null;
}

// ---------------------------------------------------------------------------
// Request + SSE event types
// ---------------------------------------------------------------------------

/**
 * Request body for `POST /analysis/author-voice/{novel_id}`.
 *
 * RULE-17 contract parity: mirrors `AuthorVoiceRequest`. Omitting
 * `chapter_ids` (or null/empty) means "analyse every chapter in the novel".
 */
export interface AuthorVoiceRequest {
  chapter_ids?: string[] | null;
}

/**
 * One event in an author-voice SSE stream.
 *
 * RULE-17 contract parity: mirrors `AuthorVoiceStreamEvent`. The `event`
 * field discriminates between progress, the single result, completion, and
 * error:
 *  - `"progress"` — pipeline status update (carried in `progress`).
 *  - `"result"` — carries the assembled profile in `result` (ONE per run).
 *  - `"done"` — terminal success event (`is_final === true`).
 *  - `"error"` — terminal error event; `error` carries the message
 *    (`is_final === true`).
 */
export interface AuthorVoiceStreamEvent {
  event?: "progress" | "result" | "done" | "error";
  result?: AuthorVoiceResult | null;
  progress?: string | null;
  error?: string | null;
  is_final?: boolean;
}

// ---------------------------------------------------------------------------
// Stream API
// ---------------------------------------------------------------------------

export interface AuthorVoiceStreamHandlers {
  /** Called for each `"progress"` event (pipeline status / chapter count). */
  onProgress?: (message: string) => void;
  /** Called once with the assembled profile when the `"result"` event arrives. */
  onResult: (result: AuthorVoiceResult) => void;
  /** Called after the terminal `"done"` event (or stream end). Never after `onError`. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal `"error"` event. */
  onError?: (error: Error) => void;
}

/**
 * Stream an author-voice analysis for a novel (ANAL-007).
 *
 * POSTs to `/analysis/author-voice/{novelId}` with the `chapter_ids` body
 * and parses the SSE event stream. The backend emits `"progress"` events,
 * ONE `"result"` event carrying the assembled profile, then a `"done"`
 * terminal event and a `data: [DONE]` signal. A terminal `"error"` event
 * surfaces a server-side failure through `onError`. The backend auto-saves
 * the profile to `ProjectSettings.author_voice` on successful analysis.
 *
 * @param novelId   Novel to analyse (URL path parameter).
 * @param body      `{ chapter_ids }` — null/omitted/empty analyses every chapter.
 * @param handlers  Callbacks for progress, the single result, completion, errors.
 * @param signal    Optional abort signal to cancel the in-flight stream.
 */
export async function streamAuthorVoice(
  novelId: string,
  body: AuthorVoiceRequest,
  handlers: AuthorVoiceStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<AuthorVoiceStreamEvent>({
    url: `/analysis/author-voice/${novelId}`,
    method: "POST",
    body,
    signal,
    onChunk: (event) => {
      // A terminal server-side error event: surface it and stop.
      if (event.event === "error" || event.error) {
        if (isComplete) return;
        isComplete = true;
        handlers.onError?.(new Error(event.error ?? "Author-voice analysis failed"));
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
