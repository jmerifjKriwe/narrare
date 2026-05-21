"use client";

/**
 * TanStack Query hooks for memory/feedback/learning.
 *
 * Query keys follow the pattern ["memory", projectId, ...] for cache management.
 * Mutation hooks invalidate preference queries on success.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memoryApi } from "@/lib/api/memory";

// --- Query key factory ---

const memoryKeys = {
  all: (projectId: string) => ["memory", projectId] as const,
  preferences: (projectId: string) => [...memoryKeys.all(projectId), "preferences"] as const,
  status: (projectId: string) => [...memoryKeys.all(projectId), "status"] as const,
};

// --- Query hooks ---

/** Fetch the preference profile for a project. Returns null if no profile yet. */
export function usePreferences(projectId: string | null) {
  return useQuery({
    queryKey: memoryKeys.preferences(projectId ?? ""),
    queryFn: () => memoryApi.getPreferences(projectId!),
    enabled: !!projectId,
  });
}

/** Fetch memory status info (event count, confidence) derived from preferences. */
export function useMemoryStatus(projectId: string | null) {
  const query = useQuery({
    queryKey: memoryKeys.status(projectId ?? ""),
    queryFn: () => memoryApi.getPreferences(projectId!),
    enabled: !!projectId,
    // Refetch every 60s to keep status fresh during writing sessions
    refetchInterval: 60_000,
  });

  return {
    ...query,
    eventCount: query.data?.event_count ?? 0,
    confidence: query.data?.confidence ?? 0,
    hasProfile: !!query.data && query.data.event_count > 0,
  };
}

// --- Mutation hooks ---

/** Mutation hook for recording feedback on AI suggestions. */
export function useRecordFeedback(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: memoryApi.recordFeedback,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: memoryKeys.all(projectId) });
    },
  });
}

/** Mutation hook for resetting all preferences for a project. */
export function useResetPreferences(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => memoryApi.resetPreferences(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: memoryKeys.all(projectId) });
    },
  });
}

/** Mutation hook for triggering preference analysis. */
export function useTriggerAnalysis(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => memoryApi.triggerAnalysis({ project_id: projectId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: memoryKeys.all(projectId) });
    },
  });
}
