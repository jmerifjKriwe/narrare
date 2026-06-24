/**
 * Prompts and KB Templates APIs.
 */

import type {
  CascadePath,
  DiffResponse,
  KBTemplateDetail,
  KBTemplateDiff,
  KBTemplateInfo,
  KBTemplateUpdateInfo,
  LiveTestRequest,
  PreviewRequest,
  PromptDetail,
  PromptHistoryClearedResponse,
  PromptHistoryListResponse,
  PromptInfo,
  PromptLiveTestStarted,
  PromptLiveTestStreamEvent,
  PromptPreview,
  PromptResetResult,
  PromptRevisionCompareResponse,
  PromptRevisionRestoredResponse,
  UpdateInfo,
} from "@/types";
import { fetchApi, fetchApiRaw } from "./core";
import { connectSSE, SSEStreamError } from "./streaming";

// --- Prompts ---

export const promptsApi = {
  list: (category?: string) =>
    fetchApi<PromptInfo[]>(`/prompts${category ? `?category=${category}` : ""}`),

  get: (id: string) => fetchApi<PromptDetail>(`/prompts/${id}`),

  save: (id: string, content: string) =>
    fetchApi<void>(`/prompts/${id}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),

  reset: (id: string) => fetchApi<void>(`/prompts/${id}/override`, { method: "DELETE" }),

  cascade: (id: string) => fetchApi<CascadePath[]>(`/prompts/${id}/cascade`),

  updates: () => fetchApi<UpdateInfo[]>("/prompts/updates"),

  diff: (id: string) => fetchApi<DiffResponse>(`/prompts/${id}/diff`),

  /** PROMPT-003: provider-free preview. */
  preview: (id: string, req: PreviewRequest) =>
    fetchApi<PromptPreview>(`/prompts/${id}/preview`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  /** PROMPT-003: reset with effective-state metadata response. */
  resetWithMetadata: (id: string) =>
    fetchApi<PromptResetResult>(`/prompts/${id}/reset`, { method: "POST" }),

  /** PROMPT-003: start optional live-test and return the raw SSE response. */
  startLiveTest: (id: string, req: LiveTestRequest) =>
    fetchApiRaw(`/prompts/${id}/live-test`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  // --- CR-AUFG-07-19: prompt history (revision list / compare / restore / clear) ---
  //
  // NOTE (RULE-17): ``scope`` is resolved to PROJECT server-side
  // (``_DEFAULT_SCOPE`` in ``router_prompt_history.py``). The client never
  // sends it. ``from`` / ``to`` use the backend query aliases; either may be
  // the literal ``PROMPT_HISTORY_ACTIVE_TOKEN`` ("active").

  /** List recorded override revisions, newest first. */
  listHistory: (id: string, limit?: number, offset?: number) =>
    fetchApi<PromptHistoryListResponse>(`/prompts/${id}/history${historyListQuery(limit, offset)}`),

  /** Compare two revisions (or either against the active override). */
  compareRevisions: (id: string, fromId: string, toId: string) =>
    fetchApi<PromptRevisionCompareResponse>(
      `/prompts/${id}/history/compare?from=${encodeURIComponent(fromId)}&to=${encodeURIComponent(toId)}`,
    ),

  /** Append-only restore: writes the active file + records a NEW revision. */
  restoreRevision: (id: string, revisionId: string) =>
    fetchApi<PromptRevisionRestoredResponse>(
      `/prompts/${id}/history/${encodeURIComponent(revisionId)}/restore`,
      { method: "POST" },
    ),

  /** Delete all history revisions (active override file untouched). */
  clearHistory: (id: string) =>
    fetchApi<PromptHistoryClearedResponse>(`/prompts/${id}/history`, {
      method: "DELETE",
    }),
};

/** Build the optional limit/offset query string for listHistory (no scope). */
function historyListQuery(limit?: number, offset?: number): string {
  const params = new URLSearchParams();
  if (limit !== undefined) params.set("limit", String(limit));
  if (offset !== undefined) params.set("offset", String(offset));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

// --- PROMPT-003 live-test SSE stream ---

/**
 * Stream the optional live-test output via SSE.
 *
 * Uses the existing ``connectSSE`` transport (RULE-13 SSE contract) so that
 * the caller's AbortSignal propagates to ``fetch`` and structured errors are
 * surfaced as :class:`SSEStreamError`. The caller wraps this with
 * ``useAIOperation`` to get the §16 lifecycle (loading/streaming/error/
 * connection-lost states, ``mapSSEError`` mapping).
 *
 * Event order emitted by the backend:
 *   1. ``event: meta``  → ``LiveTestStartedResponse``
 *   2. ``data``         → ``{ text: "..." }`` chunks
 *   3. ``event: done``  → ``{ is_final: true }``
 *   4. ``data: [DONE]`` → terminal sentinel
 */
export async function streamPromptLiveTest(
  promptId: string,
  request: LiveTestRequest,
  callbacks: {
    onMeta?: (meta: PromptLiveTestStarted) => void;
    onChunk: (text: string) => void;
    onComplete?: () => void;
    onError?: (error: SSEStreamError) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  let completed = false;
  const complete = (): void => {
    if (completed) return;
    completed = true;
    callbacks.onComplete?.();
  };

  await connectSSE<PromptLiveTestStreamEvent>({
    url: `/prompts/${promptId}/live-test`,
    method: "POST",
    body: request,
    signal,
    onChunk: (event) => {
      // meta frame: backend emits an explicit ``event: meta`` line; the
      // connectSSE transport only surfaces the parsed ``data`` payload, so
      // we recognise the meta frame by its prompt_id/intent/model_id fields.
      if (
        event.prompt_id !== undefined ||
        event.intent !== undefined ||
        event.model_id !== undefined
      ) {
        callbacks.onMeta?.({
          prompt_id: event.prompt_id ?? promptId,
          intent: event.intent ?? "",
          model_id: event.model_id ?? "",
          rate_limit_remaining: event.rate_limit_remaining ?? 0,
        });
        return;
      }

      if (event.is_final) {
        // done frame — connectSSE will call onComplete when it sees [DONE].
        return;
      }

      if (typeof event.error === "string") {
        callbacks.onError?.(new SSEStreamError(event.error, "stream"));
        completed = true;
        return;
      }

      if (event.text !== undefined) {
        callbacks.onChunk(event.text);
      }
    },
    onComplete: () => complete(),
    onError: (error) => {
      if (!completed) callbacks.onError?.(error);
    },
  });
}

// --- KB Templates ---

export const templatesApi = {
  list: (novelId: string) => fetchApi<KBTemplateInfo[]>(`/novels/${novelId}/kb/templates`),

  get: (novelId: string, entityType: string) =>
    fetchApi<KBTemplateDetail>(`/novels/${novelId}/kb/templates/${entityType}`),

  save: (novelId: string, entityType: string, content: string, basedOnVersion?: string) =>
    fetchApi<void>(`/novels/${novelId}/kb/templates/${entityType}`, {
      method: "POST",
      body: JSON.stringify({ content, based_on_version: basedOnVersion }),
    }),

  reset: (novelId: string, entityType: string) =>
    fetchApi<void>(`/novels/${novelId}/kb/templates/${entityType}`, { method: "DELETE" }),

  updates: (novelId: string) =>
    fetchApi<KBTemplateUpdateInfo[]>(`/novels/${novelId}/kb/templates/updates`),

  diff: (novelId: string, entityType: string) =>
    fetchApi<KBTemplateDiff>(`/novels/${novelId}/kb/templates/${entityType}/diff`),
};
