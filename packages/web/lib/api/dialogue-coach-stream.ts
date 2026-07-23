/**
 * SSE-backed Dialogue Coach stream (ADR-069 D17 / Phase 5 step 22).
 *
 * Connects to POST /api/v1/ai-assist/dialogue-coach/{chapter_id} and parses
 * the typed `DialogueCoachStreamEvent` stream. Mirrors the established analysis
 * stream pattern ({@link ./character-voice-stream.ts}): the backend emits a
 * type-discriminated event stream — one "progress", one "result" carrying the
 * full DialogueCoachResponse, then a terminal "done" (or "error"), followed by
 * a `data: [DONE]` sentinel.
 *
 * RULE-17 contract parity: types below mirror ai_assist/schemas.py exactly.
 * The transport (auth, SSE line parsing, connect timeout, abort) lives in
 * {@link ./streaming.ts}.
 *
 * @module dialogue-coach-stream
 */

import type {
  DialogueCoachRequest,
  DialogueCoachResponse,
  DialogueCoachStreamEvent,
} from "@/types";
import { connectSSE } from "./streaming";

export interface DialogueCoachStreamHandlers {
  /** Called for each "progress" event. */
  onProgress?: (message: string) => void;
  /** Called once with the full result when the "result" event arrives. */
  onResult: (result: DialogueCoachResponse) => void;
  /** Called after the terminal "done" event. Never after onError. */
  onComplete?: () => void;
  /** Called on transport failure or a terminal "error" event. */
  onError?: (error: Error) => void;
}

/**
 * Stream a dialogue-coach analysis for a chapter selection.
 *
 * @param chapterId  Chapter the selection belongs to (URL path param).
 * @param body       `{ selection_text, mode }` (RULE-17 DialogueCoachRequest).
 * @param handlers   Progress / result / complete / error callbacks.
 * @param signal     Optional abort signal (provided by useAIOperation).
 */
export async function streamDialogueCoach(
  chapterId: string,
  body: DialogueCoachRequest,
  handlers: DialogueCoachStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let isComplete = false;

  function complete(): void {
    if (isComplete) return;
    isComplete = true;
    handlers.onComplete?.();
  }

  await connectSSE<DialogueCoachStreamEvent>({
    url: `/ai-assist/dialogue-coach/${chapterId}`,
    method: "POST",
    body,
    signal,
    onChunk: (event) => {
      if (event.event === "error" || event.error) {
        if (isComplete) return;
        isComplete = true;
        handlers.onError?.(new Error(event.error ?? "Dialogue coach failed"));
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
      if (event.event === "done" || event.is_final) complete();
    },
    onComplete: complete,
    onError: (error) => {
      if (isComplete) return;
      isComplete = true;
      handlers.onError?.(error);
    },
  });
}
