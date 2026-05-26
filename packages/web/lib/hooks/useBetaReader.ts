"use client";

/**
 * TanStack Query hooks for Beta Reader analysis.
 *
 * All hooks accept novelId as the primary key parameter.
 * Query keys follow the pattern ["analysis", novelId, ...] for cache management.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  analysisApi,
  type BetaReaderDeepDiveRequest,
  type BetaReaderDeepDiveResponse,
  type BetaReaderRequest,
  type BetaReaderResponse,
} from "@/lib/api/analysis";

// --- Query key factory ---

const analysisKeys = {
  all: (novelId: string) => ["analysis", novelId] as const,
  betaReader: (novelId: string, chapterIds: string[]) =>
    ["analysis", novelId, "beta-reader", ...chapterIds.sort()] as const,
};

// --- Mutation hooks ---

/**
 * Mutation hook for Phase 1 (full chapter analysis).
 *
 * On success, stores the result in the TanStack Query cache so other
 * components can read it without re-fetching.
 */
export function useBetaReaderAnalyze(novelId: string) {
  const queryClient = useQueryClient();

  return useMutation<BetaReaderResponse, Error, BetaReaderRequest>({
    mutationFn: (request) => analysisApi.analyze(novelId, request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(analysisKeys.betaReader(novelId, variables.chapter_ids), data);
    },
  });
}

/**
 * Mutation hook for Phase 2 (category deep-dive).
 *
 * Phase 2 results are not cached separately — the user can re-trigger
 * if needed. The cache_key from Phase 1 is passed in the request body.
 */
export function useBetaReaderDeepDive(novelId: string) {
  return useMutation<BetaReaderDeepDiveResponse, Error, BetaReaderDeepDiveRequest>({
    mutationFn: (request) => analysisApi.deepDive(novelId, request),
  });
}
