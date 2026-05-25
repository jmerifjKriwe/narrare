/**
 * KB Session API client — assisted creation with AI streaming.
 *
 * Typed wrappers around session lifecycle endpoints.
 * REST for CRUD operations, SSE for AI streaming operations.
 *
 * Architecture:
 * - REST operations: use fetchApi from client.ts
 * - SSE operations: use connectSSE from streaming.ts, wrapped in Promises
 */

import { fetchApi } from "./client";
import { connectSSE } from "./streaming";

// --- Session types ---

export type KBCreationFieldType = "text" | "list" | "boolean" | "select";
export type KBCreationFieldSource = "user" | "ai" | "world_derived" | "merged";
export type KBCreationSessionStatus = "active" | "review" | "complete" | "abandoned";

export interface KBCreationField {
  field_key: string;
  label: string;
  field_type: KBCreationFieldType;
  required: boolean;
  options?: string[];
  user_value?: string;
  ai_suggested_value?: string;
  ai_reasoning?: string;
  source: KBCreationFieldSource;
  final_value?: string;
}

export interface KBCreationSession {
  id: string;
  novel_id: string;
  user_id: string;
  entity_type: string;
  name?: string;
  status: KBCreationSessionStatus;
  fields: KBCreationField[];
  context_entries: string[];
  created_at: string;
  updated_at: string;
}

/** Response from completing a session — includes the new KB entry ID. */
export interface KBSessionCompleteResponse {
  session: KBCreationSession;
  entry_id: string;
}

// --- SSE Response types ---

/** Chunk format for SSE streaming from the backend. */
export interface SSETextChunk {
  text: string;
  type: string;
}

/** Result from a field suggestion request. */
export interface KBSuggestionResult {
  field_key: string;
  suggestion: string;
  reasoning: string;
}

/** Result from an interview question request. */
export interface KBInterviewResult {
  question: string;
  target_field: string;
  context: string;
}

/** Result from an enhancement request. */
export interface KBEnhancementResult {
  field_key: string;
  original: string;
  suggested: string;
  reasoning: string;
}

// --- API functions: REST ---

export const kbSessionApi = {
  /** Create a new KB creation session. */
  createSession: (novelId: string, entityType: string) =>
    fetchApi<KBCreationSession>(`/novels/${novelId}/kb/sessions`, {
      method: "POST",
      body: JSON.stringify({ entity_type: entityType }),
    }),

  /** Get an existing session by ID. */
  getSession: (novelId: string, sessionId: string) =>
    fetchApi<KBCreationSession>(`/novels/${novelId}/kb/sessions/${sessionId}`),

  /** Update a field with a user-provided value. */
  answerField: (novelId: string, sessionId: string, fieldKey: string, value: string) =>
    fetchApi<KBCreationSession>(`/novels/${novelId}/kb/sessions/${sessionId}/fields/${fieldKey}`, {
      method: "PATCH",
      body: JSON.stringify({ value }),
    }),

  /** Mark session as complete and create the KB entry. */
  completeSession: (novelId: string, sessionId: string) =>
    fetchApi<KBSessionCompleteResponse>(`/novels/${novelId}/kb/sessions/${sessionId}/complete`, {
      method: "POST",
    }),

  /** Abandon and delete a session. */
  abandonSession: (novelId: string, sessionId: string) =>
    fetchApi<void>(`/novels/${novelId}/kb/sessions/${sessionId}`, {
      method: "DELETE",
    }),
};

// --- API functions: SSE (Promise-wrapped) ---

/**
 * Request AI suggestion for a specific field.
 * Uses SSE streaming, wrapped in a Promise for async/await usage.
 */
export function suggestField(
  novelId: string,
  sessionId: string,
  fieldKey: string,
  signal?: AbortSignal,
): Promise<KBSuggestionResult> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let accumulatedText = "";
    let accumulatedReasoning = "";

    const onAbort = () => {
      if (!settled) {
        settled = true;
        reject(new DOMException("Aborted", "AbortError"));
      }
    };

    if (signal?.aborted) {
      onAbort();
      return;
    }

    signal?.addEventListener("abort", onAbort, { once: true });

    connectSSE<SSETextChunk>({
      url: `/novels/${novelId}/kb/sessions/${sessionId}/suggest/${fieldKey}`,
      body: {},
      onChunk: (chunk) => {
        // Backend sends type: "text" for suggestion, type: "reasoning" for reasoning
        if (chunk.type === "reasoning") {
          accumulatedReasoning += chunk.text;
        } else {
          accumulatedText += chunk.text;
        }
      },
      onComplete: () => {
        if (!settled) {
          settled = true;
          signal?.removeEventListener("abort", onAbort);
          resolve({
            field_key: fieldKey,
            suggestion: accumulatedText,
            reasoning: accumulatedReasoning,
          });
        }
      },
      onError: (error) => {
        if (!settled) {
          settled = true;
          signal?.removeEventListener("abort", onAbort);
          reject(error);
        }
      },
      signal,
    });
  });
}

/**
 * Request next interview question from AI.
 * Uses SSE streaming, wrapped in a Promise.
 */
export function requestInterview(
  novelId: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<KBInterviewResult> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let accumulatedQuestion = "";
    let targetField = "";

    const onAbort = () => {
      if (!settled) {
        settled = true;
        reject(new DOMException("Aborted", "AbortError"));
      }
    };

    if (signal?.aborted) {
      onAbort();
      return;
    }

    signal?.addEventListener("abort", onAbort, { once: true });

    connectSSE<SSETextChunk>({
      url: `/novels/${novelId}/kb/sessions/${sessionId}/interview`,
      body: {},
      onChunk: (chunk) => {
        // type: "question" for the main question, type: "meta" for target_field
        if (chunk.type === "meta" && chunk.text.startsWith("field:")) {
          targetField = chunk.text.slice(6).trim();
        } else {
          accumulatedQuestion += chunk.text;
        }
      },
      onComplete: () => {
        if (!settled) {
          settled = true;
          signal?.removeEventListener("abort", onAbort);
          resolve({
            question: accumulatedQuestion,
            target_field: targetField,
            context: "",
          });
        }
      },
      onError: (error) => {
        if (!settled) {
          settled = true;
          signal?.removeEventListener("abort", onAbort);
          reject(error);
        }
      },
      signal,
    });
  });
}

/**
 * Request AI enhancement for all fields.
 * Uses SSE streaming, wrapped in a Promise.
 */
export function requestEnhance(
  novelId: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<KBEnhancementResult[]> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const enhancements: KBEnhancementResult[] = [];

    const onAbort = () => {
      if (!settled) {
        settled = true;
        reject(new DOMException("Aborted", "AbortError"));
      }
    };

    if (signal?.aborted) {
      onAbort();
      return;
    }

    signal?.addEventListener("abort", onAbort, { once: true });

    // Simple accumulator pattern — backend streams one enhancement after another
    // In a real implementation, we'd track per-field metadata via chunk.type
    let currentField = "";
    let currentOriginal = "";
    let currentSuggested = "";
    let currentReasoning = "";

    connectSSE<SSETextChunk>({
      url: `/novels/${novelId}/kb/sessions/${sessionId}/enhance`,
      body: {},
      onChunk: (chunk) => {
        // type: "field:field_key" signals start of a new field's enhancement
        if (chunk.type === "meta" && chunk.text.startsWith("field:")) {
          // Save previous if exists
          if (currentField && currentSuggested) {
            enhancements.push({
              field_key: currentField,
              original: currentOriginal,
              suggested: currentSuggested,
              reasoning: currentReasoning,
            });
          }
          currentField = chunk.text.slice(6).trim();
          currentOriginal = "";
          currentSuggested = "";
          currentReasoning = "";
        } else if (chunk.type === "original") {
          currentOriginal += chunk.text;
        } else if (chunk.type === "reasoning") {
          currentReasoning += chunk.text;
        } else {
          currentSuggested += chunk.text;
        }
      },
      onComplete: () => {
        if (!settled) {
          settled = true;
          signal?.removeEventListener("abort", onAbort);
          // Save the last enhancement
          if (currentField && currentSuggested) {
            enhancements.push({
              field_key: currentField,
              original: currentOriginal,
              suggested: currentSuggested,
              reasoning: currentReasoning,
            });
          }
          resolve(enhancements);
        }
      },
      onError: (error) => {
        if (!settled) {
          settled = true;
          signal?.removeEventListener("abort", onAbort);
          reject(error);
        }
      },
      signal,
    });
  });
}
