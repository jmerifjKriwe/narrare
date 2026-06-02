/**
 * Timeline API client.
 *
 * Typed wrappers around all timeline event endpoints.
 * Components never call fetch directly — always use these functions
 * via TanStack Query hooks from lib/hooks/useTimeline.ts.
 */

import type {
  ExtractedEvent,
  TemporalConsistency,
  TimelineAnalysis,
  TimelineEvent,
  TimelineEventCreateRequest,
  TimelineEventUpdateRequest,
  TimelineFilters,
} from "@/types/timeline";
import { fetchApi } from "./client";

// --- Query parameter builder ---

function buildFilterParams(filters: TimelineFilters): string {
  const params = new URLSearchParams();
  if (filters.event_type) params.set("event_type", filters.event_type);
  if (filters.chapter_id) params.set("chapter_id", filters.chapter_id);
  if (filters.source) params.set("source", filters.source);
  if (filters.is_confirmed !== undefined) params.set("is_confirmed", String(filters.is_confirmed));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

// --- API functions ---

export const timelineApi = {
  /**
   * List timeline events for a novel, with optional filters.
   * GET /planning/timeline/{novelId}/events
   */
  listEvents: (novelId: string, filters?: TimelineFilters) => {
    const qs = filters ? buildFilterParams(filters) : "";
    return fetchApi<TimelineEvent[]>(`/planning/timeline/${novelId}/events${qs}`);
  },

  /**
   * Create a new timeline event.
   * POST /planning/timeline/{novelId}/events
   */
  createEvent: (novelId: string, data: TimelineEventCreateRequest) =>
    fetchApi<TimelineEvent>(`/planning/timeline/${novelId}/events`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /**
   * Get a single timeline event by ID.
   * GET /planning/timeline/{novelId}/events/{eventId}
   */
  getEvent: (novelId: string, eventId: string) =>
    fetchApi<TimelineEvent>(`/planning/timeline/${novelId}/events/${eventId}`),

  /**
   * Update a timeline event.
   * PUT /planning/timeline/{novelId}/events/{eventId}
   */
  updateEvent: (novelId: string, eventId: string, data: TimelineEventUpdateRequest) =>
    fetchApi<TimelineEvent>(`/planning/timeline/${novelId}/events/${eventId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  /**
   * Delete a timeline event.
   * DELETE /planning/timeline/{novelId}/events/{eventId}
   */
  deleteEvent: (novelId: string, eventId: string) =>
    fetchApi<void>(`/planning/timeline/${novelId}/events/${eventId}`, {
      method: "DELETE",
    }),

  /**
   * Get AI-generated timeline analysis for a novel.
   * GET /planning/timeline/{novelId}
   */
  getAnalysis: (novelId: string) => fetchApi<TimelineAnalysis>(`/planning/timeline/${novelId}`),

  /**
   * Extract temporal expressions from selected chapters.
   * POST /planning/timeline/{novelId}/extract
   */
  extractExpressions: (novelId: string, chapterIds: string[]) =>
    fetchApi<ExtractedEvent[]>(`/planning/timeline/${novelId}/extract`, {
      method: "POST",
      body: JSON.stringify({ chapter_ids: chapterIds }),
    }),

  /**
   * Check temporal consistency for a novel.
   * GET /planning/timeline/{novelId}/consistency
   */
  checkConsistency: (novelId: string) =>
    fetchApi<TemporalConsistency>(`/planning/timeline/${novelId}/consistency`),
};
