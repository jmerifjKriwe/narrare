"use client";

/**
 * TanStack Query hooks for KB extraction.
 *
 * Mutation-only — extraction is a one-shot operation, not a subscription.
 * On apply success, invalidates KB query keys so the KB panel refreshes.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  type ApplyExtractionItem,
  type ApplyExtractionResponse,
  type ExtractionOutput,
  extractionApi,
} from "@/lib/api/extraction";

/** Extract entities from a chapter. One-shot mutation. */
export function useExtractChapter(novelId: string, chapterId: string) {
  return useMutation<ExtractionOutput, Error, void>({
    mutationFn: () => extractionApi.extractChapter(novelId, chapterId),
  });
}

/** Apply selected extraction items to the KB. Invalidates KB cache on success. */
export function useApplyExtraction(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation<ApplyExtractionResponse, Error, ApplyExtractionItem[]>({
    mutationFn: (items) => extractionApi.applyExtraction(novelId, items),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["kb", novelId] });
    },
  });
}
