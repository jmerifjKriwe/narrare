/**
 * KB Session API client — assisted creation with AI single-shot responses.
 *
 * Typed wrappers around session lifecycle endpoints. All operations are
 * REST `fetchApi` calls: the backend's suggest/interview/enhance routes
 * answer with one aggregate JSON document each (`{session, suggestion}`,
 * `{session, question}`, `{session, enhancement}`) — no SSE framing
 * (F9-2 transport fix, mirrors apps/api/narrare/kb/router_sessions.py).
 */

import { fetchApi } from "./client";

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

/**
 * Optional body for completing a session (RULE-17 mirror of the backend's
 * ``CompleteSessionRequest``). The collected entry name fills the session's
 * name before the entry is mapped; an absent body or absent name keeps the
 * backend's name-required guard (400).
 */
export interface KBCompleteSessionRequest {
  name?: string | null;
}

/** Response from completing a session — includes the new KB entry ID. */
export interface KBSessionCompleteResponse {
  session: KBCreationSession;
  entry_id: string;
}

// --- AI aggregate response types (RULE-17 mirrors of router_sessions.py) ---

/** Aggregate response from the suggest route. */
export interface KBSuggestResponse {
  session: KBCreationSession;
  suggestion: {
    field_key: string;
    suggestion: string;
    reasoning: string | null;
    context_used: string[];
  };
}

/** Aggregate response from the interview route. */
export interface KBInterviewResponse {
  session: KBCreationSession;
  question: {
    field_key: string;
    question: string;
    reasoning: string | null;
  };
}

/** Aggregate response from the enhance route. */
export interface KBEnhanceResponse {
  session: KBCreationSession;
  enhancement: {
    draft_entry: Record<string, unknown>;
    progress: number;
    reasoning: string | null;
    context_used: string[];
  };
}

// --- Result types (FE consumption contract) ---

/** Result from a field suggestion request. */
export interface KBSuggestionResult {
  field_key: string;
  suggestion: string;
  reasoning: string;
}

/**
 * Result from an interview question request. `target_field` is the wire's
 * `question.field_key`; `reasoning` is the model's why-this-question note.
 */
export interface KBInterviewResult {
  question: string;
  target_field: string;
  reasoning: string | null;
}

/** Result from an enhancement request, expanded per field. */
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

  /**
   * Mark session as complete and create the KB entry.
   * `name` is the entry name collected by the panel (F9-1); omitting it
   * keeps the backend's name-required guard.
   */
  completeSession: (novelId: string, sessionId: string, name?: string) => {
    const body: KBCompleteSessionRequest = { name: name ?? null };
    return fetchApi<KBSessionCompleteResponse>(
      `/novels/${novelId}/kb/sessions/${sessionId}/complete`,
      {
        method: "POST",
        // Body stays absent when no name was collected (BE treats it as absent).
        ...(name ? { body: JSON.stringify(body) } : {}),
      },
    );
  },

  /** Abandon and delete a session. */
  abandonSession: (novelId: string, sessionId: string) =>
    fetchApi<void>(`/novels/${novelId}/kb/sessions/${sessionId}`, {
      method: "DELETE",
    }),
};

// --- API functions: AI aggregates (REST single-shot) ---

/**
 * Request AI suggestion for a specific field.
 * Maps the `{session, suggestion}` aggregate to the suggestion result.
 */
export async function suggestField(
  novelId: string,
  sessionId: string,
  fieldKey: string,
  signal?: AbortSignal,
): Promise<KBSuggestionResult> {
  const response = await fetchApi<KBSuggestResponse>(
    `/novels/${novelId}/kb/sessions/${sessionId}/suggest/${fieldKey}`,
    { method: "POST", signal },
  );
  return {
    field_key: response.suggestion.field_key,
    suggestion: response.suggestion.suggestion,
    reasoning: response.suggestion.reasoning ?? "",
  };
}

/**
 * Request next interview question from AI.
 * Maps the `{session, question}` aggregate to the interview result.
 */
export async function requestInterview(
  novelId: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<KBInterviewResult> {
  const response = await fetchApi<KBInterviewResponse>(
    `/novels/${novelId}/kb/sessions/${sessionId}/interview`,
    { method: "POST", signal },
  );
  return {
    question: response.question.question,
    target_field: response.question.field_key,
    reasoning: response.question.reasoning,
  };
}

/**
 * Request AI enhancement of the entry.
 * Expands the `{session, enhancement}` aggregate's `draft_entry` into
 * per-field results; `original` comes from the field's prior user value in
 * the returned session (the backend overwrites `ai_suggested_value` before
 * responding, so that prior AI value is no longer recoverable).
 */
export async function requestEnhance(
  novelId: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<KBEnhancementResult[]> {
  const response = await fetchApi<KBEnhanceResponse>(
    `/novels/${novelId}/kb/sessions/${sessionId}/enhance`,
    { method: "POST", signal },
  );
  return Object.entries(response.enhancement.draft_entry)
    .filter((entry): entry is [string, string] => typeof entry[1] === "string")
    .map(([fieldKey, suggested]) => ({
      field_key: fieldKey,
      original:
        response.session.fields.find((field) => field.field_key === fieldKey)?.user_value ?? "",
      suggested,
      reasoning: response.enhancement.reasoning ?? "",
    }));
}
