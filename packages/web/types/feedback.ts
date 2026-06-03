// Memory / Feedback / Learning types

export type FeedbackAction = "accept" | "reject" | "modify";

export interface FeedbackRequest {
  action: FeedbackAction;
  suggestion_id: string;
  intent: string;
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
