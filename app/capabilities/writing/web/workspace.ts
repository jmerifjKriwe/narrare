/**
 * The workspace's read/write seam (W4 Tasks 11/13): the queries the three
 * columns share, the pure helpers that turn their answers into the tree,
 * the active-scene marker and the tension card's real labels — and the
 * structure writes the tree's CRUD doors ask through (create, rename,
 * metadata, delete, reorder), each invalidating the read family its server
 * write moves, so the tree's counts go live without a reload.
 *
 * One rule owns the active scene: the last-edited one, by the server's
 * `updated_at` — the same rule the shelf hero's door resumes (gap row 3).
 * Compared as parsed instants, strict comparison, ties keep the first entry
 * in position order, so the choice is deterministic and the door and the
 * marker can never disagree.
 *
 * The storyboard is planning's HTTP surface, read through the typed client
 * (read-only composition — a capability never imports another, rule 1). Its
 * stage title keys resolve against the merged catalog; a key the catalog
 * does not carry keeps the neutral, never a raw key on the page.
 */
import { useMutation, useQueries, useQuery, type UseMutationResult, type UseQueryResult } from "@tanstack/react-query";

import {
  client,
  type Chapter,
  type Scene,
  type Storyboard,
} from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import type { MessageKey } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";

/** A scene's or chapter's title as the page speaks it: the trimmed title,
 *  or the localized placeholder — the database stores no locale (the
 *  backend's own rule for the empty default). */
export function sceneTitle(title: string, placeholder: string): string {
  return title.trim() !== "" ? title : placeholder;
}

/** One scene standing in its chapter — the tree's and the editor's row. */
export interface SceneEntry {
  scene: Scene;
  chapter: Chapter;
}

/**
 * The book's scenes in reading order: chapters in the list's own (position)
 * order, each chapter's scenes sorted by position. The answers may arrive
 * unsorted; the position column is the authority, never the arrival order.
 */
export function orderedSceneEntries(
  chapters: readonly Chapter[],
  scenesByChapter: ReadonlyMap<string, readonly Scene[]>,
): SceneEntry[] {
  const entries: SceneEntry[] = [];
  for (const chapter of chapters) {
    const scenes = [...(scenesByChapter.get(chapter.id) ?? [])].sort(
      (a, b) => a.position - b.position,
    );
    for (const scene of scenes) entries.push({ scene, chapter });
  }
  return entries;
}

/**
 * The last-edited scene — the hero door's resume target and the workspace's
 * default active marker, one rule in one home. Parsed instants (two ISO
 * strings with different offsets do not order as their moments do), strict
 * comparison (a tie keeps the first entry, and the entries are in position
 * order, so the choice stays deterministic).
 */
export function lastEditedEntry(entries: readonly SceneEntry[]): SceneEntry | null {
  let best: SceneEntry | null = null;
  for (const entry of entries) {
    if (best === null || Date.parse(entry.scene.updated_at) > Date.parse(best.scene.updated_at)) {
      best = entry;
    }
  }
  return best;
}

/** The draft's K1-S2 badge numbers, counted from one. The backend's own
 *  numbering: chapters are 0-based, scenes 1-based (the migration wraps
 *  each chapter's prose at position 1, `positions.py`) — the scene's
 *  position IS its ordinal, the chapter's needs the +1. */
export function sceneCodeNumbers(entry: SceneEntry): { chapter: number; scene: number } {
  return { chapter: entry.chapter.position + 1, scene: entry.scene.position };
}

/** One code on the tension card's label row. */
export interface TensionCode {
  chapter: number;
  scene: number;
  active: boolean;
}

/**
 * The tension card's three labels — the first, the active and the last
 * scene — deduplicated when they coincide (a one-scene book stands once).
 * The codes are the rows' own; the curve above them is the drafted
 * placeholder (INTERIM #879 — no tension data exists).
 */
export function tensionCodes(
  entries: readonly SceneEntry[],
  active: SceneEntry | null,
): TensionCode[] {
  if (entries.length === 0) return [];
  const picks = [entries[0], active ?? entries[0], entries[entries.length - 1]];
  const codes: TensionCode[] = [];
  for (const entry of picks) {
    const { chapter, scene } = sceneCodeNumbers(entry);
    const isActive = active !== null && entry.scene.id === active.scene.id;
    const existing = codes.find((code) => code.chapter === chapter && code.scene === scene);
    if (existing) existing.active = existing.active || isActive;
    else codes.push({ chapter, scene, active: isActive });
  }
  return codes;
}

/**
 * The staged chapter's stage title key, resolved against the merged catalog
 * (the writing catalogs carry the storyboard's stage words — planning owns
 * no web surface). A chapter no stage holds, a storyboard that never
 * answered, or a title key the catalog does not carry: the neutral `null`,
 * never a raw key and never a guessed stage.
 */
export function stageTitleKey(
  storyboard: Storyboard | null | undefined,
  chapterId: string | null,
): MessageKey | null {
  if (storyboard == null || chapterId === null) return null;
  for (const stage of storyboard.stages) {
    if ((stage.chapters ?? []).some((chapter) => chapter.chapter_id === chapterId)) {
      // The membership check is the cast's guard: only a key the source
      // catalog carries reaches the message function.
      return stage.title_key in catalogs.en ? (stage.title_key as MessageKey) : null;
    }
  }
  return null;
}

/**
 * One chapter's scenes question — the key and the ask in one home, so the
 * per-chapter list below and any future single-chapter reader cannot drift.
 * The tree and the editor read the same answer; the save seam
 * (`invalidateSceneReads`) invalidates the key when a scene's prose lands.
 * An answer that is not ok throws, so the cache holds either the list or the
 * failure — never a half-current list.
 */
function scenesQueryOptions(chapterId: string) {
  return {
    queryKey: ["scenes", chapterId],
    queryFn: async () => {
      const { data, response } = await client.GET("/api/writing/chapters/{chapter_id}/scenes", {
        params: { path: { chapter_id: chapterId } },
      });
      if (!response.ok) throw new Error(`scenes unavailable: ${response.status}`);
      return data ?? [];
    },
  };
}

/**
 * Every chapter's scenes, one question per chapter, aligned with the
 * chapters list (the API lists scenes per chapter — there is no novel-level
 * scene list). The results keep the list's order, so the page can zip them
 * without a second lookup.
 */
export function useChapterScenes(chapters: readonly Chapter[]): UseQueryResult<Scene[]>[] {
  return useQueries({
    queries: chapters.map((chapter) => scenesQueryOptions(chapter.id)),
  });
}

/**
 * The read family a chapter-shape write refreshes (W4 Task 13): the
 * chapters list (the derived Σ and scene_count), the novels family (the
 * book's own count and timestamp — the hero's order, the topbar chip) and
 * the activity aggregate (the day's words the ring shows). A create, a
 * rename or a delete moves these on the server, so they ask again. Success
 * only — a refused write changed nothing and asks for nothing.
 */
export function invalidateStructureReads(novelId: string): void {
  void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
  void queryClient.invalidateQueries({ queryKey: ["novels"] });
  void queryClient.invalidateQueries({ queryKey: ["activity"] });
}

/**
 * The read family a landed scene save refreshes (W4 Task 12) — one home for
 * the autosave hook's invalidation, so the shelf's hero door and the
 * workspace can never disagree (PR 2's carry-note). The scene's own list
 * (`["scenes", chapterId]`) carries the new body, word count and
 * `updated_at` — the last-edited rule the hero door resumes reads it; the
 * structure family beside it (Task 13's seam) carries the chapter Σ, the
 * book's count and the day's words. A body write moves all four on the
 * server (`service.update_scene`), so all four ask again. Success only — a
 * refused write changed nothing and asks for nothing. The tree's CRUD
 * writes that touch a scene's row ask through this same door, so the live
 * counts reconcile with the autosave's without a second rule.
 */
export function invalidateSceneReads(chapterId: string, novelId: string): void {
  void queryClient.invalidateQueries({ queryKey: ["scenes", chapterId] });
  invalidateStructureReads(novelId);
}

/**
 * The novel's storyboard — planning's read-only HTTP surface (the tension
 * card's stage label). The key carries the planning prefix so a later
 * planning wave's writes invalidate it without reaching into writing's
 * keys. A refusal throws; the card keeps its neutral label, the page stands.
 */
export function useStoryboardQuery(novelId: string): UseQueryResult<Storyboard> {
  return useQuery({
    queryKey: ["planning", "storyboard", novelId],
    queryFn: async () => {
      const { data, response } = await client.GET("/api/planning/novels/{novel_id}/storyboard", {
        params: { path: { novel_id: novelId } },
      });
      if (!response.ok || !data) throw new Error(`storyboard unavailable: ${response.status}`);
      return data;
    },
  });
}

/** The per-chapter answers as the map the pure helpers read. A chapter whose
 *  ask has not answered contributes no scenes yet — the tree shows its
 *  skeleton, never an invented empty list. */
export function scenesByChapterFrom(
  chapters: readonly Chapter[],
  results: readonly UseQueryResult<Scene[]>[],
): Map<string, readonly Scene[]> {
  const map = new Map<string, readonly Scene[]>();
  chapters.forEach((chapter, at) => {
    const data = results[at]?.data;
    if (data !== undefined) map.set(chapter.id, data);
  });
  return map;
}

// --- The tree's order (W4 Task 13) -----------------------------------------

/**
 * The whole order one drag asks for: the dragged id lifted out and set
 * before or after the target — the permutation the order PUT carries. A
 * drop on itself, or an id the order does not hold, keeps the order as it
 * stands (no write owed, nothing invented). The keyboard's one-step move
 * is the same helper: up is „before the predecessor", down „after the
 * successor".
 */
export function movedIds(
  ids: readonly string[],
  draggedId: string,
  targetId: string,
  before: boolean,
): string[] {
  if (draggedId === targetId || !ids.includes(draggedId) || !ids.includes(targetId)) {
    return [...ids];
  }
  const next = ids.filter((id) => id !== draggedId);
  const at = next.indexOf(targetId);
  next.splice(before ? at : at + 1, 0, draggedId);
  return next;
}

/**
 * The rows in the order the ids name, positions renumbered from the level's
 * base (chapters 0, scenes 1 — the position IS the scene's ordinal). Every
 * other field rides untouched: an arrangement is not a write (D8). `null`
 * when the ids name a row the cache lacks — a second tab's addition the
 * client cannot invent; the caller refetches the truth instead.
 */
export function rowsInOrder<T extends { id: string; position: number }>(
  rows: readonly T[],
  ids: readonly string[],
  positionBase: number,
): T[] | null {
  // The whole set or nothing — an arrangement is a permutation of the rows
  // the cache holds, never a subset (the order PUT's own contract).
  if (ids.length !== rows.length) return null;
  const byId = new Map(rows.map((row) => [row.id, row]));
  const ordered: T[] = [];
  for (const [at, id] of ids.entries()) {
    const row = byId.get(id);
    if (row === undefined) return null;
    ordered.push({ ...row, position: positionBase + at });
  }
  return ordered;
}

/**
 * The tree's honest notice after a write that did not land as asked — the
 * shelf quick menu's gentle error line, re-owned under the tree. A create
 * refusal retries the very create; a reorder refusal retries the very
 * arrangement; a reorder CONFLICT (the 409's stored ids) has already
 * reverted the tree to the server's truth — its retry asks that truth
 * again, never re-sends the stale arrangement.
 */
export type TreeNotice =
  | { kind: "createChapterFailed" }
  | { kind: "createSceneFailed"; chapterId: string }
  | { kind: "reorderConflict" }
  | { kind: "reorderFailed"; level: "chapters" | "scenes"; chapterId: string | null; ids: string[] };

// --- The structure writes (W4 Task 13) -------------------------------------
//
// The query.ts convention, one home beside the reads: the mutation carries
// the request, success alone invalidates the family the server write moves,
// and a refusal throws with its status (the machine-readable fact the page
// answers by name). The reorder pair carries the 409's stored ids beside
// the status — the arrangement the client reverts to.

/** A refusal with its status — the accept-suggestion precedent. */
function refused(message: string, status: number): Error {
  return Object.assign(new Error(`${message}: ${status}`), { status });
}

/** Creating a chapter: the honest empty title, zero scenes (D16 — the
 *  empty-chapter face is the canonical new-chapter experience, no
 *  auto-create). The structure family refetches; the new chapter's scene
 *  list is asked when the tree renders it. */
export function useCreateChapter(novelId: string): UseMutationResult<Chapter, Error, void> {
  return useMutation({
    mutationFn: async () => {
      const { data, response } = await client.POST("/api/writing/novels/{novel_id}/chapters", {
        params: { path: { novel_id: novelId } },
        body: { title: "" },
      });
      if (!response.ok || !data) throw refused("chapter create refused", response.status);
      return data;
    },
    onSuccess: () => invalidateStructureReads(novelId),
  });
}

/** Creating a scene under a chapter: born empty, position allocated by the
 *  server under the book's lock. The scene family refetches — the tree's
 *  counts and the last-edited rule read the new row. */
export function useCreateScene(novelId: string): UseMutationResult<Scene, Error, { chapterId: string }> {
  return useMutation({
    mutationFn: async ({ chapterId }: { chapterId: string }) => {
      const { data, response } = await client.POST("/api/writing/chapters/{chapter_id}/scenes", {
        params: { path: { chapter_id: chapterId } },
        // The honest empty defaults, carried explicitly (the schema's own).
        body: { title: "", body: "" },
      });
      if (!response.ok || !data) throw refused("scene create refused", response.status);
      return data;
    },
    onSuccess: (_data, { chapterId }) => invalidateSceneReads(chapterId, novelId),
  });
}

/** Renaming a chapter: the title alone — the prose lives on scenes now.
 *  `""` after the service's trim is the honest unnamed (the placeholder a
 *  rendering, not a value). */
export function useUpdateChapter(
  novelId: string,
): UseMutationResult<Chapter, Error, { chapterId: string; title: string }> {
  return useMutation({
    mutationFn: async ({ chapterId, title }: { chapterId: string; title: string }) => {
      const { data, response } = await client.PUT("/api/writing/chapters/{chapter_id}", {
        params: { path: { chapter_id: chapterId } },
        body: { title },
      });
      if (!response.ok || !data) throw refused("chapter update refused", response.status);
      return data;
    },
    onSuccess: () => invalidateStructureReads(novelId),
  });
}

/** The fields a scene edit may carry: only these reach the PUT body — the
 *  client's mirror of the server's `model_fields_set` contract. The two
 *  labels are present-and-nullable: a carried `null` clears the label back
 *  to the honest unset; the body is never a field this door carries (the
 *  autosave owns it). */
export type SceneChanges = {
  title?: string;
  setting?: string | null;
  story_time?: string | null;
};

/** Editing a scene's metadata (title, setting, story_time). The scene
 *  family refetches: the tree's label, the editor's overline and the
 *  last-edited rule all read the changed row. */
export function useUpdateScene(
  novelId: string,
): UseMutationResult<Scene, Error, { sceneId: string; chapterId: string; changes: SceneChanges }> {
  return useMutation({
    mutationFn: async ({ sceneId, changes }: { sceneId: string; chapterId: string; changes: SceneChanges }) => {
      const { data, response } = await client.PUT("/api/writing/scenes/{scene_id}", {
        params: { path: { scene_id: sceneId } },
        body: changes,
      });
      if (!response.ok || !data) throw refused("scene update refused", response.status);
      return data;
    },
    onSuccess: (_data, { chapterId }) => invalidateSceneReads(chapterId, novelId),
  });
}

/** Deleting a chapter: the scenes cascade, the survivors renumber, the
 *  novel's timestamp advances. The structure family refetches and the dead
 *  chapter's scene list is retired from the cache — no view may read a
 *  list whose chapter no longer exists. */
export function useDeleteChapter(novelId: string): UseMutationResult<void, Error, string> {
  return useMutation({
    mutationFn: async (chapterId: string) => {
      const { response } = await client.DELETE("/api/writing/chapters/{chapter_id}", {
        params: { path: { chapter_id: chapterId } },
      });
      if (!response.ok) throw refused("chapter delete refused", response.status);
    },
    onSuccess: (_data, chapterId) => {
      invalidateStructureReads(novelId);
      queryClient.removeQueries({ queryKey: ["scenes", chapterId] });
    },
  });
}

/** Deleting a scene: ALWAYS allowed — the last scene leaves the chapter
 *  empty (D16), the survivors close the gap. The scene family refetches;
 *  the chapter reads honestly at zero. */
export function useDeleteScene(
  novelId: string,
): UseMutationResult<void, Error, { sceneId: string; chapterId: string }> {
  return useMutation({
    mutationFn: async ({ sceneId }: { sceneId: string; chapterId: string }) => {
      const { response } = await client.DELETE("/api/writing/scenes/{scene_id}", {
        params: { path: { scene_id: sceneId } },
      });
      if (!response.ok) throw refused("scene delete refused", response.status);
    },
    onSuccess: (_data, { chapterId }) => invalidateSceneReads(chapterId, novelId),
  });
}

/** The 409's stored ids, when the refusal is the order mismatch — the
 *  arrangement the client reverts to. Any other refusal carries none. */
function storedIdsFrom(error: unknown, field: "chapter_ids" | "scene_ids"): string[] | null {
  const detail = (error as { detail?: { code?: string } & Record<string, unknown> } | null | undefined)?.detail;
  if (detail?.code !== "order_mismatch") return null;
  const ids = detail[field];
  return Array.isArray(ids) ? (ids as string[]) : null;
}

/** What an arrangement advances: the novel's `updated_at` (D8 — the shelf's
 *  hero order and the topbar chip read it) and the activity family's one
 *  small extra GET (the shelf's one-seam discipline). NEVER the ordered
 *  lists: the optimistic order is what the 204 acknowledged, and a refetch
 *  mid-unsaved-body is the state the save-side rule guards against. */
function invalidateArrangement(): void {
  void queryClient.invalidateQueries({ queryKey: ["novels"] });
  void queryClient.invalidateQueries({ queryKey: ["activity"] });
}

/** Reordering the chapters: the PUT chapter-order write, the whole rail in
 *  its new order. The caller writes the arrangement into the cache
 *  optimistically first; a 409 carries the stored ids (the second tab's
 *  truth) beside the status, every other refusal its status alone. */
export function useReorderChapters(novelId: string): UseMutationResult<void, Error, string[]> {
  return useMutation({
    mutationFn: async (chapterIds: string[]) => {
      const { error, response } = await client.PUT("/api/writing/novels/{novel_id}/chapter-order", {
        params: { path: { novel_id: novelId } },
        body: { chapter_ids: chapterIds },
      });
      if (!response.ok) {
        throw Object.assign(refused("chapter reorder refused", response.status), {
          storedIds: response.status === 409 ? storedIdsFrom(error, "chapter_ids") : null,
        });
      }
    },
    onSuccess: () => invalidateArrangement(),
  });
}

/** Reordering a chapter's scenes: the PUT scene-order write, the whole
 *  chapter in its new order — the chapters' contract one level down. */
export function useReorderScenes(
  novelId: string,
): UseMutationResult<void, Error, { chapterId: string; ids: string[] }> {
  return useMutation({
    mutationFn: async ({ chapterId, ids }: { chapterId: string; ids: string[] }) => {
      const { error, response } = await client.PUT("/api/writing/chapters/{chapter_id}/scene-order", {
        params: { path: { chapter_id: chapterId } },
        body: { ids },
      });
      if (!response.ok) {
        throw Object.assign(refused("scene reorder refused", response.status), {
          storedIds: response.status === 409 ? storedIdsFrom(error, "scene_ids") : null,
        });
      }
    },
    onSuccess: () => invalidateArrangement(),
  });
}
