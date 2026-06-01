"use client";

/**
 * TanStack Query hooks for Readability Analysis (ANAL-003).
 *
 * Follows the useSentiment pattern exactly.
 * Mutation-based since readability analysis is user-triggered.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { analysisApi, type ReadabilityRequest, type ReadabilityResult } from "@/lib/api/analysis";

// --- Query key factory ---

const analysisKeys = {
  readability: (novelId: string, chapterIds: string[]) =>
    ["analysis", novelId, "readability", ...chapterIds.sort()] as const,
};

// --- Mutation hooks ---

/**
 * Mutation hook for readability analysis.
 *
 * On success, stores the result in the TanStack Query cache so other
 * components can read it without re-fetching.
 */
export function useReadabilityAnalysis(novelId: string) {
  const queryClient = useQueryClient();

  return useMutation<ReadabilityResult[], Error, ReadabilityRequest>({
    mutationFn: (request) => analysisApi.readability(novelId, request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(analysisKeys.readability(novelId, variables.chapter_ids), data);
    },
  });
}
