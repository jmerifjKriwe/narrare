"use client";

/**
 * React hooks for KB extraction — §16 AI-Interaction Standards.
 *
 * Wraps useAIOperation for lifecycle management (no manual AbortController).
 * Keeps TanStack Query cache for KB invalidation on apply.
 *
 * @module useExtraction
 */

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import { mapRestApiError } from "@/lib/api/ai-rest-error";
import {
  type ApplyExtractionItem,
  type ApplyExtractionResponse,
  type ExtractionOutput,
  extractionApi,
} from "@/lib/api/extraction";
import {
  buildMutationReturn,
  createAbortAwareErrorMapper,
  createOnErrorCallback,
  useAbortCallback,
  useMutateAsyncFactory,
} from "@/lib/hooks/ai-mutation-adapter";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";

/** Extract entities from a chapter. One-shot operation with cancel support. */
export function useExtractChapter(novelId: string, chapterId: string) {
  const resolveRef = useRef<((value: ExtractionOutput) => void) | null>(null);
  const rejectRef = useRef<((reason: unknown) => void) | null>(null);

  const aiOp = useAIOperation<ExtractionOutput>({
    execute: (signal) => extractionApi.extractChapter(novelId, chapterId, signal),
    errorMapper: createAbortAwareErrorMapper(resolveRef, rejectRef, mapRestApiError),
    onSuccess: (data) => {
      resolveRef.current?.(data);
      resolveRef.current = null;
      rejectRef.current = null;
    },
    onError: createOnErrorCallback(resolveRef, rejectRef),
    connectionLossTimeout: 15_000,
  });

  const mutate = useCallback(
    (_void: undefined) => {
      aiOp.start();
    },
    [aiOp],
  );

  const mutateAsync = useCallback((): Promise<ExtractionOutput> => {
    return new Promise<ExtractionOutput>((resolve, reject) => {
      resolveRef.current = resolve;
      rejectRef.current = reject;
      aiOp.start();
    });
  }, [aiOp]);

  const abort = useAbortCallback(resolveRef, rejectRef, aiOp);

  return {
    state: aiOp.state,
    start: aiOp.start,
    cancel: aiOp.cancel,
    retry: aiOp.retry,
    reset: aiOp.reset,
    notifyData: aiOp.notifyData,
    isIdle: aiOp.isIdle,
    isLoading: aiOp.isLoading,
    isStreaming: aiOp.isStreaming,
    isComplete: aiOp.isComplete,
    isError: aiOp.isError,
    isConnectionLost: aiOp.isConnectionLost,
    mutate,
    mutateAsync,
    abort,
    isPending: aiOp.isLoading || aiOp.isStreaming,
    data: aiOp.state.result,
    error: aiOp.state.error ? new Error(aiOp.state.error.userMessage) : null,
    isSuccess: aiOp.state.status === "complete",
  };
}

/** Apply selected extraction items to the KB. Invalidates KB cache on success. */
export function useApplyExtraction(novelId: string) {
  const queryClient = useQueryClient();
  const itemsRef = useRef<ApplyExtractionItem[] | null>(null);
  const resolveRef = useRef<((value: ApplyExtractionResponse) => void) | null>(null);
  const rejectRef = useRef<((reason: unknown) => void) | null>(null);

  const aiOp = useAIOperation<ApplyExtractionResponse>({
    execute: async (signal) => {
      const items = itemsRef.current;
      if (!items) throw new Error("No items to apply");
      return extractionApi.applyExtraction(novelId, items, signal);
    },
    errorMapper: createAbortAwareErrorMapper(resolveRef, rejectRef, mapRestApiError),
    onSuccess: (data) => {
      resolveRef.current?.(data);
      resolveRef.current = null;
      rejectRef.current = null;
      void queryClient.invalidateQueries({ queryKey: ["kb", novelId] });
    },
    onError: createOnErrorCallback(resolveRef, rejectRef),
    connectionLossTimeout: 15_000,
  });

  const mutate = useCallback(
    (items: ApplyExtractionItem[]) => {
      itemsRef.current = items;
      aiOp.start();
    },
    [aiOp],
  );

  return buildMutationReturn(
    aiOp,
    mutate,
    useMutateAsyncFactory(itemsRef, resolveRef, rejectRef, aiOp),
    useAbortCallback(resolveRef, rejectRef, aiOp),
    itemsRef.current,
  );
}
