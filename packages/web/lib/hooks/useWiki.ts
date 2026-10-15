"use client";

/**
 * TanStack Query hooks for Wiki summaries.
 *
 * All hooks accept novelId as the primary key parameter.
 * Query keys follow the pattern ["wiki", novelId, ...] for cache management.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/core";
import {
  type WikiChapterSummaryResponse,
  type WikiIndexResponse,
  type WikiRefreshResponse,
  type WikiSummaryListResponse,
  type WikiSummaryResponse,
  wikiApi,
} from "@/lib/api/wiki";

// --- Query key factory ---

const wikiKeys = {
  all: (novelId: string) => ["wiki", novelId] as const,
  summaries: (novelId: string) => [...wikiKeys.all(novelId), "summaries"] as const,
  summary: (novelId: string, entityId: string) =>
    [...wikiKeys.summaries(novelId), entityId] as const,
  chapterSummary: (novelId: string, chapterId: string) =>
    [...wikiKeys.all(novelId), "chapter", chapterId] as const,
  index: (novelId: string) => [...wikiKeys.all(novelId), "index"] as const,
};

// --- Query hooks ---

/** Fetch a single wiki summary for a given entity. */
export function useWikiSummary(novelId: string, entityId: string) {
  return useQuery<WikiSummaryResponse>({
    queryKey: wikiKeys.summary(novelId, entityId),
    queryFn: () => wikiApi.getSummary(novelId, entityId),
    enabled: !!novelId && !!entityId,
  });
}

/** Fetch a list of wiki summaries, optionally filtered by entity IDs. */
export function useWikiSummaries(novelId: string, entityIds?: string[]) {
  return useQuery<WikiSummaryListResponse>({
    queryKey: [...wikiKeys.summaries(novelId), entityIds ?? []] as const,
    queryFn: () => wikiApi.getSummaries(novelId, entityIds),
    enabled: !!novelId,
  });
}

/** Fetch a chapter-level wiki summary. */
export function useWikiChapterSummary(novelId: string, chapterId: string) {
  return useQuery<WikiChapterSummaryResponse | null>({
    queryKey: wikiKeys.chapterSummary(novelId, chapterId),
    queryFn: async () => {
      try {
        return await wikiApi.getChapterSummary(novelId, chapterId);
      } catch (error) {
        // N20: "never generated" is this endpoint's 404 contract state,
        // not an error — map it to null so the panel renders its
        // existing kb.wiki.noSummaryYet empty state.
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    enabled: !!novelId && !!chapterId,
  });
}

/** Fetch wiki index/health metadata for a novel. */
export function useWikiIndex(novelId: string) {
  return useQuery<WikiIndexResponse>({
    queryKey: wikiKeys.index(novelId),
    queryFn: () => wikiApi.getWikiIndex(novelId),
    enabled: !!novelId,
  });
}

// --- Mutation hooks ---

/** Refresh a wiki summary. Invalidates the summary and index caches on success. */
export function useWikiRefresh(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation<WikiRefreshResponse, Error, { entityId: string; force?: boolean }>({
    mutationFn: ({ entityId, force }) => wikiApi.refreshSummary(novelId, entityId, force),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: wikiKeys.summary(novelId, variables.entityId),
      });
      void queryClient.invalidateQueries({ queryKey: wikiKeys.summaries(novelId) });
      void queryClient.invalidateQueries({ queryKey: wikiKeys.index(novelId) });
    },
  });
}

/** Mark all wiki summaries as stale. Invalidates caches on success. */
export function useWikiMarkStale(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation<{ count: number }, Error, string | undefined>({
    mutationFn: (promptVersion?: string) => wikiApi.markStale(novelId, promptVersion),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: wikiKeys.all(novelId) });
    },
  });
}
