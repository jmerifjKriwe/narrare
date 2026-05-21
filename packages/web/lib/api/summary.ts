/**
 * Chapter Summary API client.
 *
 * Typed wrappers around summary endpoints.
 * Components never call fetch directly — always use these functions
 * via TanStack Query hooks from lib/hooks/useSummary.ts.
 *
 * Backend: POST /api/v1/summary/chapters/{chapter_id}
 */

import { fetchApi } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SummarizeRequest {
  max_sentences?: number;
  language?: string;
}

export interface SummarizeResponse {
  summary: string;
  word_count: number;
  key_points: string[];
}

// ---------------------------------------------------------------------------
// Summarization
// ---------------------------------------------------------------------------

/** Generate a summary for the given chapter. */
export function summarizeChapter(
  chapterId: string,
  novelId: string,
  options?: SummarizeRequest,
): Promise<SummarizeResponse> {
  const queryParams = new URLSearchParams({ novel_id: novelId });
  if (options?.max_sentences != null) {
    queryParams.set("max_sentences", String(options.max_sentences));
  }
  if (options?.language != null) {
    queryParams.set("language", options.language);
  }
  const qs = queryParams.toString();
  return fetchApi<SummarizeResponse>(`/summary/chapters/${chapterId}?${qs}`, {
    method: "POST",
    body: options ? JSON.stringify(options) : undefined,
  });
}

export const summaryApi = {
  summarizeChapter,
};
