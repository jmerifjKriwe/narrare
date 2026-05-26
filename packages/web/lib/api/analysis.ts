/**
 * Analysis API — types and client functions for beta reader simulation.
 *
 * Types mirror the Pydantic schemas in analysis/contracts.py (RULE-17).
 * All field names use snake_case to match the backend exactly.
 * Components never call fetch directly — use TanStack Query hooks from
 * lib/hooks/useBetaReader.ts.
 */

import { fetchApi } from "./client";

// --- Enums (string literal types matching Python StrEnum values) ---

export type FeedbackSeverity = "critical" | "moderate" | "minor";

export type FeedbackCategory = "plot" | "character" | "prose" | "pacing" | "experience";

// --- Feedback Types ---

export interface BetaFeedbackItem {
  category: FeedbackCategory;
  severity: FeedbackSeverity;
  location: string | null;
  title: string;
  description: string;
  suggestion: string | null;
  text_excerpt: string | null;
}

export interface BetaReaderStrength {
  category: FeedbackCategory;
  title: string;
  description: string;
  text_excerpt: string | null;
}

export interface BetaReaderQuestion {
  category: FeedbackCategory;
  location: string | null;
  question: string;
  context: string | null;
}

export interface BetaReaderOverallAssessment {
  summary: string;
  reader_engagement: number;
  emotional_impact: number;
  pacing_score: number;
  prose_quality: number;
  plot_progression: number;
  character_development: number;
}

// --- Request / Response ---

export interface BetaReaderRequest {
  chapter_ids: string[];
  categories?: FeedbackCategory[] | null;
  phase: "full" | "deepdive";
  deepdive_category?: FeedbackCategory | null;
  refresh?: boolean;
}

export interface BetaReaderResponse {
  novel_id: string;
  chapter_ids: string[];
  total_word_count: number;
  strengths: BetaReaderStrength[];
  feedback: BetaFeedbackItem[];
  questions: BetaReaderQuestion[];
  overall: BetaReaderOverallAssessment;
  analyzed_at: string;
  cache_key: string;
}

export interface BetaReaderDeepDiveRequest {
  chapter_ids: string[];
  category: FeedbackCategory;
  cache_key: string;
}

export interface BetaReaderDeepDiveResponse {
  novel_id: string;
  category: FeedbackCategory;
  detailed_feedback: BetaFeedbackItem[];
  revision_suggestions: string[];
  category_score: number;
  analyzed_at: string;
}

// --- API functions ---

export const analysisApi = {
  /**
   * Run Phase 1 beta reader analysis.
   *
   * POST /analysis/beta-reader?novel_id={novelId}
   * Returns comprehensive feedback across all categories.
   */
  analyze: (novelId: string, request: BetaReaderRequest) =>
    fetchApi<BetaReaderResponse>(`/analysis/beta-reader?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
    }),

  /**
   * Run Phase 2 deep-dive on a specific category.
   *
   * POST /analysis/beta-reader/deep-dive?novel_id={novelId}
   * Requires cache_key from Phase 1 response.
   */
  deepDive: (novelId: string, request: BetaReaderDeepDiveRequest) =>
    fetchApi<BetaReaderDeepDiveResponse>(`/analysis/beta-reader/deep-dive?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
    }),
};
