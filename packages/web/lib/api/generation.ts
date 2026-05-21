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

export async function streamGeneration(
  requestId: string,
  onChunk: (chunk: GenerationChunk) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void,
  signal?: AbortSignal,
  onUsage?: (usage: TokenUsage) => void,
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
            const chunk = JSON.parse(data) as GenerationChunk;
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
