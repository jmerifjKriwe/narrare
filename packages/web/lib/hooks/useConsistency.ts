"use client";

/**
 * TanStack Query hooks for Consistency Checker (CONS-001).
 *
 * Follows the useBetaReader pattern exactly.
 * Mutation-based since consistency checks are user-triggered.
 */

import { useMutation } from "@tanstack/react-query";
import { analysisApi, type ConsistencyRequest, type ConsistencyResponse } from "@/lib/api/analysis";

// --- Mutation hooks ---

/**
 * Mutation hook for cross-chapter consistency check.
 *
 * POST /consistency/check?novel_id={novelId}
 */
export function useConsistencyCheck(novelId: string) {
  return useMutation<ConsistencyResponse, Error, ConsistencyRequest>({
    mutationFn: (request) => analysisApi.consistencyCheck(novelId, request),
  });
}

/**
 * Mutation hook for single-chapter consistency check.
 *
 * POST /consistency/chapters/{chapterId}/check?novel_id={novelId}
 */
export function useConsistencyCheckChapter(novelId: string, chapterId: string) {
  return useMutation<ConsistencyResponse, Error, ConsistencyRequest>({
    mutationFn: (request) => analysisApi.consistencyCheckChapter(novelId, chapterId, request),
  });
}
