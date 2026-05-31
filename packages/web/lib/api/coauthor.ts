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
  /** Correlation ID for apply/feedback — backend-generated UUID from SSE final event. */
  request_id?: string;
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
  /** Backend-generated generation request ID for apply/feedback correlation. */
  request_id?: string;
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
    let finalRequestId: string | undefined;
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
              request_id: finalRequestId,
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

            // Final event — contains changes data + optional request_id
            if (parsed.is_final) {
              finalChanges = parsed.changes ?? [];
              finalReasoning = parsed.reasoning ?? "";
              finalRequestId = parsed.request_id;

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
      request_id: finalRequestId,
    });
  } catch (error) {
    const isAbort =
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError");
    if (isAbort) return;
    callbacks.onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}

// ---------------------------------------------------------------------------
// Apply & Feedback API — stateless text-segment-based partial apply (SET-005)
// ---------------------------------------------------------------------------

/**
 * Text segment pair for a single change — used in apply and feedback requests.
 * Field names MUST match backend schemas exactly (RULE-17).
 */
export interface TextChange {
  original_text: string;
  revised_text: string;
}

/**
 * Apply selected changes to chapter content.
 * POST /api/v1/writing/chapters/{chapterId}/co-author/apply
 *
 * The apply endpoint reconstructs chapter text from `original` + `accepted`
 * segments (stateless — no change IDs needed).  `request_id` enables optional
 * feedback tracking when the backend exposes it via SSE events.
 */
export interface ApplyChangesRequest {
  request_id: string;
  original: string;
  accepted: TextChange[];
  rejected: TextChange[];
}

/**
 * Per-change feedback for preference learning (LEARN-001).
 */
export interface ChangeFeedback {
  change_id: string;
  action: "accepted" | "rejected";
  focus: string;
  original: string;
  revised: string;
}

/**
 * Batch feedback request for co-author changes (LEARN-001).
 * POST /api/v1/writing/chapters/{chapterId}/co-author/feedback
 */
export interface CoAuthorFeedbackRequest {
  request_id: string;
  feedback: ChangeFeedback[];
}

/**
 * Apply accepted co-author changes to chapter content via the backend API.
 *
 * Returns the updated chapter with reconstructed content.  The `request_id`
 * is a client-generated UUID for feedback correlation; if the backend's
 * GenerationRequest row isn't found, feedback tracking silently degrades
 * but text reconstruction still works correctly.
 */
export async function applyChanges(
  chapterId: string,
  novelId: string,
  request: ApplyChangesRequest,
): Promise<{ id: string; content: string }> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(
    `/api/v1/writing/chapters/${chapterId}/co-author/apply?novel_id=${novelId}`,
    {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify(request),
    },
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

/**
 * Record batch feedback for co-author changes (LEARN-001).
 * Fire-and-forget — feedback is best-effort for preference learning.
 */
export async function recordFeedback(
  chapterId: string,
  novelId: string,
  request: CoAuthorFeedbackRequest,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(
    `/api/v1/writing/chapters/${chapterId}/co-author/feedback?novel_id=${novelId}`,
    {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify(request),
    },
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
}
