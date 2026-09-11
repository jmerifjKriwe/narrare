/**
 * Chat API (ADR-024 Free-Form Chat) — SSE-based streaming chat.
 *
 * Uses the shared `connectSSE` transport (streaming.ts) consistent with
 * coauthor.ts, generation-streams.ts, and suggest.ts.
 */

import type { ChatDoneEvent, ChatMetaEvent } from "@/types";
import { connectSSE, type SSEStreamError } from "./streaming";

// ---------------------------------------------------------------------------
// SSE event shape — matches backend chat/router.py event_stream()
// ---------------------------------------------------------------------------

/** Union of all SSE event types the chat endpoint emits. */
interface ChatStreamEvent {
  type?: "meta" | "token" | "done";
  /** meta event fields */
  conversation_id?: string;
  request_id?: string;
  /** token event fields */
  text?: string;
  /** done event fields */
  usage?: ChatDoneEvent["usage"];
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const chatApi = {
  /**
   * Stream a free-form chat message via SSE.
   *
   * POST /api/v1/chat with SSE response.
   * Event types: meta, token, done.
   *
   * `project_id` may be null for project-less chat (NOTES-001 global notes);
   * `note_id` optionally attaches a scratchpad note as runtime context.
   */
  streamChat: async (
    body: {
      project_id?: string | null;
      message: string;
      conversation_id?: string | null;
      note_id?: string | null;
    },
    callbacks: {
      onMeta: (meta: ChatMetaEvent) => void;
      onToken: (text: string) => void;
      onDone: (done: ChatDoneEvent) => void;
      onError: (error: Error) => void;
    },
    signal?: AbortSignal,
  ): Promise<void> => {
    await connectSSE<ChatStreamEvent>({
      url: "/chat",
      method: "POST",
      body,
      signal,
      onChunk: (event) => {
        if (event.type === "meta" || event.conversation_id) {
          callbacks.onMeta({
            conversation_id: event.conversation_id ?? "",
            request_id: event.request_id ?? "",
          });
        } else if (event.type === "token" && event.text !== undefined) {
          callbacks.onToken(event.text);
        } else if (event.type === "done") {
          callbacks.onDone({
            type: "done",
            usage: event.usage ?? { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
          });
        }
      },
      onError: (error: SSEStreamError) => {
        callbacks.onError(error);
      },
    });
  },
};
