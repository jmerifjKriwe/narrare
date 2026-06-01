"use client";

/**
 * TanStack Query hooks for Timeline events and analysis.
 *
 * All hooks accept novelId as the primary key parameter.
 * Query keys follow the pattern ["timeline", novelId, ...] for cache management.
 * Mutations invalidate related queries on success.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { timelineApi } from "@/lib/api/timeline";
import type {
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
