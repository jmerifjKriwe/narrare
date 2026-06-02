"use client";

/**
 * TanStack Query hooks for Beta Reader analysis.
 *
 * All hooks accept novelId as the primary key parameter.
 * Query keys follow the pattern ["analysis", novelId, ...] for cache management.
 * Each hook manages its own AbortController for cancel support (§16.2).
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
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
  const abortRef = useRef<AbortController | null>(null);

  const mutation = useMutation<BetaReaderResponse, Error, BetaReaderRequest>({
    mutationFn: (request) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      return analysisApi.analyze(novelId, request, abortRef.current.signal);
    },
    onSuccess: (data, variables) => {
      queryClient.setQueryData(analysisKeys.betaReader(novelId, variables.chapter_ids), data);
    },
  });

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { ...mutation, abort };
}

/**
 * Mutation hook for Phase 2 (category deep-dive).
 *
 * Phase 2 results are not cached separately — the user can re-trigger
 * if needed. The cache_key from Phase 1 is passed in the request body.
 */
export function useBetaReaderDeepDive(novelId: string) {
  const abortRef = useRef<AbortController | null>(null);

  const mutation = useMutation<BetaReaderDeepDiveResponse, Error, BetaReaderDeepDiveRequest>({
    mutationFn: (request) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      return analysisApi.deepDive(novelId, request, abortRef.current.signal);
    },
  });

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { ...mutation, abort };
}
