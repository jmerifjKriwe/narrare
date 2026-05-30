/**
 * Typed API client for WRITE-006 Co-Author Mode.
 *
 * Covers: SSE streaming of AI revision suggestions with per-change diffs,
 * focus area selection, and accept/reject lifecycle.
 *
 * Pattern: matches streamRewrite() in generation.ts exactly.
 * SSE Event Stream:
 *   1. {"type": "context_meta", ...}
 *   2. {"text": "revised text chunk..."}
 *   3. {"text": "...final text", "is_final": true, "usage": {...}, "changes": [...]}
 *   4. data: [DONE]
 */

import type { TokenUsage } from "@/types";
import { getAccessToken } from "./client";

// ---------------------------------------------------------------------------
// Types — field names match backend schemas exactly (RULE-17)
// ---------------------------------------------------------------------------

export type CoAuthorFocus = "word_choice" | "sentence" | "dialogue" | "description";

export interface CoAuthorRequest {
  selection_text: string;
  context_before?: string;
  context_after?: string;
  focus: CoAuthorFocus[];
  tone?: string;
  language?: string;
}

export interface ChangeDetail {
  id: string;
  change_type: string; // "word_choice" | "sentence" | "dialogue" | "description"
  original_text: string;
  revised_text: string;
  index: number;
}

export interface CoAuthorRevision {
  original: string;
  revised: string;
  changes: ChangeDetail[];
  reasoning: string;
}

/** SSE event shape for the Co-Author stream. */
export interface CoAuthorStreamEvent {
  type?: "context_meta";
  text?: string;
  is_final?: boolean;
  usage?: TokenUsage;
  changes?: ChangeDetail[];
  total_changes?: number;
  has_changes?: boolean;
  reasoning?: string;
}

// ---------------------------------------------------------------------------
// SSE Streaming
// ---------------------------------------------------------------------------

/**
 * Stream co-author suggestions via SSE from POST /co-author endpoint.
 *
 * Accumulates streaming text chunks and emits the full revision on completion.
 * Follows the exact pattern of streamRewrite() in generation.ts.
 */
export async function streamCoAuthor(
  chapterId: string,
  novelId: string,
  request: CoAuthorRequest,
  callbacks: {
    onContextMeta?: (meta: Record<string, unknown>) => void;
    onChunk: (text: string) => void;
    onComplete: (revision: CoAuthorRevision) => void;
    onError?: (error: Error) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  try {
    const response = await fetch(
      `/api/v1/writing/chapters/${chapterId}/co-author?novel_id=${novelId}`,
      {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify(request),
        signal,
      },
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";
    let accumulatedText = "";
    let finalChanges: ChangeDetail[] = [];
    let finalReasoning = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            // Stream complete — emit revision with accumulated data
            callbacks.onComplete({
              original: request.selection_text,
              revised: accumulatedText,
              changes: finalChanges,
              reasoning: finalReasoning,
            });
            return;
          }
          try {
            const parsed = JSON.parse(data) as CoAuthorStreamEvent;

            // Context metadata event (CR-07)
            if (parsed.type === "context_meta") {
              callbacks.onContextMeta?.(parsed as Record<string, unknown>);
              continue;
            }

            // Streaming text chunk
            if (parsed.text) {
              accumulatedText += parsed.text;
              callbacks.onChunk(parsed.text);
            }

            // Final event — contains changes data
            if (parsed.is_final) {
              finalChanges = parsed.changes ?? [];
              finalReasoning = parsed.reasoning ?? "";

              // Use the final event's text as the definitive revised text
              // (it may differ slightly from accumulated chunks)
              if (parsed.text) {
                accumulatedText = parsed.text;
              }
            }
          } catch {
            /* skip malformed JSON */
          }
        }
      }
    }

    // Stream ended without [DONE] — still emit what we have
    callbacks.onComplete({
      original: request.selection_text,
      revised: accumulatedText,
      changes: finalChanges,
      reasoning: finalReasoning,
    });
  } catch (error) {
    const isAbort =
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError");
    if (isAbort) return;
    callbacks.onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}
