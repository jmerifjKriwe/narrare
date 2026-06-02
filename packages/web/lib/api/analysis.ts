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

// --- ANAL-003: Readability Analysis Types ---

export interface ReadabilityMetrics {
  flesch_reading_ease: number;
  flesch_kincaid_grade: number;
  gunning_fog: number;
  avg_sentence_length: number;
  avg_syllables_per_word: number;
  complex_word_ratio: number;
  word_count: number;
  sentence_count: number;
}

export interface SentenceAnalysis {
  sentence: string;
  sentence_index: number;
  issues: string[];
  readability_score: number;
  suggestions: string[];
}

export interface ReadabilityResult {
  metrics: ReadabilityMetrics;
  sentence_analyses: SentenceAnalysis[];
  genre_benchmarks: Record<string, ReadabilityMetrics>;
  overall_assessment: string | null;
}

export interface ReadabilityRequest {
  chapter_ids: string[];
  language?: string;
}

// --- ANAL-004: POV Analysis Types ---

export interface POVScene {
  scene_index: number;
  start_position: number;
  end_position: number;
  pov_character: string | null;
  confidence: number;
}

export type POVIssueType =
  | "head_hop"
  | "knowledge_leak"
  | "emotional_leak"
  | "physical_impossibility";
export type POVIssueSeverity = "error" | "warning";

export interface POVIssue {
  type: POVIssueType;
  location: string;
  text: string;
  explanation: string;
  suggestion: string;
  severity: POVIssueSeverity;
}

export interface POVResult {
  scenes: POVScene[];
  issues: POVIssue[];
  pov_distribution: Record<string, number>;
  switch_count: number;
  analysis_type: string;
}

export interface POVRequest {
  chapter_ids: string[];
  language?: string;
  pov_type?: string;
}

// --- API functions ---

export const analysisApi = {
  /**
   * Run Phase 1 beta reader analysis.
   *
   * POST /analysis/beta-reader?novel_id={novelId}
   * Returns comprehensive feedback across all categories.
   */
  analyze: (novelId: string, request: BetaReaderRequest, signal?: AbortSignal) =>
    fetchApi<BetaReaderResponse>(`/analysis/beta-reader?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
      signal,
    }),

  /**
   * Run Phase 2 deep-dive on a specific category.
   *
   * POST /analysis/beta-reader/deep-dive?novel_id={novelId}
   * Requires cache_key from Phase 1 response.
   */
  deepDive: (novelId: string, request: BetaReaderDeepDiveRequest, signal?: AbortSignal) =>
    fetchApi<BetaReaderDeepDiveResponse>(`/analysis/beta-reader/deep-dive?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
      signal,
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

  // --- ANAL-003: Readability ---

  /**
   * Run readability analysis on chapter(s).
   * POST /analysis/readability?novel_id={novelId}
   * Returns deterministic metrics + AI sentence analysis per chapter.
   */
  readability: (novelId: string, request: ReadabilityRequest) =>
    fetchApi<ReadabilityResult[]>(`/analysis/readability?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
    }),

  // --- ANAL-004: POV ---

  /**
   * Run POV analysis on chapter(s).
   * POST /analysis/pov?novel_id={novelId}
   * Returns scenes, issues, and distribution of POV characters.
   */
  analyzePOV: (novelId: string, request: POVRequest) =>
    fetchApi<POVResult>(`/analysis/pov?novel_id=${novelId}`, {
      method: "POST",
      body: JSON.stringify(request),
    }),
};
