"use client";

/**
 * React hooks for Beta Reader analysis — §16 AI-Interaction Standards.
 *
 * Wraps useAIOperation for lifecycle management (no manual AbortController).
 * Keeps TanStack Query cache for result sharing between components.
 *
 * @module useBetaReader
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import { mapRestApiError } from "@/lib/api/ai-rest-error";
import {
  analysisApi,
  type BetaReaderDeepDiveRequest,
  type BetaReaderDeepDiveResponse,
  type BetaReaderRequest,
  type BetaReaderResponse,
} from "@/lib/api/analysis";
import {
  buildMutationReturn,
  createAbortAwareErrorMapper,
  createOnErrorCallback,
  createOnSuccessCallback,
  useAbortCallback,
  useMutateAsyncFactory,
} from "@/lib/hooks/ai-mutation-adapter";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

// --- Query key factory ---

const analysisKeys = {
  all: (novelId: string) => ["analysis", novelId] as const,
  betaReader: (novelId: string, chapterIds: string[]) =>
    ["analysis", novelId, "beta-reader", ...chapterIds.sort()] as const,
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Mutation hook for Phase 1 (full chapter analysis).
 * On success, stores result in TanStack Query cache.
 */
export function useBetaReaderAnalyze(novelId: string) {
  const queryClient = useQueryClient();
  const requestRef = useRef<BetaReaderRequest | null>(null);
  const resolveRef = useRef<((value: BetaReaderResponse) => void) | null>(null);
  const rejectRef = useRef<((reason: unknown) => void) | null>(null);

  const aiOp = useAIOperation<BetaReaderResponse>({
    execute: async (signal) => {
      const request = requestRef.current;
      if (!request) throw new Error("No request parameters provided");
      return analysisApi.analyze(novelId, request, signal);
    },
    errorMapper: createAbortAwareErrorMapper(resolveRef, rejectRef, mapRestApiError),
    onSuccess: (data) => {
      resolveRef.current?.(data);
      resolveRef.current = null;
      rejectRef.current = null;
      const request = requestRef.current;
      if (request) {
        queryClient.setQueryData(analysisKeys.betaReader(novelId, request.chapter_ids), data);
      }
    },
    onError: createOnErrorCallback(resolveRef, rejectRef),
    connectionLossTimeout: 15_000,
  });

  const mutate = useCallback(
    (request: BetaReaderRequest) => {
      requestRef.current = request;
      aiOp.start();
    },
    [aiOp],
  );

  return buildMutationReturn(
    aiOp,
    mutate,
    useMutateAsyncFactory(requestRef, resolveRef, rejectRef, aiOp),
    useAbortCallback(resolveRef, rejectRef, aiOp),
    requestRef.current,
  );
}

/**
 * Mutation hook for Phase 2 (category deep-dive).
 * Phase 2 results are not cached separately.
 */
export function useBetaReaderDeepDive(novelId: string) {
  const requestRef = useRef<BetaReaderDeepDiveRequest | null>(null);
  const resolveRef = useRef<((value: BetaReaderDeepDiveResponse) => void) | null>(null);
  const rejectRef = useRef<((reason: unknown) => void) | null>(null);

  const aiOp = useAIOperation<BetaReaderDeepDiveResponse>({
    execute: async (signal) => {
      const request = requestRef.current;
      if (!request) throw new Error("No request parameters provided");
      return analysisApi.deepDive(novelId, request, signal);
    },
    errorMapper: createAbortAwareErrorMapper(resolveRef, rejectRef, mapRestApiError),
    onSuccess: createOnSuccessCallback(resolveRef, rejectRef),
    onError: createOnErrorCallback(resolveRef, rejectRef),
    connectionLossTimeout: 15_000,
  });

  const mutate = useCallback(
    (request: BetaReaderDeepDiveRequest) => {
      requestRef.current = request;
      aiOp.start();
    },
    [aiOp],
  );

  return buildMutationReturn(
    aiOp,
    mutate,
    useMutateAsyncFactory(requestRef, resolveRef, rejectRef, aiOp),
    useAbortCallback(resolveRef, rejectRef, aiOp),
    requestRef.current,
  );
}
