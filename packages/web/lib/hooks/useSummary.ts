"use client";

/**
 * TanStack Query hooks for chapter summary.
 *
 * Query keys follow the pattern ["summary", ...] for cache management.
 * The mutation hook invalidates chapter queries on success so that
 * chapter data (with updated summary) is refreshed.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type SummarizeRequest, summaryApi } from "@/lib/api/summary";

/** Mutation hook to trigger chapter summarization. */
export function useSummarizeChapter(chapterId: string, novelId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (options?: SummarizeRequest) =>
      summaryApi.summarizeChapter(chapterId, novelId, options),
    onSuccess: () => {
      // Invalidate chapter queries so the summary appears in chapter data
      void queryClient.invalidateQueries({ queryKey: ["chapters", chapterId] });
    },
  });
}
