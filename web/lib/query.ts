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
  type Accept,
  type Chapter,
  type Entity,
  type Finding,
  type Hit,
  type Job,
  type Novel,
  type NovelCreate,
  type Relation,
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
 * One novel's row, cached under `["novels", novelId]` beside the shelf's
 * list: the workbench's heading reads the row, and the write paths
 * invalidate the `["novels"]` prefix — one invalidation keeps the row and
 * the list honest together. An answer that is not ok throws, so the cache
 * holds either the row or the failure — a 404 is never an empty book.
 */
export function useNovelQuery(novelId: string): UseQueryResult<Novel> {
  return useQuery({
    queryKey: ["novels", novelId],
    queryFn: async () => {
      const { data, response } = await client.GET("/api/writing/novels/{novel_id}", {
        params: { path: { novel_id: novelId } },
      });
      if (!response.ok || !data) throw new Error(`novel unavailable: ${response.status}`);
      return data;
    },
  });
}

/**
 * A novel's chapters in position order, cached under `["chapters", novelId]`.
 * The workbench's rail and editor read the list here, and the write paths (a
 * settled save, a created chapter) invalidate the key instead of patching the
 * cached array by hand — every view of the key refetches from the rows that
 * changed. An answer that is not ok throws, so the cache holds either the
 * list or the failure — never a half-current list.
 */
export function useChaptersQuery(novelId: string): UseQueryResult<Chapter[]> {
  return useQuery({
    queryKey: ["chapters", novelId],
    queryFn: async () => {
      const { data, response } = await client.GET("/api/writing/novels/{novel_id}/chapters", {
        params: { path: { novel_id: novelId } },
      });
      if (!response.ok) throw new Error(`chapters unavailable: ${response.status}`);
      return data ?? [];
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
 * A value that pauses before it becomes the ask: the words settle for
 * `delay` milliseconds, and only then does the hook hand them on — a word
 * typed a letter at a time is one consumer request, not one per keystroke.
 */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/**
 * The server-side filters of the entity list: an absent field is no
 * parameter, an empty search box means no `q`.
 */
export type EntityFilters = { type?: string; tag?: string; q?: string };

/**
 * The entity list's placeholder patience: the previous answer stays on
 * screen only while the ask is still the same novel's. A narrowed filter
 * must not blank the list it narrows, but a switch to another novel must
 * not carry the previous novel's rows across — they are selectable rows
 * with merge, edit and delete offered on them, so showing them for a
 * story they do not belong to is a lie the next click would carry out.
 * The key's third slot is the novel id
 * (`["knowledge", "entities", novelId, filters]`).
 */
export function sameNovelPlaceholder(novelId: string) {
  return <T>(
    previous: T | undefined,
    previousQuery: { queryKey: readonly unknown[] } | undefined,
  ): T | undefined => (previousQuery?.queryKey[2] === novelId ? previous : undefined);
}

/**
 * The novel's entities under the knowledge capability's key, narrowed by
 * the server's `type`/`tag`/`q` filters (the `q` tier is the trigram
 * search — a misspelt name still finds its row). The key carries the
 * filters, so every view of the list is cached under the question that
 * produced it; a caller keeping the unfiltered list beside a narrowed one
 * shares the cache when no filter is set, because the empty filters and
 * no filters are the same question. While a narrowed ask is in flight the
 * previous answer stays on screen — but only the same novel's (see
 * `sameNovelPlaceholder`). An answer that is not ok throws, so the cache
 * holds either the list or the failure — never a half-current list.
 */
export function useEntitiesQuery(
  novelId: string,
  filters: EntityFilters = {},
): UseQueryResult<Entity[]> {
  return useQuery({
    queryKey: ["knowledge", "entities", novelId, filters],
    placeholderData: sameNovelPlaceholder(novelId),
    queryFn: async () => {
      const { data, response } = await client.GET(
        "/api/knowledge/novels/{novel_id}/entities",
        {
          params: {
            path: { novel_id: novelId },
            query: {
              type: filters.type || undefined,
              tag: filters.tag || undefined,
              q: filters.q || undefined,
            },
          },
        },
      );
      if (!response.ok) throw new Error(`entities unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/**
 * One entity's relations, both directions, oldest first — the card's and
 * the edit dialog's shared view of the edges. The key carries the entity,
 * so the two surfaces read one cache and a change invalidates both.
 */
export function useEntityRelationsQuery(entityId: string): UseQueryResult<Relation[]> {
  return useQuery({
    queryKey: ["knowledge", "relations", entityId],
    queryFn: async () => {
      const { data, response } = await client.GET(
        "/api/knowledge/entities/{entity_id}/relations",
        { params: { path: { entity_id: entityId } } },
      );
      if (!response.ok) throw new Error(`relations unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/** The input of a relation add: the edge's end, its type, an optional note.
 *  A `null` note is the no-note state — an empty or whitespace note is
 *  dropped before the create (the field is sent absent), never stored as a
 *  note called "". */
export type RelationInput = {
  entityId: string;
  toEntityId: string;
  relationType: string;
  note?: string | null;
};

/** The fields a relation edit may carry: the ends are immutable. */
export type RelationChanges = { relationType?: string; note?: string | null };

/**
 * The three edge changes. Each invalidates the whole relations prefix on
 * settling — not only on success: a 404 means the edge is already gone
 * (another correction won the race), and the refetch is what makes the
 * rows follow a list that no longer holds it. The prefix, not the
 * mutating end's key, because an edge always has two ends: the other
 * end's card reads the same cache and must not wear the old graph until
 * its answer's freshness runs out.
 */
export function useAddRelation(): UseMutationResult<Relation, Error, RelationInput> {
  return useMutation({
    mutationFn: async (input: RelationInput) => {
      const { data, response } = await client.POST(
        "/api/knowledge/entities/{entity_id}/relations",
        {
          params: { path: { entity_id: input.entityId } },
          body: {
            to_entity_id: input.toEntityId,
            relation_type: input.relationType,
            note: input.note?.trim() ? input.note : undefined,
          },
        },
      );
      if (!response.ok || !data) throw new Error(`add relation refused: ${response.status}`);
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
    },
  });
}

export function useUpdateRelation(): UseMutationResult<
  Relation,
  Error,
  { relationId: string } & RelationChanges
> {
  return useMutation({
    mutationFn: async (input: { relationId: string } & RelationChanges) => {
      const { data, response } = await client.PATCH("/api/knowledge/relations/{relation_id}", {
        params: { path: { relation_id: input.relationId } },
        body: { relation_type: input.relationType, note: input.note },
      });
      if (!response.ok || !data) throw new Error(`relation update refused: ${response.status}`);
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
    },
  });
}

export function useDeleteRelation(): UseMutationResult<void, Error, { relationId: string }> {
  return useMutation({
    mutationFn: async (input: { relationId: string }) => {
      const { response } = await client.DELETE("/api/knowledge/relations/{relation_id}", {
        params: { path: { relation_id: input.relationId } },
      });
      if (!response.ok) throw new Error(`relation delete refused: ${response.status}`);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
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
 * search. The ask is debounced — the box's entity list narrows the same
 * words against the server (see `useEntitiesQuery`), and the corpus's
 * passages are owed only once the typing pauses, so a word typed a letter
 * at a time is one request, not one per keystroke. The key carries the
 * debounced text, so every answer is cached under the words that produced
 * it, and an empty query asks nothing (`enabled`).
 */
export function usePassageSearch(query: string): UseQueryResult<Hit[]> {
  const debounced = useDebouncedValue(query, 300);
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

/** The pending findings queue: the contradictions the check filed, waiting
 *  for a decision. */
export function useFindingsQuery(novelId: string): UseQueryResult<Finding[]> {
  return useQuery({
    queryKey: ["knowledge", "findings", novelId],
    queryFn: async () => {
      const { data, response } = await client.GET(
        "/api/knowledge/novels/{novel_id}/findings",
        { params: { path: { novel_id: novelId }, query: { status: "pending" } } },
      );
      if (!response.ok) throw new Error(`findings unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/** Enqueue the whole-novel consistency check: 202 and the job id to poll.
 *  The write invalidates the job key so every cached job row is asked for
 *  again — a new job makes the old answers history. */
export function useEnqueueCheck(
  novelId: string,
): UseMutationResult<{ job_id: string }, Error, void> {
  return useMutation({
    mutationFn: async () => {
      const { data, response } = await client.POST("/api/knowledge/consistency/{novel_id}", {
        params: { path: { novel_id: novelId } },
      });
      if (!response.ok || !data) throw new Error(`check refused: ${response.status}`);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

/**
 * The findings queue's two review decisions. Both invalidate the pending
 * queue on settling — not only on success: a 409 means another reviewer (or
 * an earlier click of the same one) consumed the finding first, and the
 * refetch is what removes the card a second decision would have acted on.
 */
export function useAcknowledgeFinding(
  novelId: string,
): UseMutationResult<Finding, Error, string> {
  return useMutation({
    mutationFn: async (findingId: string) => {
      const { data, response } = await client.POST(
        "/api/knowledge/findings/{finding_id}/acknowledge",
        { params: { path: { finding_id: findingId } } },
      );
      if (!response.ok || !data) throw new Error(`acknowledge refused: ${response.status}`);
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "findings", novelId] });
    },
  });
}

/** Dismiss a finding and invalidate the novel's pending queue on success or failure. */
export function useDismissFinding(
  novelId: string,
): UseMutationResult<Finding, Error, string> {
  return useMutation({
    mutationFn: async (findingId: string) => {
      const { data, response } = await client.POST(
        "/api/knowledge/findings/{finding_id}/dismiss",
        { params: { path: { finding_id: findingId } } },
      );
      if (!response.ok || !data) throw new Error(`dismiss refused: ${response.status}`);
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "findings", novelId] });
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
): UseMutationResult<Accept, Error, string> {
  return useMutation({
    mutationFn: async (suggestionId: string) => {
      const { data, error, response } = await client.POST(
        "/api/knowledge/suggestions/{suggestion_id}/accept",
        { params: { path: { suggestion_id: suggestionId } } },
      );
      if (!response.ok || !data) {
        // The refusal's detail rides the throw: one failure here has a fix
        // the UI can name (the embedding model changed, the re-embed is
        // owed first), so the machine-readable code must survive the
        // mutation boundary. Every other refusal keeps its status-only Error.
        throw Object.assign(new Error(`accept refused: ${response.status}`), {
          detail: (error as { detail?: unknown } | null | undefined)?.detail,
        });
      }
      return data;
    },
    onSettled: () => {
      void invalidateKnowledge(novelId);
    },
  });
}

/** Discard a suggestion and invalidate the novel's entities and queue on success or failure. */
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

/** The fields a correction may carry: only these reach the PATCH body. */
export type EntityChanges = Partial<Pick<Entity, "name" | "type" | "aliases" | "tags" | "content">>;

/**
 * The corrections of the detail view. Each invalidates the entity list
 * (every filtered view of it included — the invalidation is the key's
 * prefix) on settling — not only on success: a 404 means the row is
 * already gone (another correction won the race), and the refetch is what
 * makes the detail follow a list that no longer holds the row it shows.
 */
export function useUpdateEntity(
  novelId: string,
): UseMutationResult<Entity, Error, { entityId: string; changes: EntityChanges }> {
  return useMutation({
    mutationFn: async (input: { entityId: string; changes: EntityChanges }) => {
      const { data, response } = await client.PATCH("/api/knowledge/entities/{entity_id}", {
        params: { path: { entity_id: input.entityId } },
        body: input.changes,
      });
      if (!response.ok || !data) throw new Error(`update refused: ${response.status}`);
      return data;
    },
    onSettled: () => {
      void invalidateEntities(novelId);
    },
  });
}

/** Delete an entity and invalidate the novel's entity list on success or failure. */
export function useDeleteEntity(novelId: string): UseMutationResult<void, Error, string> {
  return useMutation({
    mutationFn: async (entityId: string) => {
      const { response } = await client.DELETE("/api/knowledge/entities/{entity_id}", {
        params: { path: { entity_id: entityId } },
      });
      if (!response.ok) throw new Error(`delete refused: ${response.status}`);
    },
    onSettled: () => {
      void invalidateEntities(novelId);
      // The deleted row's edges cascade: every card that showed one of
      // them must ask again, whoever's end it stood on.
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
    },
  });
}

/** Merge the source into the returned target and invalidate entities on success or failure. */
export function useMergeEntities(
  novelId: string,
): UseMutationResult<Entity, Error, { sourceId: string; targetId: string }> {
  return useMutation({
    mutationFn: async (input: { sourceId: string; targetId: string }) => {
      const { data, response } = await client.POST(
        "/api/knowledge/entities/{entity_id}/merge",
        { params: { path: { entity_id: input.sourceId } }, body: { target_id: input.targetId } },
      );
      if (!response.ok || !data) throw new Error(`merge refused: ${response.status}`);
      return data;
    },
    onSettled: () => {
      void invalidateEntities(novelId);
      // The merge re-points the source's edges to the target: cards on
      // either end of a moved edge must ask again.
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
    },
  });
}

/** The entity list is the detail view's data too: the selected row is read
 *  out of it, so one invalidation refreshes both. */
function invalidateEntities(novelId: string): void {
  void queryClient.invalidateQueries({ queryKey: ["knowledge", "entities", novelId] });
}

/** The three knowledge views of a novel go stale together: a review
 *  decision moves the queue and (on accept) the list and — the placed
 *  relations — the edges, in one request. */
function invalidateKnowledge(novelId: string): void {
  void queryClient.invalidateQueries({ queryKey: ["knowledge", "entities", novelId] });
  void queryClient.invalidateQueries({ queryKey: ["knowledge", "suggestions", novelId] });
  void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
}
