"use client";

/**
 * TanStack Query hooks for KB entry improvement analysis and application.
 *
 * Uses mutations (not queries) because analysis is a server-side computation
 * triggered on demand, not a cached resource. Results are stored in the
 * query cache for panel state management.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  type KBImproveAnalysisResponse,
  type KBImproveApplyResponse,
  kbImproveApi,
} from "@/lib/api/kb-improve";

// --- Query key helpers ---

const improveKeys = {
  analysis: (novelId: string, entryId: string) => ["kb", novelId, "improve", entryId] as const,
};

// --- Mutation hooks ---

/**
 * Analyze a KB entry for AI-powered improvement suggestions.
 * On success, caches the analysis result so the panel can read it.
 */
export function useKBImproveAnalysis(novelId: string, entryId: string) {
  const queryClient = useQueryClient();
  return useMutation<KBImproveAnalysisResponse, Error>({
    mutationFn: () => kbImproveApi.analyzeEntry(novelId, entryId),
    onSuccess: (data) => {
      queryClient.setQueryData(improveKeys.analysis(novelId, entryId), data);
    },
  });
}

/**
 * Apply selected improvement suggestions to a KB entry.
 * Invalidates the entry detail cache so the panel reflects changes.
 */
export function useKBImproveApply(novelId: string, entryId: string) {
  const queryClient = useQueryClient();
  return useMutation<KBImproveApplyResponse, Error, number[]>({
    mutationFn: (suggestionIds: number[]) =>
      kbImproveApi.applyImprovements(novelId, entryId, suggestionIds),
    onSuccess: () => {
      // Invalidate entry list and detail caches — body/metadata may have changed
      void queryClient.invalidateQueries({ queryKey: ["kb", novelId, "entries"] });
      void queryClient.invalidateQueries({
        queryKey: ["kb", novelId, "entries", entryId],
      });
      // Invalidate the analysis cache so a fresh analysis starts next time
      void queryClient.invalidateQueries({
        queryKey: improveKeys.analysis(novelId, entryId),
      });
    },
  });
}
