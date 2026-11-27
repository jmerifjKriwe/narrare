import {
  keepPreviousData,
  QueryClient,
  useMutation,
  useQueries,
  useQuery,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import {
  client,
  type Accept,
  type Activity,
  type AssistantSession,
  type AssistantSessionCreate,
  type AssistantSessionRead,
  type AssistantSessionSummary,
  type AssistantTurnCreate,
  type AssistantTurnReadback,
  type Chapter,
  type Entity,
  type EntityCreate,
  type Finding,
  type Hit,
  type Job,
  type KnowledgeDocument,
  type Novel,
  type NovelCreate,
  type Relation,
  type RemapRead,
  type SceneAggregate,
  type SceneUpsert,
  type Storyboard,
  type StoryboardChapter,
  type Suggestion,
  type TimelineEvent,
  type TimelineEventCreate,
  type TimelineEventUpdate,
} from "./api/client";
import { ApiError, TransportError, wireCode } from "./api/errors";
import { applyTheme, type Theme } from "./theme";

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
 * One request refusal, whichever call met it: the response's status, the
 * body's stable code and its detail, so a face can name the failure in the
 * reader's language instead of echoing the wire's English.
 */
export function refused(what: string, response: Response, error?: unknown): ApiError {
  return new ApiError(what, {
    status: response.status,
    code: wireCode(error),
    detail: (error as { detail?: unknown } | null | undefined)?.detail,
  });
}

/**
 * The stored settings row, as `{ locale, theme, author_name,
 * daily_goal_words, email }` — the same contract the boot effect in the
 * shell used to own: an answer carries the row's choices, an unreachable
 * service resolves to `null`s, and the browser's language and the system's
 * colour scheme decide from there. The outage is an answer, not an error
 * state, so no consumer needs a fallback branch of its own. The profile's
 * fields (W4 Tasks 10/19) ride the same read: the chrome's user block
 * names `author_name`, falling back to the row's `email` label, and the
 * book-settings atelier section edits the name and the daily goal — the
 * settings capability owns the user row.
 */
export function useSettingsQuery(): UseQueryResult<{
  locale: string | null;
  theme: string | null;
  author_name: string | null;
  daily_goal_words: number | null;
  email: string | null;
}> {
  return useQuery({
    queryKey: ["settings"],
    // No refetch on window focus: a focus refetch while the service is down
    // would erase the values adopted at boot. The row changes only through
    // the switchers, which invalidate this key themselves.
    refetchOnWindowFocus: false,
    queryFn: async () => {
      try {
        const { data } = await client.GET("/api/settings");
        return {
          locale: data?.locale ?? null,
          theme: data?.theme ?? null,
          author_name: data?.author_name ?? null,
          daily_goal_words: data?.daily_goal_words ?? null,
          email: data?.email ?? null,
        };
      } catch {
        return { locale: null, theme: null, author_name: null, daily_goal_words: null, email: null };
      }
    },
  });
}

/**
 * The settings surface's own read (W7 Task 3): the strict one. The chrome's
 * `useSettingsQuery` above answers an outage with nulls so the boot gate can
 * open — the right contract for the shell, and the wrong one for a settings
 * page, whose whole job is showing the row's truth: dressed-up nulls would
 * render the outage as an empty profile. This hook demands the answer — a
 * refusal or a dead service is an error, and the page answers with the
 * outage face and its retry. The key sits under the `["settings"]` prefix,
 * so every write's invalidation (the language contract's, the theme door's,
 * `useUpdateSettings`'s) refetches both reads together. `refetchOnWindowFocus`
 * rides the chrome read's reason: a focus refetch while the service is down
 * would erase the answers the form holds.
 */
export function useSettings(): UseQueryResult<{
  locale: string | null;
  theme: string | null;
  author_name: string | null;
  daily_goal_words: number | null;
  update_check_interval_days: number | null;
  email: string | null;
}> {
  return useQuery({
    queryKey: ["settings", "read"],
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data, error, response } = await client.GET("/api/settings");
      if (!response.ok || !data) throw refused("settings unavailable", response, error);
      return {
        locale: data.locale ?? null,
        theme: data.theme ?? null,
        author_name: data.author_name ?? null,
        daily_goal_words: data.daily_goal_words ?? null,
        update_check_interval_days: data.update_check_interval_days ?? null,
        email: data.email ?? null,
      };
    },
  });
}

/** The fields a profile save may carry: only these reach the PATCH body,
 *  beside the locale every settings write carries (the schema's own rule).
 *  `null` is the cleared state for the name and the goal — back to the email
 *  label and no goal; the update check's interval rides its wire name and a
 *  carried `null` resets it to the product default. An absent field keeps the
 *  stored answer. */
export type SettingsChanges = {
  authorName?: string | null;
  dailyGoalWords?: number | null;
  update_check_interval_days?: number | null;
};

/**
 * The preference row's write (the writing capability's GoalSetter and book
 * settings ride this same endpoint through their own hook — the settings
 * surface's home is here, beside the row's reads): the locale is ALWAYS
 * carried, present and nullable, so the caller hands the stored one through
 * unchanged; the profile fields ride only when carried. The write
 * invalidates the whole `["settings"]` prefix — the chrome's row and the
 * surface's strict read move together — and the activity aggregate, whose
 * daily goal the row carries. A refusal carries its status and the 422's
 * detail, so the form can name a field refusal as the field refusal it is.
 */
export function useUpdateSettings(): UseMutationResult<
  void,
  Error,
  { locale: string | null } & SettingsChanges
> {
  return useMutation({
    mutationFn: async ({ locale, authorName, dailyGoalWords, update_check_interval_days }) => {
      const body: {
        locale: string | null;
        author_name?: string | null;
        daily_goal_words?: number | null;
        update_check_interval_days?: number | null;
      } = { locale };
      if (authorName !== undefined) body.author_name = authorName;
      if (dailyGoalWords !== undefined) body.daily_goal_words = dailyGoalWords;
      if (update_check_interval_days !== undefined) {
        body.update_check_interval_days = update_check_interval_days;
      }
      const { error, response } = await client.PATCH("/api/settings", { body });
      if (!response.ok) {
        throw refused("settings update refused", response, error);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

/**
 * The one theme write (W7 Task 3) — the rail's tri-state toggle and the
 * settings page's three appearance cards share this seam, so there is no
 * second mechanism: the choice paints at once (`applyTheme`, the mirror
 * its cache), PATCHes the theme's own door, and a refusal restores the prior
 * appearance — the exact discipline the rail's inline toggle rode before
 * the page needed the write too. The theme rides the chrome's tolerant read:
 * on an outage the chrome keeps its appearance and the toggle still answers.
 */
export function useTheme(): {
  theme: string | null;
  setTheme: (next: Theme | null) => Promise<void>;
} {
  const settings = useSettingsQuery();
  const theme = settings.data?.theme ?? null;
  const setTheme = useCallback(async (next: Theme | null) => {
    const previous = theme;
    applyTheme(next);
    try {
      const { error, response } = await client.PATCH("/api/settings/theme", {
        body: { theme: next },
      });
      if (!response.ok) throw refused("refused", response, error);
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      applyTheme(previous === "light" || previous === "dark" ? previous : null);
    }
  }, [theme]);
  return { theme, setTheme };
}

/**
 * The chrome's active book (W4 Task 10): the latest-edited unarchived novel
 * — the shelf hero's own rule, read here because the shell owns the chrome
 * and a capability's module never crosses into it (rule 1). The two homes
 * state the same rule: parsed instants, strict comparison, ties keep the
 * first row, archived books never lead. The workspace route (Task 11) will
 * resolve the active book from its own param; until it lands, the rail's
 * switcher and the topbar read this choice.
 */
export function activeNovelFallback(novels: readonly Novel[]): Novel | null {
  let active: Novel | null = null;
  for (const novel of novels) {
    if (novel.archived_at != null) continue;
    if (active === null || Date.parse(novel.updated_at) > Date.parse(active.updated_at)) {
      active = novel;
    }
  }
  return active;
}

/**
 * The library list, cached under the writing capability's `["novels"]`
 * prefix with the archive question in the key: the shelf's „Archiv
 * einbeziehen" toggle is a real refetch (`include_archived`), not a client
 * hide — the default ask keeps its bare shape (false is the server's own
 * default), the widened ask carries the parameter. The writes' prefix
 * invalidation reaches both answers. While the toggle's ask is in flight
 * the previous list stands (`keepPreviousData`) — widening or narrowing
 * the population never flashes the skeleton over the shelf it changes.
 * An answer that is not ok throws, so the cache holds either the list or
 * the failure — never a half-current list.
 */
export function useNovelsQuery(includeArchived = false): UseQueryResult<Novel[]> {
  return useQuery({
    queryKey: ["novels", { include_archived: includeArchived }],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error, response } = includeArchived
        ? await client.GET("/api/writing/novels", {
            params: { query: { include_archived: true } },
          })
        : await client.GET("/api/writing/novels");
      if (!response.ok) throw refused("novels unavailable", response, error);
      return data ?? [];
    },
  });
}

/**
 * The atelier's activity aggregate (Task 4), cached under `["activity"]`
 * with the window in the key — the novels list's own convention: the
 * default ask keeps its bare shape (days=30 is the server's default), a
 * narrower window carries the parameter. The shelf's banner and streak
 * chip read one cache through this hook; the write family below
 * invalidates the prefix, so a chapter write moves the banner without
 * waiting out the staleTime. An answer that is not ok throws, so the
 * cache holds either the window or the failure — never an invented zero.
 */
export function useActivityQuery(days = 30): UseQueryResult<Activity> {
  return useQuery({
    queryKey: ["activity", { days }],
    queryFn: async () => {
      const { data, error, response } =
        days === 30
          ? await client.GET("/api/writing/activity")
          : await client.GET("/api/writing/activity", { params: { query: { days } } });
      if (!response.ok || !data) throw refused("activity unavailable", response, error);
      return data;
    },
  });
}

/**
 * Creating a novel: the first mutation under the spec 5.10 convention. The
 * write invalidates the shelf family instead of patching the cached list by
 * hand, so every view of the keys refetches from the row that changed. The
 * list updates when that refetch lands; the caller's own state (the form)
 * does not wait for it.
 */
export function useCreateNovel(): UseMutationResult<Novel, Error, NovelCreate> {
  return useMutation({
    mutationFn: async (input: NovelCreate) => {
      const { data, error, response } = await client.POST("/api/writing/novels", { body: input });
      if (!response.ok || !data) throw refused("create refused", response, error);
      return data;
    },
    onSuccess: () => {
      void invalidateNovelShelf();
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
      const { data, error, response } = await client.GET("/api/writing/novels/{novel_id}", {
        params: { path: { novel_id: novelId } },
      });
      if (!response.ok || !data) {
        // The status rides the throw (the accept-suggestion precedent): a
        // 404 is the one failure the workbench answers with a navigation —
        // the book was deleted elsewhere — so the machine-readable fact
        // must survive the query boundary.
        throw refused("novel unavailable", response, error);
      }
      return data;
    },
  });
}

/**
 * The one-shot note that the workspace's book was deleted elsewhere: set
 * by the workbench's 404 degrade, taken by the shelf's next mount. Module
 * state beside the cache it belongs to — the note is the 404's UI
 * translation, owned by the same layer that owns the `["novels"]` keys,
 * and both pages already import this module (no chunk changes hands).
 */
let novelDeletedElsewhere = false;

/** Record that the book the workspace tried to open answered 404; the
 *  shelf's next mount shows the note once. */
export function noteNovelDeletedElsewhere(): void {
  novelDeletedElsewhere = true;
}

/** Take the note if one stands: the shelf's mount reads it once, and the
 *  note cannot outlive the shelf that shows it. */
export function takeNovelDeletedElsewhere(): boolean {
  const was = novelDeletedElsewhere;
  novelDeletedElsewhere = false;
  return was;
}

/** The fields a details edit may carry: only these reach the PATCH body.
 *  `null` is the cleared state for the four optional fields; the title is
 *  never clearable and never `null` when sent. */
export type NovelChanges = Partial<
  Pick<Novel, "title" | "genre" | "blurb" | "author" | "language">
>;

/**
 * Correcting a novel's five metadata fields (§2): only the fields the body
 * carries are the change, so the caller sends only what the user dirtied —
 * the client's mirror of the server's `model_fields_set` contract. The
 * row's `onupdate` advances `updated_at` (D8: the archive's metadata
 * changed), so the shelf family is invalidated — the shelf's list, the
 * row this dialog's own read uses and the activity aggregate refresh
 * together. A refusal
 * carries status and detail: a 422 names the field, and the dialog shows
 * that name on the field it refused.
 */
export function useUpdateNovel(): UseMutationResult<
  Novel,
  Error,
  { novelId: string; changes: NovelChanges }
> {
  return useMutation({
    mutationFn: async (input: { novelId: string; changes: NovelChanges }) => {
      const { data, error, response } = await client.PATCH(
        "/api/writing/novels/{novel_id}",
        { params: { path: { novel_id: input.novelId } }, body: input.changes },
      );
      if (!response.ok || !data) {
        throw refused("novel update refused", response, error);
      }
      return data;
    },
    onSuccess: () => {
      void invalidateNovelShelf();
    },
  });
}

/**
 * Deleting a novel: the row and everything novel-scoped cascade in the
 * database — chapters, entities, relations, suggestions, findings, the
 * activity rows — and the documents are the library's and stay. Success
 * invalidates the shelf family (the row and the list both held a book
 * that no longer exists, and its days left the aggregate with it); a
 * failed delete asks for nothing.
 */
export function useDeleteNovel(): UseMutationResult<void, Error, string> {
  return useMutation({
    mutationFn: async (novelId: string) => {
      const { error, response } = await client.DELETE("/api/writing/novels/{novel_id}", {
        params: { path: { novel_id: novelId } },
      });
      if (!response.ok) throw refused("novel delete refused", response, error);
    },
    onSuccess: () => {
      void invalidateNovelShelf();
    },
  });
}

/**
 * Duplicating a novel (Task 3): a new book with the same metadata and a full
 * copy of its chapters, named „<title> (Kopie)", starting on the shelf —
 * unarchived, never exported. The 201 row comes back whole; success
 * invalidates the shelf family so the copy joins the shelf's list and
 * every figure is the server's own count, never a client guess. A refusal
 * (404 absent, 409 setup required) throws with its status.
 */
export function useDuplicateNovel(): UseMutationResult<Novel, Error, string> {
  return useMutation({
    mutationFn: async (novelId: string) => {
      const { data, error, response } = await client.POST(
        "/api/writing/novels/{novel_id}/duplicate",
        { params: { path: { novel_id: novelId } } },
      );
      if (!response.ok || !data) throw refused("duplicate refused", response, error);
      return data;
    },
    onSuccess: () => {
      void invalidateNovelShelf();
    },
  });
}

/** The ZIP answer: the bytes for the browser's download seam, and the name
 *  the Content-Disposition proposed — or a neutral fallback. */
export type ZipDownload = { blob: Blob; filename: string };

/** The name inside `attachment; filename="…"`, when the header carries one. */
function filenameFromDisposition(header: string | null): string | null {
  if (header === null) return null;
  return /filename="([^"]+)"/.exec(header)?.[1] ?? null;
}

/**
 * Exporting a novel as a ZIP download (the quick menu's Exportieren). The
 * endpoint answers two bodies under one URL — a JSON receipt for a path
 * export, ZIP bytes for a ZIP export — so the call reads the answer as a
 * blob (`parseAs`), never as the JSON receipt it is not; the typed client
 * stays the one door. The filename rides the Content-Disposition the server
 * names after the title's slug. Success invalidates the shelf family: every
 * export advances the row's `last_exported_at`, and the menu's meta line
 * reads it through that refetch. A refusal throws with its status (the ZIP
 * mode's failures are the absent book and the service's own refusals).
 */
export function useExportNovel(): UseMutationResult<ZipDownload, Error, string> {
  return useMutation({
    mutationFn: async (novelId: string) => {
      const { data, error, response } = await client.POST("/api/writing/novels/{novel_id}/export", {
        params: { path: { novel_id: novelId } },
        body: { mode: "zip" },
        parseAs: "blob",
      });
      if (!response.ok || !data) throw refused("export refused", response, error);
      // `parseAs: "blob"` reads the ZIP bytes at runtime; openapi-fetch's
      // init intersection widens the literal, so the inferred result still
      // names the JSON receipt the ZIP answer is not — one cast at the
      // boundary, the import upload's own precedent.
      return {
        blob: data as unknown as Blob,
        filename: filenameFromDisposition(response.headers.get("content-disposition")) ?? "export.zip",
      };
    },
    onSuccess: () => {
      void invalidateNovelShelf();
    },
  });
}

/**
 * Archiving or restoring a novel (Task 2's `archived_at` PATCH): carrying a
 * timestamp archives the book, carrying `null` restores it — the symmetric
 * reversibility the draft pins. The archive moment is the client's now; the
 * row's `onupdate` advances `updated_at` (D8), so success invalidates the
 * shelf family — the default list drops the archived book, the
 * archive-included list keeps it with its pill, and the hero re-picks. A
 * refusal throws with its status.
 */
export function useArchiveNovel(): UseMutationResult<
  Novel,
  Error,
  { novelId: string; archived: boolean }
> {
  return useMutation({
    mutationFn: async (input: { novelId: string; archived: boolean }) => {
      const { data, error, response } = await client.PATCH("/api/writing/novels/{novel_id}", {
        params: { path: { novel_id: input.novelId } },
        body: { archived_at: input.archived ? new Date().toISOString() : null },
      });
      if (!response.ok || !data) throw refused("archive refused", response, error);
      return data;
    },
    onSuccess: () => {
      void invalidateNovelShelf();
    },
  });
}

/**
 * A novel's chapters in position order, cached under `["chapters", novelId]`.
 * The workbench's rail and editor read the list here, and the write paths
 * refresh the key: a created chapter invalidates it outright; a settled save
 * patches the saved body into the cached array first, then asks the key to
 * refetch — the patch holds the page's ground while the ask is outstanding,
 * and every view of the key still refetches from the rows that changed. An
 * answer that is not ok throws, so the cache holds either the list or the
 * failure — never a half-current list.
 */
export function useChaptersQuery(novelId: string): UseQueryResult<Chapter[]> {
  return useQuery({
    queryKey: ["chapters", novelId],
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/writing/novels/{novel_id}/chapters",
        { params: { path: { novel_id: novelId } } },
      );
      if (!response.ok) throw refused("chapters unavailable", response, error);
      return data ?? [];
    },
  });
}

/**
 * The chapter last written in, by the server's `updated_at` — the
 * workbench's param-less choice and the dock panels' fallback, read from
 * one cached list so both surfaces answer the same question. Compared as
 * parsed instants, because two ISO strings with different timezone offsets
 * do not order as their moments do. Strict comparison: on equal instants
 * the first row keeps the lead, and the list is in position order, so the
 * choice stays deterministic even when two chapters tie.
 */
export function activeChapterFallback(chapters: Chapter[]): string | null {
  return (
    chapters.reduce<Chapter | null>(
      (best, chapter) =>
        best === null || Date.parse(chapter.updated_at) > Date.parse(best.updated_at)
          ? chapter
          : best,
      null,
    )?.id ?? null
  );
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
      if (jobId === null) throw new ApiError("no job to poll");
      const { data, error, response } = await client.GET("/api/jobs/{job_id}", {
        params: { path: { job_id: jobId } },
      });
      if (!response.ok || !data) {
        // The status rides the throw (the novel read's precedent): a
        // 404 is the one poll failure a lane answers by clearing itself
        // — the job row was destroyed elsewhere — so the
        // machine-readable fact must survive the query boundary. A
        // network failure throws before this line and carries no
        // status, which is its own honest answer.
        throw refused("job unavailable", response, error);
      }
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
      const { data, error, response } = await client.GET(
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
      if (!response.ok) throw refused("entities unavailable", response, error);
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
      const { data, error, response } = await client.GET(
        "/api/knowledge/entities/{entity_id}/relations",
        { params: { path: { entity_id: entityId } } },
      );
      if (!response.ok) throw refused("relations unavailable", response, error);
      return data ?? [];
    },
  });
}

/**
 * The novel's whole edge set, both directions, oldest first — the graph
 * canvas's read of the relations. The key carries the novel beside the
 * per-entity `["knowledge", "relations", entityId]` keys, so the edge
 * mutations' `["knowledge", "relations"]` prefix invalidation keeps this
 * cache honest too — an edge always has two ends, and the canvas holds
 * them all. No existing hook fits: the per-entity read would ask once
 * per node (N+1) where this endpoint answers once.
 */
export function useNovelRelationsQuery(novelId: string): UseQueryResult<Relation[]> {
  return useQuery({
    queryKey: ["knowledge", "relations", "novel", novelId],
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/knowledge/novels/{novel_id}/relations",
        { params: { path: { novel_id: novelId } } },
      );
      if (!response.ok) throw refused("novel relations unavailable", response, error);
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
      const { data, error, response } = await client.POST(
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
      if (!response.ok || !data) {
        // The refusal's status rides the throw (the accept path's carry):
        // a 409 is a duplicate the dialog names in its own words, not an
        // outage, so the machine-readable status must survive the mutation
        // boundary.
        throw refused("add relation refused", response, error);
      }
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
      void invalidateNovelShelf();
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
      const { data, error, response } = await client.PATCH(
        "/api/knowledge/relations/{relation_id}",
        {
          params: { path: { relation_id: input.relationId } },
          body: { relation_type: input.relationType, note: input.note },
        },
      );
      if (!response.ok || !data) {
        // The add path's carry: the status rides the throw, so a 409 can
        // be named as the duplicate it is, not as an outage.
        throw refused("relation update refused", response, error);
      }
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
      void invalidateNovelShelf();
    },
  });
}

export function useDeleteRelation(): UseMutationResult<void, Error, { relationId: string }> {
  return useMutation({
    mutationFn: async (input: { relationId: string }) => {
      const { error, response } = await client.DELETE("/api/knowledge/relations/{relation_id}", {
        params: { path: { relation_id: input.relationId } },
      });
      if (!response.ok) throw refused("relation delete refused", response, error);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
      void invalidateNovelShelf();
    },
  });
}

/** The pending review queue: the suggestions waiting for a decision. */
export function usePendingSuggestionsQuery(novelId: string): UseQueryResult<Suggestion[]> {
  return useQuery({
    queryKey: ["knowledge", "suggestions", novelId],
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/knowledge/novels/{novel_id}/suggestions",
        { params: { path: { novel_id: novelId }, query: { status: "pending" } } },
      );
      if (!response.ok) throw refused("suggestions unavailable", response, error);
      return data ?? [];
    },
  });
}

/**
 * The corpus's semantic search, one ask both doors share — today only the
 * sources archive's submitted box is wired (the dock's live box is still
 * undrawn); when it lands it will POST the same endpoint the same way, so
 * the ask already lives in one place. A refusal throws the ENRICHED shape —
 * status and detail ride the throw — because the doors share one cache
 * family (`["knowledge", "passages", …]`): an error one surface cached
 * replays on the other, and the 409 embedding-mismatch must name itself
 * there too, not wear the generic outage face.
 */
async function searchCorpus(query: string): Promise<Hit[]> {
  const limit = 5; // the server's own default, pinned here by the request type
  const { data, error, response } = await client.POST("/api/knowledge/search", {
    body: { query, limit },
  });
  if (!response.ok) {
    throw refused("search unavailable", response, error);
  }
  return data ?? [];
}

/**
 * The dock search's second tier: the box's text asked of the semantic
 * search. The ask is debounced — the box's entity list narrows the same
 * words against the server (see `useEntitiesQuery`), and the corpus's
 * passages are owed only once the typing pauses, so a word typed a letter
 * at a time is one request, not one per keystroke. The key carries the
 * debounced text, so every answer is cached under the words that produced
 * it, and an empty query asks nothing (`enabled`). The refusal is the
 * shared enriched shape (`searchCorpus` above).
 */
export function usePassageSearch(query: string): UseQueryResult<Hit[]> {
  const debounced = useDebouncedValue(query, 300);
  return useQuery({
    queryKey: ["knowledge", "passages", debounced],
    enabled: debounced.trim() !== "",
    queryFn: () => searchCorpus(debounced),
  });
}

/**
 * The sources archive's explicit search (W5 Task 6): the box's text asked
 * of the semantic search when the writer SUBMITS — the draft's button is
 * the pause, so no debounce sits between the click and the ask (the dock's
 * `usePassageSearch` debounces its live box instead). The key is the same
 * `["knowledge", "passages", text]` family: the same question is the same
 * cache entry, whichever surface asked it. An empty query asks nothing
 * (`enabled`). The refusal carries its status and detail — the 409
 * embedding-mismatch is a named condition with a fix, not an outage.
 */
export function useSourceSearch(query: string): UseQueryResult<Hit[]> {
  return useQuery({
    queryKey: ["knowledge", "passages", query],
    enabled: query.trim() !== "",
    queryFn: () => searchCorpus(query),
  });
}

/**
 * An explicit submit is an explicit re-ask: the sources archive's submit
 * retires the submitted words' cached answer before it stands submitted
 * again, so the POST goes out even within the `staleTime` that would
 * otherwise replay the first answer (the same string is the same key, so
 * nothing else fires). A changed string is a fresh key that fetches on
 * its own; invalidating an entry that never stood is a no-op. The dock's
 * debounced `usePassageSearch` is untouched — its asks are implicit, so
 * the cache serves them exactly as designed.
 */
export function invalidateSourceSearch(query: string): void {
  void queryClient.invalidateQueries({ queryKey: ["knowledge", "passages", query] });
}

/**
 * The library's documents (W5 Task 6), cached under `["knowledge",
 * "documents"]` — the key the delete mutation below invalidates, so the
 * sources archive's list refetches the server's truth after a delete.
 * Documents are the library's, never canon (D8): no novel id rides the
 * key, and no novel key goes stale on their account. An answer that is
 * not ok throws, so the cache holds either the list or the failure —
 * never a half-current archive.
 */
export function useDocumentsQuery(): UseQueryResult<KnowledgeDocument[]> {
  return useQuery({
    queryKey: ["knowledge", "documents"],
    queryFn: async () => {
      const { data, error, response } = await client.GET("/api/knowledge/documents");
      if (!response.ok) throw refused("documents unavailable", response, error);
      return data ?? [];
    },
  });
}

/**
 * Uploading a document (W5 Task 6): the real multipart endpoint, the file
 * in the API's own `file` field. The schema types the multipart body's
 * file as a string; the wire carries FormData — one cast at the boundary
 * (the export blob's precedent). openapi-fetch passes FormData through
 * untouched and lets the browser set the multipart boundary. The title is
 * the file's own name (the server resolves it when no form title rides
 * along). The write invalidates the documents list on SETTLING — not only
 * on success, the delete family's discipline: a refusal may mean the
 * server changed underneath (another tab's write won the race), and the
 * refetch is what makes the list follow the rows that stand. The passages
 * family is invalidated on the same settle — the upload changes the corpus
 * every cached search answer was drawn from. A refusal carries its status
 * and detail — 413 the size bound, 422 the empty document, 409 the
 * embedding mismatch — so the page names each refusal in its own words.
 */
export function useUploadDocument(): UseMutationResult<KnowledgeDocument, Error, File> {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const { data, error, response } = await client.POST("/api/knowledge/documents", {
        body: form as unknown as { file: string },
      });
      if (!response.ok || !data) {
        throw refused("upload refused", response, error);
      }
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "documents"] });
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "passages"] });
    },
  });
}

/**
 * Deleting a document: its chunks' foreign key cascades, so the passages
 * leave the corpus with the row. The write invalidates the documents list
 * key on SETTLING — not only on success: a 404 means the document is
 * already gone (another tab's delete won the race), and the refetch is
 * what removes the row a second delete would have acted on. The passages
 * family rides the same settle — a just-deleted document's chunks must
 * not survive in a same-string resubmitted search. The sources archive's
 * `useDocumentsQuery` reads that same key, so the invalidation IS the
 * list's refetch. Documents are the library's, never canon (D8), so no
 * novel key may go stale on their account.
 */
export function useDeleteDocument(): UseMutationResult<void, Error, string> {
  return useMutation({
    mutationFn: async (documentId: string) => {
      const { error, response } = await client.DELETE(
        "/api/knowledge/documents/{document_id}",
        { params: { path: { document_id: documentId } } },
      );
      if (!response.ok) throw refused("document delete refused", response, error);
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "documents"] });
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "passages"] });
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
      const { data, error, response } = await client.POST(
        "/api/knowledge/extraction/{novel_id}",
        {
          params: { path: { novel_id: novelId } },
          body: { chapter_id: input.chapterId },
        },
      );
      if (!response.ok || !data) throw refused("extraction refused", response, error);
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
      const { data, error, response } = await client.GET(
        "/api/knowledge/novels/{novel_id}/findings",
        { params: { path: { novel_id: novelId }, query: { status: "pending" } } },
      );
      if (!response.ok) throw refused("findings unavailable", response, error);
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
      const { data, error, response } = await client.POST(
        "/api/knowledge/consistency/{novel_id}",
        { params: { path: { novel_id: novelId } } },
      );
      if (!response.ok || !data) throw refused("check refused", response, error);
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
      const { data, error, response } = await client.POST(
        "/api/knowledge/findings/{finding_id}/acknowledge",
        { params: { path: { finding_id: findingId } } },
      );
      if (!response.ok || !data) throw refused("acknowledge refused", response, error);
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
      const { data, error, response } = await client.POST(
        "/api/knowledge/findings/{finding_id}/dismiss",
        { params: { path: { finding_id: findingId } } },
      );
      if (!response.ok || !data) throw refused("dismiss refused", response, error);
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
        // mutation boundary.
        throw refused("accept refused", response, error);
      }
      return data;
    },
    onSettled: () => {
      void invalidateKnowledge(novelId);
      void invalidateNovelShelf();
    },
  });
}

/** Discard a suggestion and invalidate the novel's entities and queue on success or failure. */
export function useDiscardSuggestion(
  novelId: string,
): UseMutationResult<Suggestion, Error, string> {
  return useMutation({
    mutationFn: async (suggestionId: string) => {
      const { data, error, response } = await client.POST(
        "/api/knowledge/suggestions/{suggestion_id}/discard",
        { params: { path: { suggestion_id: suggestionId } } },
      );
      if (!response.ok || !data) throw refused("discard refused", response, error);
      return data;
    },
    onSettled: () => {
      void invalidateKnowledge(novelId);
    },
  });
}

/** The fields a correction may carry: only these reach the PATCH body.
 *  Content is present-and-nullable — a carried `null` clears the body, the
 *  EntityUpdate contract's own distinction (an absent field leaves it). */
export type EntityChanges = Partial<Pick<Entity, "name" | "type" | "aliases" | "tags">> & {
  content?: string | null;
};

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
      const { data, error, response } = await client.PATCH(
        "/api/knowledge/entities/{entity_id}",
        {
          params: { path: { entity_id: input.entityId } },
          body: input.changes,
        },
      );
      if (!response.ok || !data) throw refused("update refused", response, error);
      return data;
    },
    onSettled: () => {
      void invalidateEntities(novelId);
      void invalidateNovelShelf();
    },
  });
}

/** Delete an entity and invalidate the novel's entity list on success or failure. */
export function useDeleteEntity(novelId: string): UseMutationResult<void, Error, string> {
  return useMutation({
    mutationFn: async (entityId: string) => {
      const { error, response } = await client.DELETE("/api/knowledge/entities/{entity_id}", {
        params: { path: { entity_id: entityId } },
      });
      if (!response.ok) throw refused("delete refused", response, error);
    },
    onSettled: () => {
      void invalidateEntities(novelId);
      // The deleted row's edges cascade: every card that showed one of
      // them must ask again, whoever's end it stood on.
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
      void invalidateNovelShelf();
    },
  });
}

/** Merge the source into the returned target and invalidate entities on success or failure. */
export function useMergeEntities(
  novelId: string,
): UseMutationResult<Entity, Error, { sourceId: string; targetId: string }> {
  return useMutation({
    mutationFn: async (input: { sourceId: string; targetId: string }) => {
      const { data, error, response } = await client.POST(
        "/api/knowledge/entities/{entity_id}/merge",
        { params: { path: { entity_id: input.sourceId } }, body: { target_id: input.targetId } },
      );
      if (!response.ok || !data) throw refused("merge refused", response, error);
      return data;
    },
    onSettled: () => {
      void invalidateEntities(novelId);
      // The merge re-points the source's edges to the target: cards on
      // either end of a moved edge must ask again.
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
      void invalidateNovelShelf();
    },
  });
}

/** The create's failure, enriched for the dialog: the status picks the copy
 *  family, `code` and `detail` carry the backend's coded refusal, and `row`
 *  names the visible row the dialog marks; `field` rides along for a
 *  field-level marking the dialog does not do. A request that never reached
 *  the server keeps its own recognisable shape (`TransportError`). */
function createEntityFailure(cause: unknown): ApiError {
  const failure = cause as {
    response?: Response;
    error?: { detail?: { code?: string; detail?: string; row?: number; field?: string } };
  };
  const response = failure?.response;
  if (response === undefined) {
    // A transport failure carries no HTTP answer: the browser's own
    // «Failed to fetch» is English and names no cause a writer can act on,
    // so the dialog renders the catalog's sentence instead.
    return new TransportError("create refused", cause);
  }
  const detail = failure?.error?.detail;
  return new ApiError("create refused", {
    status: response.status,
    code: detail?.code,
    detail: detail?.detail,
    extra: { row: detail?.row, field: detail?.field },
  });
}

/**
 * Create an entity by hand, with its relation lines, in one transaction.
 * The settle invalidates the whole entity and relation families — the graph
 * and the dossiers refetch the server's truth, never an optimistic row — and
 * the shelf's canon rule follows, because a birth is a write to the book.
 */
export function useCreateEntity(): UseMutationResult<Entity, ApiError, EntityCreate> {
  return useMutation({
    mutationFn: async (body: EntityCreate) => {
      const result = await client.POST("/api/knowledge/entities", { body }).catch((cause: unknown) => {
        throw createEntityFailure(cause);
      });
      if (!result.response.ok || !result.data) throw createEntityFailure(result);
      return result.data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "entities"] });
      void queryClient.invalidateQueries({ queryKey: ["knowledge", "relations"] });
      void invalidateNovelShelf();
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

// --- The planning reads and writes (W6 Task 3) -----------------------------

/**
 * The novel's timeline events in the server's manual order — positioned
 * rows first, unordered (null position) last, creation order breaking
 * ties — cached under the planning capability's own key. The chronology
 * page is the reader; the write family below invalidates the key on
 * settling, so the page refetches the server's truth after every write.
 * An answer that is not ok throws, so the cache holds either the list or
 * the failure — never an invented empty timeline.
 */
export function useTimelineEvents(novelId: string): UseQueryResult<TimelineEvent[]> {
  return useQuery({
    queryKey: ["planning", "timeline", novelId],
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/planning/novels/{novel_id}/timeline-events",
        { params: { path: { novel_id: novelId } } },
      );
      if (!response.ok) throw refused("timeline events unavailable", response, error);
      return data ?? [];
    },
  });
}

/** The fields an event edit may carry: only these reach the PUT body, and
 *  only the ones the writer dirtied — the client's mirror of the server's
 *  `model_fields_set` contract. `chapter_id` and `position` are
 *  present-and-nullable: a carried `null` clears the link or the order,
 *  an absent field leaves the stored row alone. */
export type TimelineEventChanges = {
  title?: string;
  description?: string;
  date_label?: string;
  character_names?: string[];
  chapter_id?: string | null;
  position?: number | null;
};

/** Invalidate the novel's timeline list — the three writes' shared settle. */
function invalidateTimeline(novelId: string): void {
  void queryClient.invalidateQueries({ queryKey: ["planning", "timeline", novelId] });
}

/**
 * Creating an event: the POST body carries the whole row's writer fields,
 * no timestamps (those are the server's own). A refusal carries status
 * and detail — a 422 names the blank title or the chapter link the novel
 * does not hold, and the dialog shows those words on the field it owns.
 * Settling (not only success) invalidates the list key: a refused write
 * leaves the page holding the server's truth, whatever raced it.
 */
export function useCreateTimelineEvent(
  novelId: string,
): UseMutationResult<TimelineEvent, Error, TimelineEventCreate> {
  return useMutation({
    mutationFn: async (input: TimelineEventCreate) => {
      const { data, error, response } = await client.POST(
        "/api/planning/novels/{novel_id}/timeline-events",
        { params: { path: { novel_id: novelId } }, body: input },
      );
      if (!response.ok || !data) {
        throw refused("event create refused", response, error);
      }
      return data;
    },
    onSettled: () => {
      invalidateTimeline(novelId);
    },
  });
}

/**
 * Editing an event: only the carried fields are the change (the partial-
 * update contract — see `TimelineEventChanges`), so the caller sends only
 * what the writer dirtied. The body crosses the generated type's boundary
 * with one cast: openapi-typescript types the schema's defaulted fields
 * (description, date_label, character_names) as required, while the
 * server's `exclude_unset` honors their absence — the same one-cast rule
 * the export blob and the upload form carry. A refusal carries status
 * and detail (the blank title, the unknown chapter link).
 */
export function useUpdateTimelineEvent(
  novelId: string,
): UseMutationResult<TimelineEvent, Error, { eventId: string; changes: TimelineEventChanges }> {
  return useMutation({
    mutationFn: async (input: { eventId: string; changes: TimelineEventChanges }) => {
      const { data, error, response } = await client.PUT(
        "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
        {
          params: { path: { novel_id: novelId, event_id: input.eventId } },
          body: input.changes as TimelineEventUpdate,
        },
      );
      if (!response.ok || !data) {
        throw refused("event update refused", response, error);
      }
      return data;
    },
    onSettled: () => {
      invalidateTimeline(novelId);
    },
  });
}

/**
 * Deleting an event: the 204 route, nothing to return. Settling (not only
 * success) invalidates the list key — a 404 means the row is already gone
 * (another tab's delete won the race), and the refetch is what removes the
 * card a second delete would have acted on.
 */
export function useDeleteTimelineEvent(
  novelId: string,
): UseMutationResult<void, Error, string> {
  return useMutation({
    mutationFn: async (eventId: string) => {
      const { error, response } = await client.DELETE(
        "/api/planning/novels/{novel_id}/timeline-events/{event_id}",
        { params: { path: { novel_id: novelId, event_id: eventId } } },
      );
      if (!response.ok) throw refused("event delete refused", response, error);
    },
    onSettled: () => {
      invalidateTimeline(novelId);
    },
  });
}

/** The chapter-scene key the fan-out caches under and the save invalidates. */
function chapterScenesKey(chapterId: string): readonly unknown[] {
  return ["planning", "scenes", chapterId];
}

/**
 * Invalidate one chapter's scene aggregate — the seam the aggregate save
 * writes through (W6 Task 4's drill-in): a saved aggregate settles and
 * the chapter's own key goes stale, exactly the chapter the write touched
 * and none of its siblings. The timeline's counters and the causality
 * strip refetch through their own standing queries.
 */
export function invalidateChapterScenes(chapterId: string): void {
  void queryClient.invalidateQueries({ queryKey: chapterScenesKey(chapterId) });
}

/**
 * The novel's scenes, one chapter at a time (W6's fan-out ruling): there
 * is no bulk endpoint and none is built, so the hook reads each chapter's
 * aggregate through the query seam — parallel `useQueries`, each cached
 * under its own per-chapter key so the aggregate save's invalidation
 * reaches exactly the chapter it touched. A novel's chapter count
 * (dozens, local-first single user) makes this honest. The combined
 * answer is the whole fan or nothing: `data` stands only when every
 * chapter answered, `isError` when any one failed — the timeline's
 * status counters never sum a half-current novel. The combined shape is
 * the plan-pinned `UseQueryResult<SceneAggregate[]>` (one documented
 * boundary cast — `combine` returns the caller's own fields, not
 * TanStack's per-query object).
 */
export function useNovelScenes(
  chapters: readonly Chapter[],
): UseQueryResult<SceneAggregate[]> {
  return useQueries({
    queries: chapters.map((chapter) => ({
      queryKey: chapterScenesKey(chapter.id),
      queryFn: async () => {
        const { data, error, response } = await client.GET(
          "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
          {
            params: { path: { novel_id: chapter.novel_id, chapter_id: chapter.id } },
          },
        );
        if (!response.ok || !data) {
          throw refused("scenes unavailable", response, error);
        }
        return data;
      },
    })),
    combine: (results) =>
      ({
        data: results.every((result) => result.data !== undefined)
          ? results.map((result) => result.data)
          : undefined,
        error: results.find((result) => result.isError)?.error ?? null,
        isError: results.some((result) => result.isError),
        isPending: results.some((result) => result.isPending),
        isSuccess: results.every((result) => result.isSuccess),
        refetch: () => Promise.all(results.map((result) => result.refetch())),
      }) as unknown as UseQueryResult<SceneAggregate[]>,
  });
}

// --- The storyboard reads and writes (W6 Task 4) ----------------------------

/**
 * The novel's storyboard — the same read the writing capability's tension
 * card makes through its own hook, on the SAME key (`["planning",
 * "storyboard", novelId]`), so the two surfaces share one cache entry and
 * every write below refreshes both (rule 1: the coordination is the key,
 * never an import). An answer that is not ok throws, so the cache holds
 * either the board or the failure — never an invented empty storyboard.
 */
export function useStoryboard(novelId: string): UseQueryResult<Storyboard> {
  return useQuery({
    queryKey: ["planning", "storyboard", novelId],
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        "/api/planning/novels/{novel_id}/storyboard",
        { params: { path: { novel_id: novelId } } },
      );
      if (!response.ok || !data) throw refused("storyboard unavailable", response, error);
      return data;
    },
  });
}

/** Invalidate the novel's board — the storyboard writes' shared settle. */
function invalidateStoryboard(novelId: string): void {
  void queryClient.invalidateQueries({ queryKey: ["planning", "storyboard", novelId] });
}

/**
 * Moving one chapter to a stage of the current structure. The PUT answers
 * the assignment; a refusal carries status and detail — a 422 names the
 * unknown chapter or the stage key outside the structure, and the board's
 * refetch (the settle) is what returns the card to its true column.
 */
export function useSetChapterStage(
  novelId: string,
): UseMutationResult<StoryboardChapter, Error, { chapterId: string; stageKey: string }> {
  return useMutation({
    mutationFn: async (input: { chapterId: string; stageKey: string }) => {
      const { data, error, response } = await client.PUT(
        "/api/planning/novels/{novel_id}/chapters/{chapter_id}/stage",
        {
          params: { path: { novel_id: novelId, chapter_id: input.chapterId } },
          body: { stage_key: input.stageKey },
        },
      );
      if (!response.ok || !data) {
        throw refused("stage assignment refused", response, error);
      }
      return data;
    },
    onSettled: () => {
      invalidateStoryboard(novelId);
    },
  });
}

/**
 * The remap, both steps of the server's own contract: `confirm: false`
 * previews the mapping without writing a row, `confirm: true` writes the
 * assignments plus the novel setting in one transaction — exactly the
 * previewed mapping. A preview settles without invalidating anything
 * (nothing moved); a confirm invalidates the board. A refusal carries
 * status and detail — a 422 names the structure id the registry does not
 * know (`unknown structure: …`), the face Review Focus 2 pins.
 */
export function useRemapStoryboard(
  novelId: string,
): UseMutationResult<RemapRead, Error, { structureId: string; confirm: boolean }> {
  return useMutation({
    mutationFn: async (input: { structureId: string; confirm: boolean }) => {
      const { data, error, response } = await client.POST("/api/planning/novels/{novel_id}/remap", {
        params: { path: { novel_id: novelId } },
        body: { structure_id: input.structureId, confirm: input.confirm },
      });
      if (!response.ok || !data) {
        throw refused("remap refused", response, error);
      }
      return data;
    },
    onSuccess: (_data, input) => {
      if (input.confirm) invalidateStoryboard(novelId);
    },
  });
}

/**
 * The stale-aggregate answer the API's own semantics serve: the PUT has no
 * server-side version check — two concurrent saves resolve
 * last-writer-wins — so the check is the client's, at the save: the
 * chapter's stamp (`version_updated_at`, touched by every aggregate write)
 * is re-read first, and a stamp that moved since the editor's snapshot
 * throws THIS error carrying the server's fresh copy, before any PUT
 * crosses the wire. The face offers the fresh load or the honest
 * overwrite; `overwrite: true` on the retry is the writer naming
 * last-writer-wins with open eyes.
 */
export class SceneVersionConflict extends Error {
  constructor(readonly server: SceneAggregate) {
    super("the chapter's scenes changed elsewhere");
  }
}

/** The fields of one scene the aggregate PUT carries: the whole list, in
 *  its new order — ids the client mints for new scenes, positions implied
 *  by the array (the server renumbers 1..N). The beats are the editor's
 *  own guarantee (the schema's generated optional reads as the server's
 *  default empty list; the working copy never carries `undefined`). */
export type SceneDraft = Omit<SceneUpsert, "beats"> & { beats: string[] };

/**
 * Saving a chapter's whole scene list. The mutation is the version-stamp
 * contract's one door: unless `overwrite`, the chapter is re-read first
 * and a pre-read that cannot answer (an outage, an unusable body)
 * refuses the save as the loss-free error it is — no PUT may cross on a
 * version check that never ran. A stamp that moved under the editor's
 * snapshot refuses as `SceneVersionConflict`, and the server's fresh
 * copy seeds the chapter's standing entry at once — the dock reads the
 * truth behind the face without waiting for the settle's refetch, the
 * same seeding the PUT's own answer performs. The PUT answers the
 * persisted aggregate. Settling invalidates the chapter's own scenes key
 * (the fan's entry — the plan's named seam), the board (the sync
 * statuses derive from the scenes) and the chapters list (the save
 * advances the chapter's stamp, and the workspace's last-edited rule
 * reads it). A refusal carries status and detail — a 422 names the
 * doubled id, the id owned elsewhere or the status outside the
 * lifecycle.
 */
export function useSaveChapterScenes(
  novelId: string,
): UseMutationResult<
  SceneAggregate,
  Error,
  { chapterId: string; scenes: readonly SceneDraft[]; expectedVersion: string; overwrite?: boolean }
> {
  return useMutation({
    mutationFn: async (input: {
      chapterId: string;
      scenes: readonly SceneDraft[];
      expectedVersion: string;
      overwrite?: boolean;
    }) => {
      if (!input.overwrite) {
        const { data, error, response } = await client.GET(
          "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
          { params: { path: { novel_id: novelId, chapter_id: input.chapterId } } },
        );
        // The pre-read must ANSWER before any PUT crosses: falling
        // through on a broken read would name last-writer-wins for a
        // writer who never chose it.
        if (!response.ok || data === undefined) {
          throw refused("scene aggregate pre-read refused", response, error);
        }
        if (data.version_updated_at !== input.expectedVersion) {
          // The server's copy is the answer the conflict face shows — and
          // it seeds the fan's entry at once, so the dock reads the fresh
          // rows behind the face without waiting for the settle's
          // refetch; the standing entry still re-asks to confirm.
          queryClient.setQueryData(chapterScenesKey(input.chapterId), data);
          invalidateChapterScenes(input.chapterId);
          throw new SceneVersionConflict(data);
        }
      }
      const { data, error, response } = await client.PUT(
        "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
        {
          params: { path: { novel_id: novelId, chapter_id: input.chapterId } },
          body: { scenes: [...input.scenes] },
        },
      );
      if (!response.ok || !data) {
        throw refused("scene aggregate refused", response, error);
      }
      return data;
    },
    onSuccess: (answer, input) => {
      // The PUT's own answer seeds the fan's entry at once: without it the
      // snapshot could re-pin the pre-save stamp in the window before the
      // settle's refetch lands, and an immediate second save would refuse
      // as a conflict the write itself caused.
      queryClient.setQueryData(chapterScenesKey(input.chapterId), answer);
    },
    onSettled: (_data, _error, input) => {
      invalidateChapterScenes(input.chapterId);
      invalidateStoryboard(novelId);
      void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
    },
  });
}

/** D8's canon rule, seen from the shelf: every knowledge write that
 *  changes what the export archive carries advances the novel's
 *  `updated_at` on the server, and the shelf's last-touched hero and the
 *  export warning read that column — through this cache's 30 s
 *  staleTime unless the canon-writing mutations invalidate the key
 *  themselves, which would leave the rule unobservable for half a
 *  minute. The `["novels"]` prefix also covers `["novels", id]`, so the
 *  workbench's own novel row refreshes with the shelf.
 *
 *  The atelier's activity aggregate rides the same family (Task 10): a
 *  chapter write moves the day's words, and the banner must not wait out
 *  the staleTime to show it — the workspace wave's save hook joins this
 *  door. Every shelf write asks both keys; the writes that cannot move
 *  words (archive, export, a knowledge edit) pay one small extra GET so
 *  the family stays one seam instead of a rule scattered per mutation. */
function invalidateNovelShelf(): void {
  void queryClient.invalidateQueries({ queryKey: ["novels"] });
  void queryClient.invalidateQueries({ queryKey: ["activity"] });
}

// --- The assistant interview (W9 Task 10) ---------------------------------
//
// The knowledge graph page hosts the first assistant session; chat owns the
// wire. The key prefix is `["chat", …]`, so every read and every write of the
// substrate shares one family: the list (`["chat", "sessions", novelId]`), one
// session's transcript and draft (`["chat", "session", sessionId]`), and the
// three mutations, each invalidating both on settle so a panel that was hidden
// while the model answered reads the reply when it returns.

/** The session read's coded refusal (`{"detail": {"code", "detail"}}`) as the
 *  panel names it. A transport failure has no HTTP answer and is the one
 *  provider failure the panel can only describe, never inspect. */
function assistantFailure(cause: unknown): ApiError {
  const failure = cause as {
    response?: Response;
    error?: { detail?: { code?: string; detail?: string } };
  };
  const response = failure?.response;
  if (response === undefined) {
    return new ApiError("assistant session failed", { code: "provider-error" });
  }
  const detail = failure?.error?.detail;
  return new ApiError("assistant session failed", {
    status: response.status,
    code: detail?.code ?? (response.status === 404 ? "not-found" : undefined),
    detail: detail?.detail,
  });
}

function invalidateAssistantSessions(): void {
  void queryClient.invalidateQueries({ queryKey: ["chat", "sessions"] });
  void queryClient.invalidateQueries({ queryKey: ["chat", "session"] });
}

/**
 * The novel's interviews: open first, then closed, newest first in each state.
 * A row carries the draft's name, never the proposal — opening a session reads
 * the transcript and the draft. The graph's door counts the open rows here,
 * and the panel's list groups them by the same `closed_at`.
 */
export function useAssistantSessionsQuery(
  novelId: string,
): UseQueryResult<AssistantSessionSummary[]> {
  return useQuery({
    queryKey: ["chat", "sessions", novelId],
    queryFn: async () => {
      const { data, error, response } = await client.GET("/api/chat/sessions", {
        params: { query: { novel_id: novelId } },
      });
      if (!response.ok || !data) throw assistantFailure({ response, error });
      return data.items;
    },
  });
}

/**
 * One session with its transcript (oldest first) and its proposal. `null`
 * reads nothing — the chooser has no session yet. A 404 is the coded
 * `not-found` the panel hands back to the door; a closed row still reads, so
 * an ended interview keeps its transcript and its savable draft.
 */
export function useAssistantSessionQuery(
  sessionId: string | null,
): UseQueryResult<AssistantSession> {
  return useQuery({
    queryKey: ["chat", "session", sessionId],
    enabled: sessionId !== null,
    queryFn: async () => {
      const { data, error, response } = await client.GET("/api/chat/sessions/{session_id}", {
        params: { path: { session_id: sessionId ?? "" } },
      });
      if (!response.ok || !data) throw assistantFailure({ response, error });
      return data;
    },
  });
}

/** Open one interview: the panel always sends its mode and the chosen type. */
export function useOpenAssistantSession(): UseMutationResult<
  AssistantSessionRead,
  ApiError,
  AssistantSessionCreate
> {
  return useMutation({
    mutationFn: async (body: AssistantSessionCreate) => {
      const result = await client
        .POST("/api/chat/sessions", { body })
        .catch((cause: unknown) => {
          throw assistantFailure(cause);
        });
      if (!result.response.ok || !result.data) throw assistantFailure(result);
      return result.data;
    },
    onSettled: invalidateAssistantSessions,
  });
}

/** One writer turn: the answer, the merged proposal and any suggestion. The
 *  panel's text lives in its own state, so a failed turn has lost nothing. */
export function useAssistantTurn(): UseMutationResult<
  AssistantTurnReadback,
  ApiError,
  { sessionId: string; body: AssistantTurnCreate }
> {
  return useMutation({
    mutationFn: async ({ sessionId, body }) => {
      const result = await client
        .POST("/api/chat/sessions/{session_id}/turns", {
          params: { path: { session_id: sessionId } },
          body,
        })
        .catch((cause: unknown) => {
          throw assistantFailure(cause);
        });
      if (!result.response.ok || !result.data) throw assistantFailure(result);
      return result.data;
    },
    onSettled: invalidateAssistantSessions,
  });
}

/** End an interview: idempotent, explicit and irreversible. The transcript
 *  stays readable and the proposal stays savable; only the door's count loses
 *  the row from the open group. */
export function useCloseAssistantSession(): UseMutationResult<
  AssistantSessionRead,
  ApiError,
  string
> {
  return useMutation({
    mutationFn: async (sessionId: string) => {
      const result = await client
        .POST("/api/chat/sessions/{session_id}/close", {
          params: { path: { session_id: sessionId } },
        })
        .catch((cause: unknown) => {
          throw assistantFailure(cause);
        });
      if (!result.response.ok || !result.data) throw assistantFailure(result);
      return result.data;
    },
    onSettled: invalidateAssistantSessions,
  });
}
