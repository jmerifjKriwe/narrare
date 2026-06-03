"use client";

/**
 * TanStack Query hooks for Timeline events and analysis.
 *
 * All hooks accept novelId as the primary key parameter.
 * Query keys follow the pattern ["timeline", novelId, ...] for cache management.
 * Mutations invalidate related queries on success.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { confirmExtractedEvent, extractExpressionsSSE, timelineApi } from "@/lib/api/timeline";
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

// --- Query key factory ---

const timelineKeys = {
  all: (novelId: string) => ["timeline", novelId] as const,
  events: (novelId: string) => [...timelineKeys.all(novelId), "events"] as const,
  eventsFiltered: (novelId: string, filters: TimelineFilters | undefined) =>
    [...timelineKeys.events(novelId), filters ?? {}] as const,
  event: (novelId: string, eventId: string) => [...timelineKeys.events(novelId), eventId] as const,
  analysis: (novelId: string) => [...timelineKeys.all(novelId), "analysis"] as const,
  consistency: (novelId: string) => [...timelineKeys.all(novelId), "consistency"] as const,
  characterAges: (novelId: string) => [...timelineKeys.all(novelId), "character-ages"] as const,
};

// --- Query hooks ---

/** Fetch timeline events for a novel, with optional filters. */
export function useTimelineEvents(novelId: string, filters?: TimelineFilters) {
  return useQuery<TimelineEvent[]>({
    queryKey: timelineKeys.eventsFiltered(novelId, filters),
    queryFn: () => timelineApi.listEvents(novelId, filters),
    enabled: !!novelId,
  });
}

/** Fetch a single timeline event by ID. */
export function useTimelineEvent(novelId: string, eventId: string) {
  return useQuery<TimelineEvent>({
    queryKey: timelineKeys.event(novelId, eventId),
    queryFn: () => timelineApi.getEvent(novelId, eventId),
    enabled: !!novelId && !!eventId,
  });
}

/** Fetch AI-generated timeline analysis for a novel. */
export function useTimelineAnalysis(novelId: string) {
  return useQuery<TimelineAnalysis>({
    queryKey: timelineKeys.analysis(novelId),
    queryFn: () => timelineApi.getAnalysis(novelId),
    enabled: !!novelId,
  });
}

// --- Mutation hooks ---

/** Create a new timeline event. Invalidates the events list on success. */
export function useCreateTimelineEvent(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation<TimelineEvent, Error, TimelineEventCreateRequest>({
    mutationFn: (data) => timelineApi.createEvent(novelId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: timelineKeys.events(novelId) });
    },
  });
}

/** Update a timeline event. Invalidates the events list and single event on success. */
export function useUpdateTimelineEvent(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation<TimelineEvent, Error, { eventId: string; data: TimelineEventUpdateRequest }>({
    mutationFn: ({ eventId, data }) => timelineApi.updateEvent(novelId, eventId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: timelineKeys.events(novelId) });
      void queryClient.invalidateQueries({
        queryKey: timelineKeys.event(novelId, variables.eventId),
      });
    },
  });
}

/** Delete a timeline event. Invalidates the events list on success. */
export function useDeleteTimelineEvent(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (eventId) => timelineApi.deleteEvent(novelId, eventId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: timelineKeys.events(novelId) });
    },
  });
}

// --- Phase 2: Extraction & Consistency ---

/**
 * Extract temporal expressions from chapters via SSE streaming.
 * Events are accumulated progressively as SSE chunks arrive.
 * Invalidates the events list on completion.
 *
 * Returns control functions for managing extraction state.
 */
export function useSSEExtraction(novelId: string) {
  const queryClient = useQueryClient();
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractedEvents, setExtractedEvents] = useState<ExtractedEvent[]>([]);
  const [extractError, setExtractError] = useState<string | null>(null);

  const startExtraction = useCallback(
    (chapterIds: string[]) => {
      setIsExtracting(true);
      setExtractedEvents([]);
      setExtractError(null);

      const abortController = new AbortController();

      extractExpressionsSSE(
        novelId,
        chapterIds,
        {
          onEvent: (event) => {
            setExtractedEvents((prev) => [...prev, event]);
          },
          onComplete: () => {
            setIsExtracting(false);
            void queryClient.invalidateQueries({ queryKey: timelineKeys.events(novelId) });
          },
          onError: (error) => {
            setIsExtracting(false);
            setExtractError(error.message);
          },
        },
        abortController.signal,
      );

      return () => abortController.abort();
    },
    [novelId, queryClient],
  );

  const reset = useCallback(() => {
    setExtractedEvents([]);
    setExtractError(null);
  }, []);

  return { isExtracting, extractedEvents, extractError, startExtraction, reset };
}

/**
 * Confirm an extracted expression and persist it as a timeline event.
 * Preserves source='extracted', confidence, and is_confirmed metadata.
 * Invalidates the events list on success.
 */
export function useConfirmExtractedEvent(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation<TimelineEvent, Error, ExtractedEvent>({
    mutationFn: (extracted) => confirmExtractedEvent(novelId, extracted),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: timelineKeys.events(novelId) });
    },
  });
}

/** Check temporal consistency for a novel. Query with auto-refetch. */
export function useTimelineConsistency(novelId: string) {
  return useQuery<TemporalConsistency>({
    queryKey: timelineKeys.consistency(novelId),
    queryFn: () => timelineApi.checkConsistency(novelId),
    enabled: !!novelId,
  });
}

// --- Phase 3: Character Ages ---

/** Fetch character age report from KB metadata. */
export function useCharacterAges(novelId: string) {
  return useQuery<CharacterAgeReport>({
    queryKey: timelineKeys.characterAges(novelId),
    queryFn: () => timelineApi.getCharacterAges(novelId),
    enabled: !!novelId,
  });
}
