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
  StyleVariant,
  StyleVariantRegenerateRequest,
} from "./generation-streams";
// Re-export stream functions and types from the streams module
export {
  parseAlternatives,
  streamExtend,
  streamGeneration,
  streamRewrite,
  streamStyleVariantRegeneration,
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
// WebSocket — Interactive writing sessions (re-exported)
// ---------------------------------------------------------------------------
//
// WritingSessionSocket and its message types live in `./writing-session-socket`
// (RULE-06: the interactive-session transport is a separate lifecycle from the
// SSE operation path per ADR-052 / ADR-043 Review-Trigger #1). They are
// re-exported here for backward compatibility so existing imports keep working.

export type {
  RecoveryFailureReason,
  SessionResponse,
  SessionTranscriptTailItem,
  StopReason,
  StreamStatus,
  WritingSessionSocketOptions,
} from "./writing-session-socket";
export {
  DEFAULT_MAX_RECONNECT_ATTEMPTS,
  DEFAULT_RECONNECT_BASE_DELAY_MS,
  WritingSessionSocket,
} from "./writing-session-socket";
