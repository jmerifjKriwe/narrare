/**
 * SSE-backed coreference analysis stream (ANAL-005).
 *
 * Connects to the backend `POST /api/v1/analysis/coreference/{chapter_id}`
 * SSE endpoint and parses the structured `CoreferenceStreamEvent` stream.
 *
 * Mirrors the writing module's story-suggest stream pattern
 * ({@link ./story-suggest-stream.ts}): the backend emits a single `"result"`
 * event carrying the full coreference analysis, followed by a terminal
 * `"done"` (or `"error"`) event. There is no incremental accumulation — the
 * entire result arrives in one event — so this module only translates the
 * discriminated event stream into simple callbacks.
 *
 * RULE-17 contract parity: the types below mirror the Pydantic models in
 * `apps/api/narrare/analysis/schemas_coreference.py` exactly (field names,
 * snake_case, optionality). The backend is the SSOT.
 *
 * The transport/parser (auth headers, URL prefixing, SSE line parsing,
 * connect timeout, abort handling) lives in {@link ./streaming.ts}.
 */

import { connectSSE, type SSEStreamError } from "./streaming";

/**
 * A single pronoun resolved to its referent.
 *
 * RULE-17 contract parity: mirrors `PronounResolutionResponse`.
 */
export interface PronounResolution {
  /** Pronoun token as it appears in the text (e.g. "he", "she", "their"). */
  pronoun: string;
  /** Character offset of the pronoun within the analysed text. */
  position: number;
  /** Character name the pronoun refers to, or "" when unresolved/ambiguous. */
  referent: string;
  /** Resolution confidence (0.0-1.0). */
  confidence: number;
  /** True when multiple referents are plausible. */
  is_ambiguous: boolean;
}

/**
 * A character and the positions where it is mentioned.
 *
 * RULE-17 contract parity: mirrors `CharacterMentionResponse`.
 */
export interface CharacterMention {
  /** The character's name (or most common reference form). */
  character_name: string;
  /** Character offsets within the analysed text where the character is referred to. */
  mentions: number[];
  /** True when this character appears to be the POV character for the passage. */
  is_pov: boolean;
}

/**
 * Full coreference analysis for a chapter.
 *
 * RULE-17 contract parity: mirrors `CoreferenceResponse`.
 */
export interface CoreferenceResult {
  /** The chapter that was analysed. */
  chapter_id: string;
  /** Overall referential clarity of the passage (0-100). Higher is clearer. */
  clarity_score: number;
  /** Brief free-text assessment of referential clarity (1-3 sentences). */
  summary: string;
  /** Per-pronoun resolutions to their referents. */
  resolutions: PronounResolution[];
  /** Per-character mention tracking. */
  character_mentions: CharacterMention[];
}

/**
 * One event in a coreference SSE stream.
 *
 * RULE-17 contract parity: mirrors `CoreferenceStreamEvent`. The `event`
 * field discriminates between result data, completion, and error events:
 *  - `"result"` — carries the full analysis in `result`.
 *  - `"done"` — terminal success event (`is_final === true`).
 *  - `"error"` — terminal error event; `error` carries the message
 *    (`is_final === true`).
 */
export interface CoreferenceStreamEvent {
  event?: "result" | "done" | "error";
  result?: CoreferenceResult | null;
  error?: string | null;
  is_final?: boolean;
}

interface StreamCallbacks {
  onError?: (error: Error) => void;
}

function reportStreamError(callbacks: StreamCallbacks, error: SSEStreamError): void {
  callbacks.onError?.(error);
}

export interface CoreferenceStreamHandlers {
  /** Called once with the full analysis when the `"result"` event arrives. */
  onResult: (result: CoreferenceResult) => void;
  /** Called after the terminal `"done"` event (or stream end). Never called after `onError`. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal `"error"` event. */
  onError?: (error: Error) => void;
}

/**
 * Stream a coreference analysis for a chapter (ANAL-005).
 *
 * POSTs to `/analysis/coreference/{chapterId}` and parses the SSE event
 * stream. The backend emits at most one `"result"` event (with the full
 * analysis) followed by a `"done"` terminal event, then a `data: [DONE]`
 * signal. A terminal `"error"` event surfaces a server-side failure through
 * `onError`.
 *
 * @param chapterId  Chapter to analyse (URL path parameter).
 * @param handlers   Callbacks for the result, completion, and errors.
 * @param signal     Optional abort signal to cancel the in-flight stream.
 */
export async function streamCoreference(
  chapterId: string,
  handlers: CoreferenceStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<CoreferenceStreamEvent>({
    url: `/analysis/coreference/${chapterId}`,
    method: "POST",
    signal,
    onChunk: (event) => {
      // A terminal server-side error event: surface it and stop.
      if (event.event === "error" || event.error) {
        const message = event.error ?? "Coreference analysis failed";
        isComplete = true;
        handlers.onError?.(new Error(message));
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
    onError: (error) => reportStreamError(handlers, error),
  });
}
