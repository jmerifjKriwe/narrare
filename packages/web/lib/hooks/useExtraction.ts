"use client";

/**
 * TanStack Query hooks for KB extraction.
 *
 * Mutation-only — extraction is a one-shot operation, not a subscription.
 * On apply success, invalidates KB query keys so the KB panel refreshes.
 * Each hook manages its own AbortController for cancel support (§16.2).
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import {
  type ApplyExtractionItem,
  type ApplyExtractionResponse,
  type ExtractionOutput,
  extractionApi,
} from "@/lib/api/extraction";

/** Extract entities from a chapter. One-shot mutation with cancel support. */
export function useExtractChapter(novelId: string, chapterId: string) {
  const abortRef = useRef<AbortController | null>(null);

  const mutation = useMutation<ExtractionOutput, Error, void>({
    mutationFn: () => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      return extractionApi.extractChapter(novelId, chapterId, abortRef.current.signal);
    },
  });

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { ...mutation, abort };
}

/** Apply selected extraction items to the KB. Invalidates KB cache on success. */
export function useApplyExtraction(novelId: string) {
  const queryClient = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);

  const mutation = useMutation<ApplyExtractionResponse, Error, ApplyExtractionItem[]>({
    mutationFn: (items) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();
      return extractionApi.applyExtraction(novelId, items, abortRef.current.signal);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["kb", novelId] });
    },
  });

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  return { ...mutation, abort };
}
