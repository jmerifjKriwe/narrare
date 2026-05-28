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

// --- ANAL-002: Sentiment Analysis Types ---

export interface VADScores {
  valence: number;
  arousal: number;
  dominance: number;
}

export interface EmotionScores {
  anger: number;
  anticipation: number;
  disgust: number;
  fear: number;
  joy: number;
  sadness: number;
  surprise: number;
  trust: number;
  positive: number;
  negative: number;
}

export interface SentenceSentiment {
  sentence: string;
  sentence_index: number;
  vad: VADScores;
  emotions: EmotionScores;
  word_count: number;
  is_dialogue: boolean;
  dominant_emotion: string | null;
}

export interface NarrativeArc {
  arc_type: string;
  confidence: number;
  segments: Array<Record<string, unknown>>;
  explanation: string;
}

export interface SentimentOverview {
  sentence_count: number;
  average_vad: VADScores;
  overall_emotions: EmotionScores;
  narrative_arc: NarrativeArc | null;
  sentences: SentenceSentiment[];
  dominant_emotions: string[];
}

export interface SentimentRequest {
  chapter_ids: string[];
  language?: string | null;
  detect_arc: boolean;
}

// --- CONS-001: Consistency Checker Types ---

export type ConsistencyCheckType = "character" | "timeline" | "world" | "plot";
export type ConsistencySeverity = "error" | "warning" | "info";

export interface ConsistencyIssue {
  check_type: ConsistencyCheckType;
  severity: ConsistencySeverity;
  description: string;
  locations: string[];
  conflicting_facts: string[];
  suggestion: string | null;
  confidence: number;
}

export interface ConsistencyRequest {
  chapter_ids: string[];
  check_types: ConsistencyCheckType[];
  include_kb: boolean;
}

export interface ConsistencyResponse {
  novel_id: string;
  chapter_ids: string[];
  check_types: ConsistencyCheckType[];
  issues: ConsistencyIssue[];
  error_count: number;
  warning_count: number;
  info_count: number;
  total_issues: number;
  overall_assessment: string;
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

  // --- ANAL-002: Sentiment ---

  /**
   * Run deterministic sentiment analysis on chapter(s).
   * POST /analysis/sentiment?novel_id={novelId}
   * Returns VAD + emotion + arc data per chapter.
   */
  sentiment: (novelId: string, request: SentimentRequest) =>
    fetchApi<SentimentOverview[]>(`/analysis/sentiment?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
    }),

  // --- CONS-001: Consistency ---

  /**
   * Run cross-chapter consistency check.
   * POST /consistency/check?novel_id={novelId}
   */
  consistencyCheck: (novelId: string, request: ConsistencyRequest) =>
    fetchApi<ConsistencyResponse>(`/consistency/check?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
    }),

  /**
   * Run single-chapter consistency check.
   * POST /consistency/chapters/{chapterId}/check?novel_id={novelId}
   */
  consistencyCheckChapter: (novelId: string, chapterId: string, request: ConsistencyRequest) =>
    fetchApi<ConsistencyResponse>(`/consistency/chapters/${chapterId}/check?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
    }),
};
