/**
 * SSE-backed story-direction suggestions for Writer's Unblock (WRITE-009).
 *
 * Connects to the backend `POST /api/v1/writing/story-suggest/{novel_id}`
 * SSE endpoint and parses the structured `StorySuggestStreamEvent` stream.
 *
 * Unlike the text-accumulating streams in {@link ./generation-streams.ts},
 * this endpoint emits a single `"suggestions"` event carrying the full
 * suggestion list, followed by a terminal `"done"` (or `"error"`) event.
 * There is no incremental text to accumulate — the entire result arrives in
 * one event — so this module only translates the discriminated event stream
 * into simple callbacks.
 *
 * The transport/parser (auth headers, URL prefixing, SSE line parsing,
 * connect timeout, abort handling) lives in {@link ./streaming.ts}.
 */

import { connectSSE, type SSEStreamError } from "./streaming";

/**
 * Category of a story-direction suggestion.
 *
 * RULE-17 contract parity: these are the documented values of the serialized
 * enum `narrare_core.agents.story_suggest_types.StorySuggestion.type`, surfaced
 * as a plain `str` in the API response. The backend is the SSOT; this union is
 * a client-side convenience for type-safe UI rendering and i18n key lookup
 * (`studio.unblock.suggestionType.*`). Unknown values must still be tolerated
 * at runtime, so consumers should fall back gracefully.
 */
export type StorySuggestionType =
  | "plot_development"
  | "character_moment"
  | "dialogue_option"
  | "world_detail"
  | "stylistic_alternative";

/**
 * A single story-direction suggestion.
 *
 * RULE-17 contract parity: mirrors the Python `StorySuggestionResponse`
 * in `apps/api/narrare/writing/schemas_story_suggest.py` exactly (field names,
 * optionality). Backend is the SSOT.
 */
export interface StorySuggestion {
  type: StorySuggestionType | string;
  title: string;
  description: string;
  connection: string;
}

/**
 * Request body for the story-suggest endpoint.
 *
 * RULE-17 contract parity: mirrors `StorySuggestRequest` — `novel_id` is
 * required but supplied via the URL path parameter, not the body, so it is
 * omitted here and only the optional fields are sent in the JSON body.
 * `author_instructions` is capped at 2000 characters server-side.
 */
export interface StorySuggestRequestBody {
  chapter_id?: string;
  author_instructions?: string;
}

/**
 * One event in a story-suggest SSE stream.
 *
 * RULE-17 contract parity: mirrors the Python `StorySuggestStreamEvent`.
 * The `event` field discriminates between suggestion data, completion, and
 * error events:
 *  - `"suggestions"` — carries the full suggestion list in `suggestions`.
 *  - `"done"` — terminal success event (`is_final === true`).
 *  - `"error"` — terminal error event; `error` carries the message
 *    (`is_final === true`).
 */
export interface StorySuggestStreamEvent {
  event?: "suggestions" | "done" | "error";
  suggestions?: StorySuggestion[] | null;
  error?: string | null;
  is_final?: boolean;
}

interface StreamCallbacks {
  onError?: (error: Error) => void;
}

function reportStreamError(callbacks: StreamCallbacks, error: SSEStreamError): void {
  callbacks.onError?.(error);
}

export interface StorySuggestStreamHandlers {
  /** Called once with the full suggestion list when the `"suggestions"` event arrives. */
  onSuggestions: (suggestions: StorySuggestion[]) => void;
  /** Called after the terminal `"done"` event (or stream end). Never called after `onError`. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal `"error"` event. */
  onError?: (error: Error) => void;
}

/**
 * Stream story-direction suggestions for a novel (Writer's Unblock).
 *
 * POSTs to `/writing/story-suggest/{novelId}` and parses the SSE event
 * stream. The backend emits at most one `"suggestions"` event (with the
 * 3-5 distinct suggestions) followed by a `"done"` terminal event, then a
 * `data: [DONE]` signal. A terminal `"error"` event surfaces a server-side
 * failure through `onError`.
 *
 * @param novelId     Novel to generate suggestions for (URL path parameter).
 * @param body        Optional request body (`chapter_id`, `author_instructions`).
 * @param handlers    Callbacks for suggestions, completion, and errors.
 * @param signal      Optional abort signal to cancel the in-flight stream.
 */
export async function streamStorySuggestions(
  novelId: string,
  body: StorySuggestRequestBody,
  handlers: StorySuggestStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<StorySuggestStreamEvent>({
    url: `/writing/story-suggest/${novelId}`,
    method: "POST",
    body,
    signal,
    onChunk: (event) => {
      // A terminal server-side error event: surface it and stop.
      if (event.event === "error" || event.error) {
        const message = event.error ?? "Story suggestion failed";
        isComplete = true;
        handlers.onError?.(new Error(message));
        return;
      }

      if (event.event === "suggestions" && event.suggestions) {
        handlers.onSuggestions(event.suggestions);
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
