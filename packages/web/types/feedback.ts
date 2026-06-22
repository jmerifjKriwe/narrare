// Memory / Feedback / Learning types

export type FeedbackAction = "accept" | "reject" | "modify";

/**
 * Closed-vocabulary source taxonomy (CR-AUFG-07-24).
 *
 * MUST stay in sync with `packages/core/narrare_core/memory/source_types.py`
 * `FeedbackSourceType` — enforced by
 * `tests/integration/memory/test_feedback_source_type_parity.py`.
 *
 * Mirror of the backend `Literal` in `apps/api/narrare/memory/schemas.py`
 * (RULE-17: the frontend type is a 1:1 mirror of the backend contract).
 */
export type FeedbackSourceType =
  | "co_author_change"
  | "kb_field_suggest"
  | "kb_enhance_field"
  | "kb_improve_suggestion"
  | "chat_message";

export interface FeedbackRequest {
  action: FeedbackAction;
  /**
   * Server-canonical UUID for the rated suggestion.
   *
   * CR-AUFG-07-24: now OPTIONAL client-side. The backend accepts either a
   * valid `suggestion_id` UUID OR the (`source_id` + `source_type`) pair and
   * derives the canonical uuid5 server-side. The frontend forwards a value
   * here ONLY when the surface genuinely owns a UUID; non-UUID surface ids
   * (change ids, message ids, field keys, numeric ids) MUST travel as
   * `source_id` instead.
   */
  suggestion_id?: string | null;
  /**
   * Stable per-surface id (change id, field key, message id, suggestion id,
   * ...) that the backend resolves to the canonical suggestion UUID.
   *
   * CR-AUFG-07-24: sent alongside `source_type`. Mirror of the backend
   * `FeedbackRequest.source_id` (RULE-17).
   */
  source_id?: string | null;
  intent: string;
  source_type?: FeedbackSourceType | null;
  suggestion_text: string;
  modification?: string | null;
  rating?: number | null;
  context?: Record<string, unknown> | null;
  project_id: string;
  chapter_id?: string | null;
  genre?: string | null;
  mode?: string | null;
}

export interface FeedbackResponse {
  id: string;
  action: string;
  created_at: string;
}

export interface PreferenceProfile {
  user_id: string;
  project_id: string;
  event_count: number;
  confidence: number;
  style: Record<string, string>;
  content: Record<string, string>;
  constraints: string[];
  last_updated: string;
}

export interface ResetResponse {
  message: string;
  deleted_count: number;
}

export interface AnalyzeRequest {
  project_id: string;
}

export interface AnalyzeResponse {
  id: string;
  user_id: string;
  project_id: string;
  confidence: number;
  summary: string;
  style_patterns: string[];
  content_patterns: string[];
  avoidance_patterns: string[];
  event_count_at_analysis: number;
  created_at: string;
  updated_at: string;
}
