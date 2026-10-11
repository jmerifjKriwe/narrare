"use client";

/**
 * useSceneDraftContext — assembles the chapter context for the AI scene
 * draft (PLAN-001 follow-up #1) from data the studio already holds.
 *
 * Sources, each degrading independently (a missing/failed fetch yields no
 * field — the BE omits empty `<chapter_context>` lines, and the zero-context
 * body remains the graceful floor, never a blocker):
 *
 * - `structure_type`: the planning storyboard (mirrors `novel.story_structure`,
 *   the same value the BE's storyboard view reports).
 * - `outline_notes`: the chapter outline aggregate (`getOutline`) — this also
 *   resolves the endpoint's orphaned-client status (CURRENT_STATE FU#4).
 * - `chapter_summary` / `neighbor_summaries`: chapter detail records
 *   (`Chapter.summary`) for the current and the position-adjacent chapters,
 *   ordered via the storyboard stage layout.
 *
 * `instruction` is intentionally NOT sourced — no UI collects one yet; the
 * server default ("") applies.
 *
 * The outline key comes from `usePlanning`'s exported `planningKeys` factory;
 * the chapter-detail key follows the `["novels", novelId, "chapters", chapterId]`
 * convention shared with the editor view, so cache invalidations stay coherent
 * across features.
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { chaptersApi } from "@/lib/api/client";
import { getOutline } from "@/lib/api/planning";
import { planningKeys, useStoryboard } from "@/lib/hooks/usePlanning";
import type { Chapter, ChapterInStoryboard, StoryboardResponse } from "@/types";
import type { SceneDraftRequest } from "@/types/planning";

/** Flatten the storyboard's stage layout into position-ordered chapters. */
function orderedStoryboardChapters(storyboard: StoryboardResponse): ChapterInStoryboard[] {
  return storyboard.stages
    .flatMap((stage) => stage.chapters)
    .sort((a, b) => a.position - b.position);
}

/** One compact free-form neighbor line; null (omitted) without a summary. */
function neighborLine(prefix: string, chapter: Chapter | undefined): string | null {
  if (!chapter?.summary) return null;
  return `${prefix} "${chapter.title}": ${chapter.summary}`;
}

/** Context ids around `chapterId` within the position-ordered storyboard. */
function neighborIds(ordered: ChapterInStoryboard[], chapterId: string | null) {
  const index = chapterId ? ordered.findIndex((c) => c.chapter_id === chapterId) : -1;
  const prev = index > 0 ? ordered[index - 1]!.chapter_id : null;
  const next = index >= 0 && index + 1 < ordered.length ? ordered[index + 1]!.chapter_id : null;
  return { prev, next };
}

/**
 * Chapter context for the AI draft — spreads ONLY fields that actually
 * resolved, so an empty-context run produces today's `{}` body rather than
 * shipping empty strings (RULE-17: no invented values).
 */
export function useSceneDraftContext(novelId: string, chapterId: string | null): SceneDraftRequest {
  const { data: storyboard } = useStoryboard(novelId);

  const ordered = useMemo(
    () => (storyboard ? orderedStoryboardChapters(storyboard) : []),
    [storyboard],
  );
  const { prev, next } = neighborIds(ordered, chapterId);

  // Outline aggregate — key from usePlanning's shared factory, so
  // useUpdateOutline invalidations refresh this query too.
  const { data: outline } = useQuery({
    queryKey: planningKeys.outline(novelId, chapterId ?? ""),
    queryFn: () => getOutline(novelId, chapterId!),
    enabled: !!novelId && !!chapterId,
  });

  const { data: chapter } = useQuery({
    queryKey: ["novels", novelId, "chapters", chapterId],
    queryFn: () => chaptersApi.get(novelId, chapterId!),
    enabled: !!novelId && !!chapterId,
  });

  const { data: prevChapter } = useQuery({
    queryKey: ["novels", novelId, "chapters", prev],
    queryFn: () => chaptersApi.get(novelId, prev!),
    enabled: !!novelId && !!prev,
  });

  const { data: nextChapter } = useQuery({
    queryKey: ["novels", novelId, "chapters", next],
    queryFn: () => chaptersApi.get(novelId, next!),
    enabled: !!novelId && !!next,
  });

  return useMemo(() => {
    const neighbors = [
      neighborLine("Previous chapter", prevChapter),
      neighborLine("Next chapter", nextChapter),
    ]
      .filter((line): line is string => line !== null)
      .join("\n");
    return {
      ...(storyboard?.structure_type ? { structure_type: storyboard.structure_type } : {}),
      ...(outline?.outline_notes ? { outline_notes: outline.outline_notes } : {}),
      ...(chapter?.summary ? { chapter_summary: chapter.summary } : {}),
      ...(neighbors ? { neighbor_summaries: neighbors } : {}),
    };
  }, [storyboard, outline, chapter, prevChapter, nextChapter]);
}
