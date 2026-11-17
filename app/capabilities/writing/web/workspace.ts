/**
 * The workspace's read seam (W4 Task 11): the queries the three columns
 * share and the pure helpers that turn their answers into the tree, the
 * active-scene marker and the tension card's real labels.
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
import { useQueries, useQuery, type UseQueryResult } from "@tanstack/react-query";

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
 * The read family a landed scene save refreshes (W4 Task 12) — one home for
 * the autosave hook's invalidation, so the shelf's hero door and the
 * workspace can never disagree (PR 2's carry-note). The scene's own list
 * (`["scenes", chapterId]`) carries the new body, word count and
 * `updated_at` — the last-edited rule the hero door resumes reads it; the
 * chapter list carries the derived Σ; the novels family the book's own count
 * and timestamp (the hero's order, the topbar chip); the activity aggregate
 * the day's words the ring shows. A body write moves all four on the server
 * (`service.update_scene`), so all four ask again. Success only — a refused
 * write changed nothing and asks for nothing.
 */
export function invalidateSceneReads(chapterId: string, novelId: string): void {
  void queryClient.invalidateQueries({ queryKey: ["scenes", chapterId] });
  void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
  void queryClient.invalidateQueries({ queryKey: ["novels"] });
  void queryClient.invalidateQueries({ queryKey: ["activity"] });
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
