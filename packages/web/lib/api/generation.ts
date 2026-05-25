/**
 * Typed API client for the writing/generation endpoints.
 *
 * Covers: start/stop generation, accept/reject draft, scene-by-scene control,
 * SSE streaming of generated text, and WebSocket interactive sessions.
 */

import type { TokenUsage } from "@/types";
import { fetchApi, getAccessToken } from "./client";

// ---------------------------------------------------------------------------
// Types — field names match backend schemas exactly (RULE-17)
// ---------------------------------------------------------------------------

export type GenerationMode =
  | "full_draft"
  | "scene_by_scene"
  | "interview_assisted"
  | "interactive_session";

export type GenerationStatus = "pending" | "streaming" | "completed" | "stopped" | "failed";

export interface GenerateRequest {
  mode: GenerationMode;
  outline?: string | null;
  prompt?: string | null;
  auto_continue?: boolean;
  word_target?: number | null;
  tone?: string;
  language?: string;
}

export interface GenerateResponse {
  request_id: string;
  status: string;
  mode: string;
}

export interface StopResponse {
  request_id: string;
  status: string;
  word_count: number;
}

export interface AcceptResponse {
  request_id: string;
  chapter_id: string;
  word_count: number;
}

export interface RejectResponse {
  request_id: string;
  status: string;
}

export interface GenerationStats {
  total_generations: number;
  success_rate: number;
  avg_tokens: number;
  avg_word_count: number;
  most_used_model: string | null;
}

// ---------------------------------------------------------------------------
// REST API
// ---------------------------------------------------------------------------

export const writingApi = {
  startGeneration: (chapterId: string, novelId: string, request: GenerateRequest) =>
    fetchApi<GenerateResponse>(`/writing/chapters/${chapterId}/generate?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
    }),

  stopGeneration: (requestId: string) =>
    fetchApi<StopResponse>(`/writing/generation/${requestId}`, { method: "DELETE" }),

  acceptDraft: (requestId: string, modifiedText?: string) =>
    fetchApi<AcceptResponse>(`/writing/generation/${requestId}/accept`, {
      method: "POST",
      body: JSON.stringify({ modified_text: modifiedText }),
    }),

  rejectDraft: (requestId: string) =>
    fetchApi<RejectResponse>(`/writing/generation/${requestId}/reject`, { method: "POST" }),

  nextScene: (requestId: string) =>
    fetchApi<{ request_id: string; scene_number: number; status: string }>(
      `/writing/generation/${requestId}/scene/next`,
      { method: "POST" },
    ),

  acceptScene: (requestId: string, sceneNumber: number) =>
    fetchApi<AcceptResponse>(`/writing/generation/${requestId}/scene/${sceneNumber}/accept`, {
      method: "POST",
    }),

  getStats: (novelId: string) => fetchApi<GenerationStats>(`/writing/novels/${novelId}/stats`),
};

// ---------------------------------------------------------------------------
// SSE Streaming
// ---------------------------------------------------------------------------

export interface GenerationChunk {
  text: string;
  is_final?: boolean;
  usage?: TokenUsage;
}

/** Context metadata sent as first SSE event (CR-07 Context Inspector). */
export interface ContextMeta {
  type: "context_meta";
  kb_characters_count: number;
  kb_locations_count: number;
  kb_factions_count: number;
  kb_suggested_count: number;
  kb_pinned_count: number;
  recent_chapter_count: number;
  character_names: string[];
  location_names: string[];
  faction_names: string[];
  is_first_chapter: boolean;
  has_user_preferences: boolean;
  tone: string;
  total_budget_tokens: number;
}

// ---------------------------------------------------------------------------
// Rewrite (WRITE-004)
// ---------------------------------------------------------------------------

export type RewriteMode = "tone" | "style" | "voice" | "fix" | "custom";

export interface RewriteRequest {
  selection_text: string;
  context_before?: string;
  context_after?: string;
  mode: RewriteMode;
  options?: Record<string, string>;
  character_id?: string;
  custom_instructions?: string;
  count?: number;
  tone?: string;
  language?: string;
}

export interface RewriteAlternative {
  label: string;
  text: string;
}

export interface RewriteConfig {
  mode: RewriteMode;
  option: string;
  count: number;
  customInstructions?: string;
}

/**
 * Client-side state machine parser for `<alternative label="...">` tags.
 *
 * Buffers partial tags across SSE chunk boundaries. Only recognizes
 * `<alternative` at line boundaries (start of line or after `</alternative>`).
 * Returns RewriteAlternative[] with parsed label and text.
 *
 * Fallback: if no tags found, entire response = single alternative.
 */
export function parseAlternatives(fullText: string): RewriteAlternative[] {
  const alternatives: RewriteAlternative[] = [];
  const openTagRegex = /^<alternative\s+label="([^"]*)">/;
  const closeTag = "</alternative>";

  let i = 0;
  let inAlternative = false;
  let currentLabel = "";
  let currentTextStart = 0;

  while (i < fullText.length) {
    if (!inAlternative) {
      // Look for opening tag at line boundary (start of text or after newline/closing tag)
      const remaining = fullText.slice(i);
      const match = openTagRegex.exec(remaining);

      if (match) {
        // Verify this is at a valid boundary: start of text, or preceded by \n
        if (
          i === 0 ||
          fullText[i - 1] === "\n" ||
          fullText.slice(i - closeTag.length, i) === closeTag
        ) {
          currentLabel = match[1];
          i += match[0].length;
          currentTextStart = i;
          inAlternative = true;
          continue;
        }
      }
      i++;
    } else {
      // Look for closing tag
      const closeIdx = fullText.indexOf(closeTag, i);
      if (closeIdx === -1) {
        // No closing tag found — rest is part of this alternative (incomplete)
        break;
      }

      const text = fullText.slice(currentTextStart, closeIdx);
      alternatives.push({ label: currentLabel, text });
      i = closeIdx + closeTag.length;
      inAlternative = false;
    }
  }

  // Fallback: if no tags found, entire response = single alternative
  if (alternatives.length === 0 && fullText.trim().length > 0) {
    alternatives.push({ label: "Rewritten text", text: fullText.trim() });
  }

  return alternatives;
}

/**
 * Stream rewrite SSE directly from POST /rewrite endpoint.
 *
 * Accumulates stream text, calls parseAlternatives() as complete
 * alternatives are detected, and emits callbacks for each one.
 */
export async function streamRewrite(
  chapterId: string,
  novelId: string,
  request: RewriteRequest,
  callbacks: {
    onRequestInfo?: (requestId: string) => void;
    onAlternative: (label: string, text: string) => void;
    onAlternativeFinal?: (count: number) => void;
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
      `/api/v1/writing/chapters/${chapterId}/rewrite?novel_id=${novelId}`,
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
    let emittedCount = 0;
    const closeTag = "</alternative>";

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
            // Final parse: emit any remaining alternatives
            const allAlts = parseAlternatives(accumulatedText);
            for (let i = emittedCount; i < allAlts.length; i++) {
              callbacks.onAlternative(allAlts[i].label, allAlts[i].text);
              emittedCount++;
            }
            callbacks.onAlternativeFinal?.(emittedCount);
            return;
          }
          try {
            const parsed = JSON.parse(data) as ExtendStreamEvent;

            if (parsed.type === "request_info" && parsed.request_id) {
              callbacks.onRequestInfo?.(parsed.request_id);
              continue;
            }

            if (parsed.text) {
              accumulatedText += parsed.text;

              // Check if we have complete alternatives to emit
              while (accumulatedText.includes(closeTag)) {
                const closeIdx = accumulatedText.indexOf(closeTag);
                const preceding = accumulatedText.slice(0, closeIdx + closeTag.length);

                // Parse just this portion
                const parsedAlts = parseAlternatives(preceding);
                for (const alt of parsedAlts) {
                  callbacks.onAlternative(alt.label, alt.text);
                  emittedCount++;
                }

                // Remove the parsed portion from accumulated text
                accumulatedText = accumulatedText.slice(closeIdx + closeTag.length);
              }
            }
            if (parsed.is_final) {
              // Final parse for any remaining text
              const allAlts = parseAlternatives(accumulatedText);
              for (let i = emittedCount; i < allAlts.length; i++) {
                callbacks.onAlternative(allAlts[i].label, allAlts[i].text);
                emittedCount++;
              }
              callbacks.onAlternativeFinal?.(emittedCount);
              return;
            }
          } catch {
            /* skip malformed JSON */
          }
        }
      }
    }

    // Stream ended without [DONE] — still emit any remaining
    const allAlts = parseAlternatives(accumulatedText);
    for (let i = emittedCount; i < allAlts.length; i++) {
      callbacks.onAlternative(allAlts[i].label, allAlts[i].text);
      emittedCount++;
    }
    callbacks.onAlternativeFinal?.(emittedCount);
  } catch (error) {
    const isAbort =
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError");
    if (isAbort) return;
    callbacks.onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}

// ---------------------------------------------------------------------------
// Extend (WRITE-003)
// ---------------------------------------------------------------------------

export type ExtendLength = "short" | "medium" | "long";

export interface ExtendRequest {
  text_before: string;
  text_after?: string | null;
  length?: ExtendLength;
  tone?: string;
  language?: string;
}

export interface ExtendStreamEvent {
  type?: "request_info" | "text" | "done";
  request_id?: string;
  text?: string;
  is_final?: boolean;
  usage?: TokenUsage;
}

/** Stream extend SSE directly from POST /extend endpoint. */
export async function streamExtend(
  chapterId: string,
  novelId: string,
  request: ExtendRequest,
  callbacks: {
    onRequestInfo?: (requestId: string) => void;
    onChunk: (text: string) => void;
    onComplete?: () => void;
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
      `/api/v1/writing/chapters/${chapterId}/extend?novel_id=${novelId}`,
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
            callbacks.onComplete?.();
            return;
          }
          try {
            const parsed = JSON.parse(data) as ExtendStreamEvent;

            if (parsed.type === "request_info" && parsed.request_id) {
              callbacks.onRequestInfo?.(parsed.request_id);
              continue;
            }

            if (parsed.text) {
              callbacks.onChunk(parsed.text);
            }
            if (parsed.is_final) {
              callbacks.onComplete?.();
              return;
            }
          } catch {
            /* skip malformed JSON */
          }
        }
      }
    }
    // Stream ended without [DONE] — still complete
    callbacks.onComplete?.();
  } catch (error) {
    const isAbort =
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError");
    if (isAbort) return;
    callbacks.onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}

export async function streamGeneration(
  requestId: string,
  onChunk: (chunk: GenerationChunk) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void,
  signal?: AbortSignal,
  onUsage?: (usage: TokenUsage) => void,
  onContextMeta?: (meta: ContextMeta) => void,
): Promise<void> {
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  try {
    const response = await fetch(`/api/v1/writing/generation/${requestId}/stream`, {
      headers,
      credentials: "include",
      signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";

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
            onComplete?.();
            return;
          }
          try {
            const parsed = JSON.parse(data);

            // Context metadata event (CR-07: first event before text)
            if (parsed.type === "context_meta") {
              onContextMeta?.(parsed as ContextMeta);
              continue;
            }

            const chunk = parsed as GenerationChunk;
            if (chunk.is_final && chunk.usage) {
              onUsage?.(chunk.usage);
            }
            onChunk(chunk);
          } catch {
            /* skip malformed JSON */
          }
        }
      }
    }
  } catch (error) {
    const isAbort =
      (error instanceof DOMException && error.name === "AbortError") ||
      (error instanceof Error && error.name === "AbortError");
    if (isAbort) return;
    onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}

// ---------------------------------------------------------------------------
// WebSocket — Interactive Sessions
// ---------------------------------------------------------------------------

export interface SessionMessage {
  type: "user_direction" | "user_feedback" | "save_to_chapter" | "end_session" | "generate_draft";
  content?: string;
  action?: string;
  text?: string;
}

export interface SessionResponse {
  type:
    | "greeting"
    | "text_chunk"
    | "text_done"
    | "feedback_acknowledged"
    | "saved"
    | "timeout"
    | "error"
    | "draft_done"
    | "interview_greeting";
  text?: string;
  message?: string;
  content?: string;
  action?: string;
  word_count?: number;
  session_id?: string;
  mode?: string;
}

export class WritingSessionSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnects = 3;

  constructor(
    private chapterId: string,
    private onMessage: (msg: SessionResponse) => void,
    private onError?: (error: Error) => void,
    private userId?: string,
    private projectId?: string,
    private mode: string = "interactive_session",
  ) {}

  connect(): void {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "";
    // Derive WebSocket base: replace http(s) with ws(s), or use current host
    const wsBaseUrl = baseUrl
      ? baseUrl.replace(/^http/, "ws") // http:// → ws://, https:// → wss://
      : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
    const params = new URLSearchParams();
    if (this.userId) params.set("user_id", this.userId);
    if (this.projectId) params.set("project_id", this.projectId);
    if (this.mode && this.mode !== "interactive_session") params.set("mode", this.mode);
    const qs = params.toString();
    const wsUrl = `${wsBaseUrl}/api/v1/writing/sessions/${this.chapterId}${qs ? `?${qs}` : ""}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      try {
        this.onMessage(JSON.parse(event.data) as SessionResponse);
        this.reconnectAttempts = 0;
      } catch {
        /* skip malformed JSON */
      }
    };

    this.ws.onerror = () => {
      this.onError?.(new Error("WebSocket error"));
    };

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnects) {
        const delay = 2 ** this.reconnectAttempts * 1000;
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), delay);
      }
    };
  }

  send(message: SessionMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  close(): void {
    this.reconnectAttempts = this.maxReconnects;
    this.ws?.close();
  }
}
