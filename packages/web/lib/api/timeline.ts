/**
 * Timeline API client.
 *
 * Typed wrappers around all timeline event endpoints.
 * Components never call fetch directly — always use these functions
 * via TanStack Query hooks from lib/hooks/useTimeline.ts.
 */

import type {
  CharacterAgeReport,
  ExtractedEvent,
  TemporalConsistency,
  TimelineAnalysis,
  TimelineEvent,
  TimelineEventCreateRequest,
  TimelineEventUpdateRequest,
  TimelineFilters,
} from "@/types/timeline";
import { fetchApi } from "./client";
import { connectSSE } from "./streaming";

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
   *
   * @deprecated Use extractExpressionsSSE for progressive SSE streaming extraction.
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

  /**
   * Get character age report from KB metadata.
   * GET /planning/timeline/{novelId}/character-ages
   */
  getCharacterAges: (novelId: string) =>
    fetchApi<CharacterAgeReport>(`/planning/timeline/${novelId}/character-ages`),
};

// --- SSE Extraction & Confirm (Phase 2 — PLAN-004) ---

/**
 * Extract temporal expressions from chapters via SSE streaming.
 * Events arrive progressively via onChunk callback as the backend processes them.
 *
 * POST /planning/timeline/{novelId}/extract (SSE)
 *
 * Stream format:
 *   data: <ExtractedEvent JSON>\n\n
 *   data: [DONE]\n\n
 */
export function extractExpressionsSSE(
  novelId: string,
  chapterIds: string[],
  callbacks: {
    onEvent: (event: ExtractedEvent) => void;
    onComplete: () => void;
    onError: (error: Error) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  return connectSSE<ExtractedEvent>({
    url: `/planning/timeline/${novelId}/extract`,
    body: { chapter_ids: chapterIds },
    onChunk: callbacks.onEvent,
    onComplete: () => callbacks.onComplete(),
    onError: callbacks.onError,
    signal,
  });
}

/**
 * Confirm an extracted temporal expression and persist it as a timeline event.
 * Preserves source='extracted', confidence, and is_confirmed metadata.
 *
 * POST /planning/timeline/{novelId}/extract/confirm
 */
export function confirmExtractedEvent(
  novelId: string,
  extracted: ExtractedEvent,
): Promise<TimelineEvent> {
  return fetchApi<TimelineEvent>(`/planning/timeline/${novelId}/extract/confirm`, {
    method: "POST",
    body: JSON.stringify({
      expression: extracted.expression,
      event_name: extracted.event_name,
      timestamp_raw: extracted.timestamp_raw,
      chapter_reference: extracted.chapter_reference,
      character_names: extracted.character_names,
      location_name: extracted.location_name,
      confidence: extracted.confidence,
      context: extracted.context,
    }),
  });
}
