"use client";

/**
 * TanStack Query hooks for Sentiment Analysis (ANAL-002).
 *
 * Follows the useBetaReader pattern exactly.
 * Mutation-based since sentiment analysis is user-triggered.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { analysisApi, type SentimentOverview, type SentimentRequest } from "@/lib/api/analysis";

// --- Query key factory ---

const analysisKeys = {
  all: (novelId: string) => ["analysis", novelId] as const,
  sentiment: (novelId: string, chapterIds: string[]) =>
    ["analysis", novelId, "sentiment", ...chapterIds.sort()] as const,
};

// --- Mutation hooks ---

/**
 * Mutation hook for sentiment analysis.
 *
 * On success, stores the result in the TanStack Query cache so other
 * components can read it without re-fetching.
 */
export function useSentimentAnalyze(novelId: string) {
  const queryClient = useQueryClient();

  return useMutation<SentimentOverview[], Error, SentimentRequest>({
    mutationFn: (request) => analysisApi.sentiment(novelId, request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(analysisKeys.sentiment(novelId, variables.chapter_ids), data);
    },
  });
}
