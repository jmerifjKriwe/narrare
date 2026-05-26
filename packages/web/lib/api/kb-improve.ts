/**
 * KB Improve API types and client.
 *
 * REST endpoints for entry improvement analysis and application.
 * Components never call fetch directly — always use these functions
 * via TanStack Query hooks from lib/hooks/useKBImprove.ts.
 */

import { fetchApi } from "./client";

// --- Types ---

export interface ImproveSuggestion {
  type: "add_field" | "connect" | "expand" | "reorganize";
  target: string;
  description: string;
  proposed_content: string | null;
  related_entity_id: string | null;
  related_entity_name: string | null;
  confidence: number;
  reasoning: string | null;
  suggestion_id: number;
}

export interface KBImproveAnalysisResponse {
  suggestions: ImproveSuggestion[];
  overall_assessment: string;
  completeness_score: number;
}

export interface KBImproveApplyRequest {
  suggestion_ids: number[];
}

export interface KBImproveApplyResponse {
  success: boolean;
  entry_id: string;
  applied_count: number;
  message: string;
}

// --- API client ---

export const kbImproveApi = {
  /** Analyze a KB entry and return improvement suggestions. */
  analyzeEntry: (novelId: string, entryId: string) =>
    fetchApi<KBImproveAnalysisResponse>(`/novels/${novelId}/kb/entities/${entryId}/improve`, {
      method: "POST",
    }),

  /** Apply selected improvement suggestions to an entry. */
  applyImprovements: (novelId: string, entryId: string, suggestionIds: number[]) =>
    fetchApi<KBImproveApplyResponse>(`/novels/${novelId}/kb/entities/${entryId}/improve/apply`, {
      method: "POST",
      body: JSON.stringify({ suggestion_ids: suggestionIds } satisfies KBImproveApplyRequest),
    }),
};
