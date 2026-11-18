/**
 * The workspace's read/write seam (W4 Tasks 11/13/16): the queries the three
 * columns share, the pure helpers that turn their answers into the tree,
 * the active-scene marker and the tension card's real labels — and the
 * structure writes the tree's CRUD doors ask through (create, rename,
 * metadata, delete, reorder), each invalidating the read family its server
 * write moves, so the tree's counts go live without a reload. Task 16 adds
 * the continuation stream: the ghost text's lifecycle on the scene continue
 * endpoint's SSE door (the ask, the phase machine, the dismissal — the
 * editor owns the Tab insertion and the autosave handoff). Task 18 adds
 * the zen seam: the Satz-Fokus's sentence geometry, the session-only
 * pomodoro and the session word delta — the draft's frontend-real pieces
 * (D6), pure and hook-shaped beside the reads.
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
import { useCallback, useEffect, useRef, useState } from "react";

import {
  client,
  type Chapter,
  type Novel,
  type NovelChanges,
  type Scene,
  type Series,
  type Storyboard,
} from "@shell/lib/api/client";
import { readSse } from "@shell/lib/api/sse";
import { catalogs } from "@shell/lib/generated/catalogs";
import type { MessageKey } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { countWords } from "@shell/lib/words";

// Type-only: the autosave's flush vocabulary, erased at runtime (the
// autosave imports this seam's invalidation door — no runtime cycle).
import type { FlushOutcome } from "./useAutosave";

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

/** Renaming a chapter and setting its word goal (W4 Task 19): the title
 *  and the goal ride the one PUT door, each only when carried — `""` after
 *  the service's trim is the honest unnamed (the placeholder a rendering,
 *  not a value); a carried `null` goal clears back to the honest unset, an
 *  absent one keeps the stored goal. */
export function useUpdateChapter(
  novelId: string,
): UseMutationResult<Chapter, Error, { chapterId: string; title?: string; targetWords?: number | null }> {
  return useMutation({
    mutationFn: async ({ chapterId, title, targetWords }: { chapterId: string; title?: string; targetWords?: number | null }) => {
      const body: { title?: string; target_words?: number | null } = {};
      if (title !== undefined) body.title = title;
      if (targetWords !== undefined) body.target_words = targetWords;
      const { data, response } = await client.PUT("/api/writing/chapters/{chapter_id}", {
        params: { path: { chapter_id: chapterId } },
        body,
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

// --- The settings writes (W4 Task 19) --------------------------------------
//
// The book-settings dialog's doors: the novel PATCH (only the carried
// fields change — the client builds the diff, a carried null clears), the
// series create/list the select rides, and the atelier's profile write
// through the settings capability's HTTP door (read-only composition's
// write sibling — the shell's language switcher PATCHes the same row).
// Success alone invalidates the family the server write moves.

/** The user's series, alphabetical — the book-settings select's list.
 *  The key carries the writing prefix; the create invalidates it. */
export function useSeriesQuery(): UseQueryResult<Series[]> {
  return useQuery({
    queryKey: ["series"],
    queryFn: async () => {
      const { data, response } = await client.GET("/api/writing/series");
      if (!response.ok) throw new Error(`series unavailable: ${response.status}`);
      return data ?? [];
    },
  });
}

/** Creating a series inline (the draft's „Neue Reihe anlegen"): the row
 *  exists once the POST lands — the select offers it at once, and the
 *  book's link rides the novel PATCH on Speichern. */
export function useCreateSeries(): UseMutationResult<Series, Error, { title: string }> {
  return useMutation({
    mutationFn: async ({ title }: { title: string }) => {
      const { data, response } = await client.POST("/api/writing/series", { body: { title } });
      if (!response.ok || !data) throw refused("series create refused", response.status);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["series"] });
    },
  });
}

/** The novel PATCH: the carried fields alone are the change (the server's
 *  `model_fields_set` contract). The novels family refetches — the shelf's
 *  pills, the hero's series line, the identity card and the running head
 *  all read the changed row. */
export function useUpdateNovel(novelId: string): UseMutationResult<Novel, Error, NovelChanges> {
  return useMutation({
    mutationFn: async (changes: NovelChanges) => {
      const { data, response } = await client.PATCH("/api/writing/novels/{novel_id}", {
        params: { path: { novel_id: novelId } },
        body: changes,
      });
      if (!response.ok || !data) throw refused("novel update refused", response.status);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
    },
  });
}

/** The atelier's profile write (the settings capability's row): the locale
 *  is ALWAYS carried — the schema requires it, present and nullable — so
 *  the caller hands the stored one through unchanged; the profile fields
 *  ride only when carried (a carried null clears). The settings row and
 *  the activity aggregate refetch: the chrome's user block reads the name,
 *  the ring and the banner read the goal. */
export function useUpdateSettings(): UseMutationResult<
  void,
  Error,
  { locale: string | null; authorName?: string | null; dailyGoalWords?: number | null }
> {
  return useMutation({
    mutationFn: async ({ locale, authorName, dailyGoalWords }) => {
      const body: { locale: string | null; author_name?: string | null; daily_goal_words?: number | null } = { locale };
      if (authorName !== undefined) body.author_name = authorName;
      if (dailyGoalWords !== undefined) body.daily_goal_words = dailyGoalWords;
      const { response } = await client.PATCH("/api/settings", { body });
      if (!response.ok) throw refused("settings update refused", response.status);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

// --- The continuation stream (W4 Task 16) ---------------------------------
//
// The ghost text's lifecycle rides the scene continue endpoint's SSE door
// (design G4/D5): deltas accumulate into the preview, `done` rests it
// pending at the scene tail, the coded `error` frame (or a refusal before
// the stream, or a dead connection) raises the error face. The stream is
// consumed through the shell's SSE reader — fetch, not the typed client,
// which buffers the whole answer; a continuation must arrive piece by piece.
//
// Acceptance is NOT here: the editor inserts the pending text at the tail
// and hands the joined body to the autosave chain (the one write path), so
// the save invalidates the ["scenes", chapterId] family exactly as a typed
// edit does. This seam owns the ask, the stream and the dismissal.
//
// The ask is SAVE-FIRST (the leave guard's flush-first rule): the server
// continues the SAVED body, so every start and retry settles the active
// scene's autosave before the wire — the page hands its flush over as the
// seam. A failed flush sends nothing: the autosave's own failure face
// stands, the writer saves first.

/** The ghost's four faces: nothing stands, the wire is running, the proposal
 *  rests at the tail (Tab accepts), or the continuation failed (the states
 *  sheet's KACHEL 8). */
export type ContinuationPhase = "idle" | "streaming" | "pending" | "error";

export interface Continuation {
  phase: ContinuationPhase;
  /** The accumulated proposal — the ghost preview's text. */
  text: string;
  /** The failure's machine code (the coded frame's own, or the client's
   *  name for a refusal before the stream) — null while no error stands. */
  errorCode: string | null;
  /** Ask for a continuation; a carried prompt rides the optional body
   *  (D5), an absent one is today's bare continuation. Replaces any
   *  standing ghost — one proposal at a time. With the page's save seam
   *  handed over, the ask flushes the autosave FIRST: a failed flush sends
   *  nothing (the writer saves first). */
  start: (prompt?: string) => void;
  /** Drop the ghost and abort any running stream — Esc, typing, Stoppen,
   *  Verwerfen. A chosen stop is no failure: no error face follows it. */
  dismiss: () => void;
  /** Re-run the very last ask — the error face's „Erneut versuchen". */
  retry: () => void;
}

/** The prompt bound's client mirror — the schema's own (SceneContinue, the
 *  chat question's precedent): 1–2000 characters of the RAW string, no
 *  trim. The count is CODE POINTS, the server's len(): JS .length counts
 *  UTF-16 units, and an astral character (an emoji) is two of those — the
 *  unit count would refuse what the server accepts. The bar refuses an
 *  over-long instruction before the wire; the empty input is no prompt at
 *  all (the bare continuation), not a refusal. */
export const PROMPT_MAX_LENGTH = 2000;

export function promptWithinBound(prompt: string): boolean {
  const codePoints = [...prompt].length;
  return codePoints >= 1 && codePoints <= PROMPT_MAX_LENGTH;
}

/** The code a terminal error frame carries — the payload's own `code`, or
 *  the contract's fallback when a malformed frame names none. */
function errorCodeOf(data: string): string {
  try {
    const payload = JSON.parse(data) as { code?: unknown };
    return typeof payload.code === "string" ? payload.code : "unknown";
  } catch {
    return "unknown";
  }
}

/** The delta a data frame carries, or null when it carries none. */
function deltaOf(data: string): string | null {
  try {
    const payload = JSON.parse(data) as { delta?: unknown };
    return typeof payload.delta === "string" ? payload.delta : null;
  } catch {
    return null;
  }
}

/** What one running stream tells its hook — every answer checked against
 *  the stream's own abort signal first: a retired stream never speaks. */
interface ContinuationSink {
  delta: (text: string) => void;
  done: () => void;
  error: (code: string) => void;
}

/** Consume one continuation ask to its terminal frame. The refusal before
 *  the stream (the schema's 422, the 404) is a JSON answer, not SSE — named
 *  by its status; a stream that closes without done/error is the silent
 *  close the router's own docblock forbids, named `interrupted`. */
async function consumeContinuation(
  sceneId: string,
  prompt: string | undefined,
  signal: AbortSignal,
  sink: ContinuationSink,
): Promise<void> {
  let response: Response;
  try {
    // Fixed same-origin base + the encoded server-issued id, concatenated
    // (never interpolated) — one path segment, no SSRF-shaped template.
    // SSRF false positive: the base is a constant relative path and the id a
    // server-issued UUID — no user-controlled URL (PR #901's Codacy round).
    response = await fetch("/api/writing/scenes/" + encodeURIComponent(sceneId) + "/continue", { // nosemgrep: Semgrep_rules_lgpl_javascript_ssrf_rule-node-ssrf
      method: "POST",
      signal,
      // The bare continuation carries no body at all — the endpoint's own
      // shape since before D5; a prompt rides the JSON body.
      ...(prompt !== undefined
        ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) }
        : {}),
    });
  } catch {
    if (!signal.aborted) sink.error("network");
    return;
  }
  if (signal.aborted) return;
  if (!response.ok || response.body === null) {
    // The refusal is a JSON answer, not a stream — release the connection.
    void response.body?.cancel();
    sink.error(`http-${response.status}`);
    return;
  }
  try {
    for await (const frame of readSse(response.body)) {
      if (signal.aborted) return;
      if (frame.event === "done") {
        sink.done();
        return;
      }
      if (frame.event === "error") {
        sink.error(errorCodeOf(frame.data));
        return;
      }
      const delta = deltaOf(frame.data);
      if (delta !== null) sink.delta(delta);
    }
    if (!signal.aborted) sink.error("interrupted");
  } catch {
    if (!signal.aborted) sink.error("network");
  }
}

/**
 * The continuation hook — one ghost for the active scene. The page owns it
 * (its lifetime matches the page, beside the autosave); the editor renders
 * the ghost and owns the Tab insertion, the bar owns the ask. A scene
 * switch retires the ghost: it belongs to the tail it was asked for. An
 * unmount aborts the stream — the server's audit records the interruption.
 *
 * The optional `flush` is the page's autosave seam (the leave guard's
 * flush-first rule, the ask's own door): the server continues the SAVED
 * body, so every start and retry settles the draft before the wire. A
 * failed flush keeps the ask home — the autosave's failure face already
 * stands. Without the seam the ask rides straight to the wire (today's
 * behavior, the hook's own tests).
 */
export function useContinuation(
  sceneId: string | null,
  flush?: () => Promise<FlushOutcome>,
): Continuation {
  const [phase, setPhase] = useState<ContinuationPhase>("idle");
  const [text, setText] = useState("");
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const lastPrompt = useRef<string | undefined>(undefined);
  // The accumulated text beside the state — the done answer reads it
  // without waiting for a render (an empty answer is no continuation).
  const accumulated = useRef("");
  const scene = useRef(sceneId);
  scene.current = sceneId;

  const dismiss = useCallback(() => {
    abort.current?.abort();
    abort.current = null;
    accumulated.current = "";
    setPhase("idle");
    setText("");
    setErrorCode(null);
  }, []);

  const start = useCallback(
    (prompt?: string) => {
      const target = scene.current;
      if (target === null) return;
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      lastPrompt.current = prompt;

      const begin = () => {
        accumulated.current = "";
        setPhase("streaming");
        setText("");
        setErrorCode(null);
        void consumeContinuation(target, prompt, controller.signal, {
          delta: (piece) => {
            if (controller.signal.aborted) return;
            accumulated.current += piece;
            setText(accumulated.current);
          },
          done: () => {
            if (controller.signal.aborted) return;
            if (accumulated.current === "") {
              // Nothing arrived: a blank pill would be a false affordance.
              setPhase("error");
              setErrorCode("empty");
            } else {
              setPhase("pending");
            }
          },
          error: (code) => {
            if (controller.signal.aborted) return;
            setPhase("error");
            setErrorCode(code);
          },
        });
      };

      // No save seam: today's ask, straight to the wire (the hook's own
      // tests; the page always hands its autosave's flush over).
      if (flush === undefined) {
        begin();
        return;
      }
      // Save first (the leave guard's flush-first rule): the server
      // continues the SAVED body — unsaved words must land before the ask.
      // A failed flush sends nothing; the autosave's failure face stands.
      // A dismissal, a replacement or a scene switch during the flush
      // retires the ask — the controller's abort is the stream's own guard.
      void flush().then((outcome) => {
        if (controller.signal.aborted || outcome === "failed") return;
        if (scene.current !== target) return;
        begin();
      });
    },
    [flush],
  );

  const retry = useCallback(() => start(lastPrompt.current), [start]);

  // A scene switch (and the first mount) rests the ghost at idle — the
  // ghost belongs to the tail it was asked for.
  // biome-ignore lint/correctness/useExhaustiveDependencies: sceneId is the deliberate re-run key, not a value the body reads — a scene switch must retire the ghost (the WorkspacePage novelId reset's own pattern).
  useEffect(() => {
    dismiss();
  }, [sceneId]);

  // The page goes away: the stream goes with it.
  useEffect(
    () => () => {
      abort.current?.abort();
    },
    [],
  );

  return { phase, text, errorCode, start, dismiss, retry };
}

// --- The zen seam (W4 Task 18) ----------------------------------------------
//
// The frontend-real pieces of the zen draft (D6): the sentence geometry the
// Satz-Fokus dims by, the session-only pomodoro and the session word delta.
// The timer keeps NOTHING — no storage write, no server row (design §12:
// „Zen timer is session-only"); its whole lifetime is the zen spell, and a
// re-entry starts fresh. The counters' today half reads the activity
// aggregate at the page (the ring's own source); the session half is the
// live net delta since entry — the shared whitespace rule counts, the same
// figure the server derives. The dimming itself rides the editor's
// decoration plugin (SceneEditor); the presets' geometry lives here, pure
// and testable without ProseMirror.

/** The three focus presets the draft's segment control draws. */
export type ZenFocusMode = "paragraph" | "sentence" | "normal";

/** The pomodoro's span — the classic 25 minutes. The draft's „18:42" is a
 *  mock mid-count; the session starts full. */
export const POMODORO_SECONDS = 25 * 60;

/** The timer's face: minutes and seconds, two digits each. */
export function formatClock(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/**
 * The text's sentences as half-open spans — the Satz-Fokus's geometry. A
 * sentence ends at a run of terminal punctuation (. ! ? …) followed by the
 * closing quotes that belong to it (the German „…" face included) and then
 * whitespace or the end; the whitespace BETWEEN sentences belongs to no
 * span. Text without a terminal is one sentence — the whole span. Empty or
 * whitespace-only text carries none. A simple honest splitter: no
 * abbreviation dictionary (a „z. B." reads as a boundary — the draft draws
 * no abbreviation rule, and a guessed one would dim the wrong words).
 */
export function sentenceSpans(text: string): Array<readonly [number, number]> {
  const spans: Array<readonly [number, number]> = [];
  const terminal = /[.!?…]+[»"“”'’)\]]*(?=\s|$)/g;
  let start = 0;
  let match: RegExpExecArray | null;
  while ((match = terminal.exec(text)) !== null) {
    const end = match.index + match[0].length;
    if (text.slice(start, end).trim() !== "") spans.push([start, end]);
    start = end;
    while (start < text.length && /\s/.test(text[start])) start += 1;
    terminal.lastIndex = start;
  }
  if (start < text.length && text.slice(start).trim() !== "") spans.push([start, text.length]);
  return spans;
}

/**
 * The sentence the caret sits in — end-inclusive (the boundary right after
 * the terminal keeps the sentence just ended). An offset in the whitespace
 * between sentences keeps the PREVIOUS one: the writer just finished it.
 * No text, no sentence — null, never an invented span.
 */
export function activeSentence(text: string, offset: number): readonly [number, number] | null {
  const spans = sentenceSpans(text);
  if (spans.length === 0) return null;
  for (const span of spans) {
    if (offset >= span[0] && offset <= span[1]) return span;
  }
  let best = spans[0];
  for (const span of spans) {
    if (span[1] <= offset) best = span;
  }
  return best;
}

/** The pomodoro's state — the session's own, never stored. */
export interface ZenTimer {
  /** The seconds left on the clock. */
  remaining: number;
  /** Whether the clock is running. */
  running: boolean;
  /** The span is spent — the clock rests at zero. */
  done: boolean;
  /** Pause a running clock, resume a held one; a spent span starts fresh. */
  toggle: () => void;
  /** The full span again, running — the draft's start affordance. */
  reset: () => void;
}

/**
 * The session-only pomodoro (D6, design §12): starts full and running —
 * the draft's timer is already on when the room opens — counts down one
 * second at a time, rests at zero (never negative), and keeps nothing:
 * no localStorage, no sessionStorage, no server row. The hook's lifetime
 * IS the session; the zen surface mounts it on entry and unmounts it on
 * exit, so a re-entry starts a fresh span by construction.
 */
export function useZenTimer(): ZenTimer {
  const [remaining, setRemaining] = useState(POMODORO_SECONDS);
  const [running, setRunning] = useState(true);
  const done = remaining === 0;

  useEffect(() => {
    if (!running || done) return;
    const id = window.setInterval(() => setRemaining((seconds) => Math.max(0, seconds - 1)), 1000);
    return () => window.clearInterval(id);
  }, [running, done]);

  // The spent span rests the clock — the toggle's fresh start is the
  // writer's own choice, never an automatic restart.
  useEffect(() => {
    if (done) setRunning(false);
  }, [done]);

  const toggle = useCallback(() => {
    if (done) {
      setRemaining(POMODORO_SECONDS);
      setRunning(true);
      return;
    }
    setRunning((value) => !value);
  }, [done]);

  const reset = useCallback(() => {
    setRemaining(POMODORO_SECONDS);
    setRunning(true);
  }, []);

  return { remaining, running, done, toggle, reset };
}

/** The session word counter's state — the net delta since zen entry. */
export interface SessionWords {
  /** The net words the session added (a removal is honest — negative). */
  words: number;
  /** Feed every edit's whole body; the delta against the last figure rides
   *  the shared whitespace rule (the server's own count). */
  track: (body: string) => void;
}

/**
 * The live session delta: the entry body is the baseline (zero, never a
 * claim), every edit moves the counter by the net words it changed. The
 * hook lives in the zen surface — its lifetime is the spell, so the
 * counter resets on re-entry by construction. The today half of the
 * draft's chip is NOT here: it reads the activity aggregate at the page.
 */
export function useSessionWords(initialBody: string): SessionWords {
  const [words, setWords] = useState(0);
  const previous = useRef(countWords(initialBody));
  const track = useCallback((body: string) => {
    const next = countWords(body);
    const delta = next - previous.current;
    previous.current = next;
    if (delta !== 0) setWords((value) => value + delta);
  }, []);
  return { words, track };
}
