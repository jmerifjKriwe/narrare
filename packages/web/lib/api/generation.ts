/**
 * Generation API — name generation, writing generation, and streaming.
 *
 * Re-exports SSE stream wrappers from generation-streams.ts so consumers
 * can import everything from a single module.
 */

import type { NameGenerateRequest, NameGenerateResponse } from "@/types";
import { fetchApi } from "./core";

export type {
  ContextMeta,
  ExtendLength,
  ExtendRequest,
  ExtendStreamEvent,
  GenerationChunk,
  RewriteAlternative,
  RewriteConfig,
  RewriteMode,
  RewriteRequest,
} from "./generation-streams";
// Re-export stream functions and types from the streams module
export {
  parseAlternatives,
  streamExtend,
  streamGeneration,
  streamRewrite,
} from "./generation-streams";

// ---------------------------------------------------------------------------
// Generation types
// ---------------------------------------------------------------------------

/** Available generation modes for chapter writing. */
export type GenerationMode =
  | "full_draft"
  | "scene_by_scene"
  | "interview_assisted"
  | "interactive_session";

/** Request body for starting a chapter generation. */
export interface GenerateRequest {
  mode: GenerationMode;
  word_target?: number | null;
  tone?: string;
  outline?: string | null;
  prompt?: string | null;
  auto_continue?: boolean;
}

// ---------------------------------------------------------------------------
// Name generation
// ---------------------------------------------------------------------------

export const generationApi = {
  generateNames: (request: NameGenerateRequest, signal?: AbortSignal) =>
    fetchApi<NameGenerateResponse>("/generation/names", {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    }),
};

// ---------------------------------------------------------------------------
// Writing generation (REST)
// ---------------------------------------------------------------------------

export const writingApi = {
  /** Start a new generation request for a chapter. */
  startGeneration: (chapterId: string, novelId: string, body: GenerateRequest) =>
    fetchApi<{ request_id: string; status: string; mode?: string }>(
      `/writing/chapters/${chapterId}/generate?novel_id=${novelId}`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  /** Stop an in-progress generation. */
  stopGeneration: (requestId: string) =>
    fetchApi<{ request_id: string; status: string; word_count: number }>(
      `/writing/generation/${requestId}`,
      { method: "DELETE" },
    ),

  /** Accept the generated draft, optionally with edits. */
  acceptDraft: (requestId: string, modifiedText?: string) =>
    fetchApi<{ request_id: string; chapter_id: string; word_count: number }>(
      `/writing/generation/${requestId}/accept`,
      {
        method: "POST",
        body:
          modifiedText !== undefined ? JSON.stringify({ modified_text: modifiedText }) : undefined,
      },
    ),

  /** Reject the generated draft. */
  rejectDraft: (requestId: string) =>
    fetchApi<{ request_id: string; status: string }>(`/writing/generation/${requestId}/reject`, {
      method: "POST",
    }),

  /** Advance to the next scene. */
  nextScene: (requestId: string) =>
    fetchApi<{ request_id: string; scene_number: number; status: string }>(
      `/writing/generation/${requestId}/scene/next`,
      { method: "POST" },
    ),

  /** Accept a specific scene. */
  acceptScene: (requestId: string, sceneNum: number) =>
    fetchApi<{ request_id: string; chapter_id: string; word_count: number }>(
      `/writing/generation/${requestId}/scene/${sceneNum}/accept`,
      { method: "POST" },
    ),

  /** Get generation stats for a novel. */
  getStats: (novelId: string) =>
    fetchApi<{
      total_generations: number;
      success_rate: number;
      avg_tokens: number;
      avg_word_count: number;
      most_used_model: string;
    }>(`/writing/novels/${novelId}/stats`),
};

// ---------------------------------------------------------------------------
// WebSocket — Interactive writing sessions
// ---------------------------------------------------------------------------

/** Server-sent message types during an interactive writing session. */
export interface SessionResponse {
  type:
    | "greeting"
    | "interview_greeting"
    | "text_chunk"
    | "text_done"
    | "draft_done"
    | "feedback_acknowledged"
    | "saved"
    | "timeout"
    | "error";
  text?: string;
  message?: string;
}

/** Configuration options for WritingSessionSocket. */
export interface WritingSessionSocketOptions {
  /** Maximum reconnection attempts. Default: 5. */
  readonly maxReconnectAttempts?: number;
  /** Base delay in ms for linear reconnect backoff (delay = base × attempt). Default: 1000. */
  readonly reconnectBaseDelayMs?: number;
}

/** Default values for socket configuration. */
export const DEFAULT_MAX_RECONNECT_ATTEMPTS = 5;
export const DEFAULT_RECONNECT_BASE_DELAY_MS = 1000;

/**
 * WebSocket wrapper for interactive writing sessions.
 *
 * Connects to `ws(s)://{host}/api/v1/writing/sessions/{chapterId}` and
 * handles reconnection up to maxReconnectAttempts. Gracefully degrades
 * when WebSocket is unavailable (e.g. test environments).
 */
export class WritingSessionSocket {
  private ws: WebSocket | null = null;
  private closed = false;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts: number;
  private readonly reconnectBaseDelayMs: number;

  constructor(
    private readonly chapterId: string,
    private readonly onMessage: (msg: SessionResponse) => void,
    private readonly onError: () => void,
    private readonly userId?: string,
    private readonly novelId?: string,
    private readonly mode?: string,
    socketOptions?: WritingSessionSocketOptions,
  ) {
    this.maxReconnectAttempts =
      socketOptions?.maxReconnectAttempts ?? DEFAULT_MAX_RECONNECT_ATTEMPTS;
    this.reconnectBaseDelayMs =
      socketOptions?.reconnectBaseDelayMs ?? DEFAULT_RECONNECT_BASE_DELAY_MS;
  }

  /** Open the WebSocket connection. Safe to call multiple times. */
  connect(): void {
    if (this.closed) return;

    const protocol =
      typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = typeof window !== "undefined" ? window.location.host : "localhost";

    const params = new URLSearchParams();
    if (this.userId) params.set("user_id", this.userId);
    if (this.novelId) params.set("project_id", this.novelId);
    if (this.mode) params.set("mode", this.mode);

    const url = `${protocol}//${host}/api/v1/writing/sessions/${this.chapterId}?${params.toString()}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          this.onMessage(JSON.parse(event.data) as SessionResponse);
        } catch {
          // Ignore malformed messages
        }
      };

      this.ws.onerror = () => {
        this.onError();
      };

      this.ws.onclose = () => {
        if (!this.closed && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          setTimeout(() => this.connect(), this.reconnectBaseDelayMs * this.reconnectAttempts);
        }
      };
    } catch {
      // WebSocket not available (e.g. test environment) — degrade gracefully
    }
  }

  /** Send a JSON message over the socket. No-op if not connected. */
  send(message: Record<string, unknown>): void {
    try {
      this.ws?.send(JSON.stringify(message));
    } catch {
      // Silently ignore if not connected
    }
  }

  /** Close the socket and prevent further reconnection attempts. */
  close(): void {
    this.closed = true;
    this.reconnectAttempts = this.maxReconnectAttempts;
    try {
      this.ws?.close();
    } catch {
      // Silently ignore
    }
    this.ws = null;
  }
}
