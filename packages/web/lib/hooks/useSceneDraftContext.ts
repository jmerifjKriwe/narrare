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
 * - `chapter_summary` / `neighbor_summaries`: the summary-only plan-context
 *   endpoint (`chaptersApi.getPlanContext`) — ONE light request replacing the
 *   former up-to-three full-chapter GETs (whose payloads carried `content`).
 *   Neighbors are position-adjacent within the novel, resolved server-side.
 *
 * `instruction` is intentionally NOT sourced — no UI collects one yet; the
 * server default ("") applies.
 *
 * The outline key comes from `usePlanning`'s exported `planningKeys` factory;
 * plan-context uses its own `["novels", novelId, "chapters", chapterId,
 * "plan-context"]` family, nested below the shared chapter-detail key so
 * chapter-scoped invalidations stay coherent. Freshness is the TanStack
 * default (mount refetch), like the queries it replaces — no extra
 * invalidation wiring.
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { chaptersApi } from "@/lib/api/client";
import { getOutline } from "@/lib/api/planning";
import { planningKeys, useStoryboard } from "@/lib/hooks/usePlanning";
import type { ChapterPlanContextChapter, SceneDraftRequest } from "@/types/planning";

/** One compact free-form neighbor line; null (omitted) without a summary. */
function neighborLine(prefix: string, chapter: ChapterPlanContextChapter | null): string | null {
  if (!chapter?.summary) return null;
  return `${prefix} "${chapter.title}": ${chapter.summary}`;
}

/**
 * Chapter context for the AI draft — spreads ONLY fields that actually
 * resolved, so an empty-context run produces today's `{}` body rather than
 * shipping empty strings (RULE-17: no invented values).
 */
export function useSceneDraftContext(novelId: string, chapterId: string | null): SceneDraftRequest {
  const { data: storyboard } = useStoryboard(novelId);

  // Outline aggregate — key from usePlanning's shared factory, so
  // useUpdateOutline invalidations refresh this query too.
  const { data: outline } = useQuery({
    queryKey: planningKeys.outline(novelId, chapterId ?? ""),
    queryFn: () => getOutline(novelId, chapterId!),
    enabled: !!novelId && !!chapterId,
  });

  // ONE summary-only plan-context fetch replaces the former three
  // full-chapter GETs (current + prev + next) — no `content` on the wire.
  const { data: planContext } = useQuery({
    queryKey: ["novels", novelId, "chapters", chapterId ?? "", "plan-context"],
    queryFn: () => chaptersApi.getPlanContext(novelId, chapterId!),
    enabled: !!novelId && !!chapterId,
  });

  return useMemo(() => {
    const neighbors = [
      neighborLine("Previous chapter", planContext?.previous ?? null),
      neighborLine("Next chapter", planContext?.next ?? null),
    ]
      .filter((line): line is string => line !== null)
      .join("\n");
    return {
      ...(storyboard?.structure_type ? { structure_type: storyboard.structure_type } : {}),
      ...(outline?.outline_notes ? { outline_notes: outline.outline_notes } : {}),
      ...(planContext?.chapter.summary ? { chapter_summary: planContext.chapter.summary } : {}),
      ...(neighbors ? { neighbor_summaries: neighbors } : {}),
    };
  }, [storyboard, outline, planContext]);
}
