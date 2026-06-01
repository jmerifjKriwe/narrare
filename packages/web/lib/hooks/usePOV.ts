"use client";

/**
 * TanStack Query hooks for POV Analysis (ANAL-004).
 *
 * Follows the useReadability pattern exactly.
 * Mutation-based since POV analysis is user-triggered.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { analysisApi, type POVRequest, type POVResult } from "@/lib/api/analysis";

// --- Query key factory ---

const analysisKeys = {
  pov: (novelId: string, chapterIds: string[]) =>
    ["analysis", novelId, "pov", ...chapterIds.sort()] as const,
};

// --- Mutation hooks ---

/**
 * Mutation hook for POV analysis.
 *
 * On success, stores the result in the TanStack Query cache so other
 * components can read it without re-fetching.
 */
export function usePOVAnalysis(novelId: string) {
  const queryClient = useQueryClient();

  return useMutation<POVResult, Error, POVRequest>({
    mutationFn: (request) => analysisApi.analyzePOV(novelId, request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(analysisKeys.pov(novelId, variables.chapter_ids), data);
    },
  });
}
