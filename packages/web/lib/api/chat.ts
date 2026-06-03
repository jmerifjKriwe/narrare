/**
 * Chat API (ADR-024 Free-Form Chat) — SSE-based streaming chat.
 */

import type { ChatDoneEvent, ChatMetaEvent } from "@/types";
import { getAccessToken } from "./core";

export const chatApi = {
  /**
   * Stream a free-form chat message via SSE.
   *
   * POST /api/v1/chat with SSE response.
   * Event types: meta, token, done.
   * Follows the same SSE pattern as coauthor.ts / generation.ts.
   */
  streamChat: async (
    body: { project_id: string; message: string; conversation_id?: string | null },
    callbacks: {
      onMeta: (meta: ChatMetaEvent) => void;
      onToken: (text: string) => void;
      onDone: (done: ChatDoneEvent) => void;
      onError: (error: Error) => void;
    },
    signal?: AbortSignal,
  ): Promise<void> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    };
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    try {
      const response = await fetch("/api/v1/chat", {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify(body),
        signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          // Track SSE event type
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
            continue;
          }

          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") return;

            try {
              const parsed = JSON.parse(data) as Record<string, unknown>;

              if (currentEvent === "meta" || parsed.conversation_id) {
                callbacks.onMeta(parsed as unknown as ChatMetaEvent);
              } else if (currentEvent === "token" || parsed.type === "token") {
                callbacks.onToken(parsed.text as string);
              } else if (currentEvent === "done" || parsed.type === "done") {
                callbacks.onDone(parsed as unknown as ChatDoneEvent);
              }
            } catch {
              // Skip malformed JSON
            }

            currentEvent = "";
          }
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      callbacks.onError(error instanceof Error ? error : new Error(String(error)));
    }
  },
};
