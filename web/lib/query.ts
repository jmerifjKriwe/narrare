import {
  QueryClient,
  useMutation,
  useQuery,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  client,
  type Entity,
  type Hit,
  type Job,
  type Novel,
  type NovelCreate,
  type Suggestion,
} from "./api/client";

/**
 * The one query client. `retry: false` because the backend is a local
 * service: it is either up or the page reports the outage itself, and a
 * retry only delays that report. `staleTime: 30_000` because an answer is
 * recent enough for half a minute, so a remount reads the cache instead of
 * asking again.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 30_000,
    },
  },
});

/**
 * The stored settings row, as `{ locale }` — the same contract the boot
 * effect in the shell used to own: an answer carries the row's locale, an
 * unreachable service resolves to `locale: null`, and the browser's
 * language decides from there. The outage is an answer, not an error
 * state, so no consumer needs a fallback branch of its own.
 */
export function useSettingsQuery(): UseQueryResult<{ locale: string | null }> {
  return useQuery({
    queryKey: ["settings"],
    // No refetch on window focus: a focus refetch while the service is down
    // would erase the locale adopted at boot. The row changes only through
    // the switcher, which invalidates this key itself.
    refetchOnWindowFocus: false,
    queryFn: async () => {
      try {
        const { data } = await client.GET("/api/settings");
        return { locale: data?.locale ?? null };
      } catch {
        return { locale: null };
      }
    },
  });
}

/**
 * The library list, cached under the writing capability's `["novels"]` key.
 * An answer that is not ok throws, so the cache holds either the list or
 * the failure — never a half-current list.
 */
export function useNovelsQuery(): UseQueryResult<Novel[]> {
  return useQuery({
    queryKey: ["novels"],
    queryFn: async () => {
      const { data, response } = await client.GET("/api/writing/novels");
      if (!response.ok) throw new Error(`novels unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/**
 * Creating a novel: the first mutation under the spec 5.10 convention. The
 * write invalidates `["novels"]` instead of patching the cached list by
 * hand, so every view of the key refetches from the row that changed. The
 * list updates when that refetch lands; the caller's own state (the form)
 * does not wait for it.
 */
export function useCreateNovel(): UseMutationResult<Novel, Error, NovelCreate> {
  return useMutation({
    mutationFn: async (input: NovelCreate) => {
      const { data, response } = await client.POST("/api/writing/novels", { body: input });
      if (!response.ok || !data) throw new Error(`create refused: ${response.status}`);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
    },
  });
}

/**
 * A durable job's row (spec §9 D10): the UI polls the state, never a
 * connection to the work. The poll lives here as the one place that knows a
 * queued or running row is still provisional — `refetchInterval` answers a
 * second while the work is outstanding and `false` on done or failed, so
 * the polling stops exactly when the row stops moving. No timer outlives
 * the answer, whatever surface mounted this query.
 *
 * `null` disables the query: a dock with no job enqueued asks nothing.
 */
export function useJobQuery(jobId: string | null): UseQueryResult<Job> {
  return useQuery({
    queryKey: ["jobs", jobId],
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 1000 : false;
    },
    queryFn: async () => {
      if (jobId === null) throw new Error("no job to poll");
      const { data, response } = await client.GET("/api/jobs/{job_id}", {
        params: { path: { job_id: jobId } },
      });
      if (!response.ok || !data) throw new Error(`job unavailable: ${response.status}`);
      return data;
    },
  });
}

/**
 * The novel's entities under the knowledge capability's key. An answer that
 * is not ok throws, so the cache holds either the list or the failure —
 * never a half-current list.
 */
export function useEntitiesQuery(novelId: string): UseQueryResult<Entity[]> {
  return useQuery({
    queryKey: ["knowledge", "entities", novelId],
    queryFn: async () => {
      const { data, response } = await client.GET(
        "/api/knowledge/novels/{novel_id}/entities",
        { params: { path: { novel_id: novelId } } },
      );
      if (!response.ok) throw new Error(`entities unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/** The pending review queue: the suggestions waiting for a decision. */
export function usePendingSuggestionsQuery(novelId: string): UseQueryResult<Suggestion[]> {
  return useQuery({
    queryKey: ["knowledge", "suggestions", novelId],
    queryFn: async () => {
      const { data, response } = await client.GET(
        "/api/knowledge/novels/{novel_id}/suggestions",
        { params: { path: { novel_id: novelId }, query: { status: "pending" } } },
      );
      if (!response.ok) throw new Error(`suggestions unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/**
 * The dock search's second tier: the box's text asked of the semantic
 * search. The ask is debounced (300ms) — the instant tier of the box is
 * the client-side entity filter, and the server's answer is owed only
 * once the typing pauses, so a word typed a letter at a time is one
 * request, not one per keystroke. The key carries the debounced text, so
 * every answer is cached under the words that produced it, and an empty
 * query asks nothing (`enabled`).
 */
export function usePassageSearch(query: string): UseQueryResult<Hit[]> {
  const [debounced, setDebounced] = useState(query);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(timer);
  }, [query]);
  return useQuery({
    queryKey: ["knowledge", "passages", debounced],
    enabled: debounced.trim() !== "",
    queryFn: async () => {
      const limit = 5; // the server's own default, pinned here by the request type
      const { data, response } = await client.POST("/api/knowledge/search", {
        body: { query: debounced, limit },
      });
      if (!response.ok) throw new Error(`search unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/** Enqueue extraction for a chapter: 202 and the job id to poll. The write
 *  invalidates the job key so every cached job row is asked for again —
 *  a new job makes the old answers history. */
export function useEnqueueExtraction(
  novelId: string,
): UseMutationResult<{ job_id: string }, Error, { chapterId: string }> {
  return useMutation({
    mutationFn: async (input: { chapterId: string }) => {
      const { data, response } = await client.POST("/api/knowledge/extraction/{novel_id}", {
        params: { path: { novel_id: novelId } },
        body: { chapter_id: input.chapterId },
      });
      if (!response.ok || !data) throw new Error(`extraction refused: ${response.status}`);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

/**
 * The two review decisions. Both invalidate the entity list and the pending
 * queue on settling — not only on success: a 409 means another reviewer (or
 * an earlier click of the same one) consumed the suggestion first, and the
 * refetch is what removes the card a second decision would have acted on.
 */
export function useAcceptSuggestion(
  novelId: string,
): UseMutationResult<Entity, Error, string> {
  return useMutation({
    mutationFn: async (suggestionId: string) => {
      const { data, response } = await client.POST(
        "/api/knowledge/suggestions/{suggestion_id}/accept",
        { params: { path: { suggestion_id: suggestionId } } },
      );
      if (!response.ok || !data) throw new Error(`accept refused: ${response.status}`);
      return data;
    },
    onSettled: () => {
      void invalidateKnowledge(novelId);
    },
  });
}

export function useDiscardSuggestion(
  novelId: string,
): UseMutationResult<Suggestion, Error, string> {
  return useMutation({
    mutationFn: async (suggestionId: string) => {
      const { data, response } = await client.POST(
        "/api/knowledge/suggestions/{suggestion_id}/discard",
        { params: { path: { suggestion_id: suggestionId } } },
      );
      if (!response.ok || !data) throw new Error(`discard refused: ${response.status}`);
      return data;
    },
    onSettled: () => {
      void invalidateKnowledge(novelId);
    },
  });
}

/** The two knowledge views of a novel go stale together: a review decision
 *  moves the queue and (on accept) the list in one request. */
function invalidateKnowledge(novelId: string): void {
  void queryClient.invalidateQueries({ queryKey: ["knowledge", "entities", novelId] });
  void queryClient.invalidateQueries({ queryKey: ["knowledge", "suggestions", novelId] });
}
