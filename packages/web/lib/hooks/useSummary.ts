"use client";

/**
 * TanStack Query hooks for chapter summary.
 *
 * The mutation hook invalidates the novel-scoped chapter cache family
 * (`["novels", novelId, "chapters"]`) on success so that chapter data
 * (with updated summary) is refreshed.
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
      // Invalidate the novel-scoped chapter cache family (prefix match).
      // Summarization rewrites the chapter's `summary` and bumps `updated_at`
      // server-side, staling: the chapter-detail entry
      // `["novels", novelId, "chapters", chapterId]` (carries `summary`),
      // this chapter's plan-context entry (carries chapter + neighbor
      // summaries), and the ChapterSummary[] list caches (carry `updated_at`).
      // The previously invalidated key (`"chapters"` at the root of the key
      // array) matched no query in the app (dead key — its consumers moved to
      // the novel-scoped family), so cached chapter data never refreshed.
      void queryClient.invalidateQueries({ queryKey: ["novels", novelId, "chapters"] });
    },
  });
}
