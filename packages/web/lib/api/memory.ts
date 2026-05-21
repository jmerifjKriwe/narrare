/**
 * Typed API client for the memory/feedback/learning endpoints.
 *
 * Covers: recording feedback, retrieving/resetting preferences,
 * and triggering preference analysis.
 */

import type {
  AnalyzeRequest,
  AnalyzeResponse,
  FeedbackRequest,
  FeedbackResponse,
  PreferenceProfile,
  ResetResponse,
} from "@/types";
import { fetchApi } from "./client";

// ---------------------------------------------------------------------------
// Memory API
// ---------------------------------------------------------------------------

export const memoryApi = {
  /** Record user feedback on an AI suggestion. */
  recordFeedback: (data: FeedbackRequest) =>
    fetchApi<FeedbackResponse>("/memory/feedback", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /** Retrieve aggregated preferences for a user/project pair. */
  getPreferences: (projectId: string) =>
    fetchApi<PreferenceProfile>(`/memory/preferences?project_id=${projectId}`),

  /** Clear all feedback events and preferences for a user/project pair. */
  resetPreferences: (projectId: string) =>
    fetchApi<ResetResponse>(`/memory/preferences?project_id=${projectId}`, {
      method: "DELETE",
    }),

  /** Trigger preference analysis on accumulated feedback. */
  triggerAnalysis: (data: AnalyzeRequest) =>
    fetchApi<AnalyzeResponse>("/memory/analyze", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
