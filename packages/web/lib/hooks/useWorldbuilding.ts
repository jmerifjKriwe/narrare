"use client";

/**
 * TanStack Query hooks for worldbuilding analysis.
 *
 * Both endpoints are POST mutations — analysis results are ephemeral
 * and tied to the analysis request. The latest analysis is stored in
 * query cache for the apply flow to reference.
 * Each hook manages its own AbortController for cancel support (§16.2).
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import {
  type WorldbuildingAnalysisRequest,
  type WorldbuildingAnalysisResponse,
  type WorldbuildingApplyRequestBody,
  type WorldbuildingApplyResponse,
  worldbuildingApi,
} from "@/lib/api/worldbuilding";

// --- Query key factory ---

export const worldbuildingKeys = {
  all: (novelId: string) => ["worldbuilding", novelId] as const,
  analysis: (novelId: string) => [...worldbuildingKeys.all(novelId), "analysis"] as const,
};

// --- Hooks ---

/**
 * Run worldbuilding analysis (mutation).
 *
 * On success, stores the latest analysis in query cache so the
 * apply flow can reference it without keeping it in component state.
 */
export function useWorldbuildingAnalyze(novelId: string) {
  const queryClient = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);

  const mutation = useMutation<
    WorldbuildingAnalysisResponse,
    Error,
    WorldbuildingAnalysisRequest | undefined
  >({
    mutationFn: (options) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      return worldbuildingApi.analyze(novelId, options, abortRef.current.signal);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(worldbuildingKeys.analysis(novelId), data);
    },
  });

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { ...mutation, abort };
}

/**
 * Apply selected connection suggestions (mutation).
 *
 * Invalidates both KB entries/relationships and worldbuilding cache
 * after successfully creating new relationships.
 */
export function useWorldbuildingApply(novelId: string) {
  const queryClient = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);

  const mutation = useMutation<WorldbuildingApplyResponse, Error, WorldbuildingApplyRequestBody>({
    mutationFn: (body) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      return worldbuildingApi.applyConnections(novelId, body, abortRef.current.signal);
    },
    onSuccess: () => {
      // Invalidate KB entries and relationships after applying connections
      void queryClient.invalidateQueries({ queryKey: ["kb", novelId] });
      void queryClient.invalidateQueries({
        queryKey: worldbuildingKeys.all(novelId),
      });
    },
  });

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { ...mutation, abort };
}
