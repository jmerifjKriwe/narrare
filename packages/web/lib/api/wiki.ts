/**
 * Wiki API client.
 *
 * Typed wrappers around all Wiki summary endpoints.
 * Components never call fetch directly — always use these functions
 * via TanStack Query hooks from lib/hooks/useWiki.ts.
 */

import { fetchApi } from "./client";

// --- Wiki Entity Summary types ---

export interface WikiSummaryResponse {
  id: string;
  novel_id: string;
  entity_id: string;
  narrative_summary: string;
  role_in_story: string | null;
  key_attributes: string[] | null;
  relationships: Record<string, unknown>[] | null;
  chapter_references: Record<string, unknown>[] | null;
  character_arc: string | null;
  status: "fresh" | "stale" | "pending";
  version: number;
  generated_at: string | null;
  refreshed_at: string | null;
}

export interface WikiChapterSummaryResponse {
  id: string;
  chapter_id: string;
  narrative_summary: string;
  key_events: string[] | null;
  entities_involved: Record<string, unknown>[] | null;
  themes: string[] | null;
  emotional_arc: string | null;
  status: "fresh" | "stale" | "pending";
  version: number;
  generated_at: string | null;
}

export interface WikiSummaryListResponse {
  items: WikiSummaryResponse[];
  total: number;
}

export interface WikiRefreshResponse {
  summary_id: string | null;
  status: string;
  message: string;
}

export interface WikiIndexResponse {
  novel_id: string;
  total_summaries: number;
  fresh_count: number;
  stale_count: number;
  pending_count: number;
  last_generated_at: string | null;
}

// --- API functions ---

export const wikiApi = {
  getSummaries: (novelId: string, entityIds?: string[]) => {
    const params = entityIds?.length ? `?entity_ids=${entityIds.join(",")}` : "";
    return fetchApi<WikiSummaryListResponse>(`/novels/${novelId}/wiki/summaries${params}`);
  },

  getSummary: (novelId: string, entityId: string) =>
    fetchApi<WikiSummaryResponse>(`/novels/${novelId}/wiki/summaries/${entityId}`),

  getChapterSummary: (novelId: string, chapterId: string) =>
    fetchApi<WikiChapterSummaryResponse>(`/novels/${novelId}/wiki/chapters/${chapterId}/summary`),

  refreshSummary: (novelId: string, entityId: string, force = false) =>
    fetchApi<WikiRefreshResponse>(`/novels/${novelId}/wiki/summaries/${entityId}/refresh`, {
      method: "POST",
      body: JSON.stringify({ entity_id: entityId, force }),
    }),

  getWikiIndex: (novelId: string) => fetchApi<WikiIndexResponse>(`/novels/${novelId}/wiki/index`),

  markStale: (novelId: string, promptVersion?: string) =>
    fetchApi<{ count: number }>(`/novels/${novelId}/wiki/mark-stale`, {
      method: "POST",
      body: JSON.stringify(promptVersion ? { prompt_version: promptVersion } : {}),
    }),
};
