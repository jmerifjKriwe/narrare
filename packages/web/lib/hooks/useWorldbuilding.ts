"use client";

/**
 * React hooks for worldbuilding analysis — §16 AI-Interaction Standards.
 *
 * Wraps useAIOperation for lifecycle management (no manual AbortController).
 * Keeps TanStack Query cache for result sharing and KB invalidation.
 *
 * @module useWorldbuilding
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import { mapRestApiError } from "@/lib/api/ai-rest-error";
import {
  type WorldbuildingAnalysisRequest,
  type WorldbuildingAnalysisResponse,
  type WorldbuildingApplyRequestBody,
  type WorldbuildingApplyResponse,
  worldbuildingApi,
} from "@/lib/api/worldbuilding";
import {
  buildMutationReturn,
  createAbortAwareErrorMapper,
  createOnErrorCallback,
  useAbortCallback,
  useMutateAsyncFactory,
} from "@/lib/hooks/ai-mutation-adapter";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

// --- Query key factory ---

export const worldbuildingKeys = {
  all: (novelId: string) => ["worldbuilding", novelId] as const,
  analysis: (novelId: string) => [...worldbuildingKeys.all(novelId), "analysis"] as const,
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Run worldbuilding analysis (one-shot operation).
 * Stores the latest analysis in query cache on success.
 */
export function useWorldbuildingAnalyze(novelId: string) {
  const queryClient = useQueryClient();
  const optionsRef = useRef<WorldbuildingAnalysisRequest | undefined>(undefined);
  const resolveRef = useRef<((value: WorldbuildingAnalysisResponse) => void) | null>(null);
  const rejectRef = useRef<((reason: unknown) => void) | null>(null);

  const aiOp = useAIOperation<WorldbuildingAnalysisResponse>({
    execute: async (signal) => {
      return worldbuildingApi.analyze(novelId, optionsRef.current, signal);
    },
    errorMapper: createAbortAwareErrorMapper(resolveRef, rejectRef, mapRestApiError),
    onSuccess: (data) => {
      resolveRef.current?.(data);
      resolveRef.current = null;
      rejectRef.current = null;
      queryClient.setQueryData(worldbuildingKeys.analysis(novelId), data);
    },
    onError: createOnErrorCallback(resolveRef, rejectRef),
    connectionLossTimeout: 15_000,
  });

  const mutate = useCallback(
    (options?: WorldbuildingAnalysisRequest) => {
      optionsRef.current = options;
      aiOp.start();
    },
    [aiOp],
  );

  const mutateAsync = useCallback(
    (options?: WorldbuildingAnalysisRequest): Promise<WorldbuildingAnalysisResponse> => {
      return new Promise<WorldbuildingAnalysisResponse>((resolve, reject) => {
        resolveRef.current = resolve;
        rejectRef.current = reject;
        optionsRef.current = options;
        aiOp.start();
      });
    },
    [aiOp],
  );

  return buildMutationReturn(
    aiOp,
    mutate,
    mutateAsync,
    useAbortCallback(resolveRef, rejectRef, aiOp),
    optionsRef.current,
  );
}

/**
 * Apply selected connection suggestions (one-shot operation).
 * Invalidates KB and worldbuilding cache on success.
 */
export function useWorldbuildingApply(novelId: string) {
  const queryClient = useQueryClient();
  const bodyRef = useRef<WorldbuildingApplyRequestBody | null>(null);
  const resolveRef = useRef<((value: WorldbuildingApplyResponse) => void) | null>(null);
  const rejectRef = useRef<((reason: unknown) => void) | null>(null);

  const aiOp = useAIOperation<WorldbuildingApplyResponse>({
    execute: async (signal) => {
      const body = bodyRef.current;
      if (!body) throw new Error("No request body provided");
      return worldbuildingApi.applyConnections(novelId, body, signal);
    },
    errorMapper: createAbortAwareErrorMapper(resolveRef, rejectRef, mapRestApiError),
    onSuccess: (data) => {
      resolveRef.current?.(data);
      resolveRef.current = null;
      rejectRef.current = null;
      void queryClient.invalidateQueries({ queryKey: ["kb", novelId] });
      void queryClient.invalidateQueries({ queryKey: worldbuildingKeys.all(novelId) });
    },
    onError: createOnErrorCallback(resolveRef, rejectRef),
    connectionLossTimeout: 15_000,
  });

  const mutate = useCallback(
    (body: WorldbuildingApplyRequestBody) => {
      bodyRef.current = body;
      aiOp.start();
    },
    [aiOp],
  );

  return buildMutationReturn(
    aiOp,
    mutate,
    useMutateAsyncFactory(bodyRef, resolveRef, rejectRef, aiOp),
    useAbortCallback(resolveRef, rejectRef, aiOp),
    bodyRef.current,
  );
}
