"use client";

/**
 * TanStack Query hooks for the planning/storyboard feature.
 *
 * Query keys follow the pattern ["planning", ...] for cache management.
 * All mutations invalidate related queries on success.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  confirmRemap,
  draftScenes,
  getOutline,
  getScenePlans,
  getStoryboard,
  previewRemap,
  refineScene,
  saveScenePlans,
  updateOutline,
} from "@/lib/api/planning";
import type { OutlineUpdateRequest } from "@/types";
import type { SceneDraftRequest, ScenePlanSaveRequest, SceneRefineRequest } from "@/types/planning";

// --- Query key factory ---

const planningKeys = {
  storyboard: (novelId: string) => ["planning", "storyboard", novelId] as const,
  sync: (novelId: string) => ["planning", "sync", novelId] as const,
  outline: (novelId: string, chapterId: string) =>
    ["planning", "outline", novelId, chapterId] as const,
  scenes: (novelId: string, chapterId: string) =>
    ["planning", "scenes", novelId, chapterId] as const,
};

// --- Query hooks ---

/** Fetch the full storyboard view for a novel. */
export function useStoryboard(novelId: string) {
  return useQuery({
    queryKey: planningKeys.storyboard(novelId),
    queryFn: () => getStoryboard(novelId),
    enabled: !!novelId,
  });
}

/** Fetch the outline for a specific chapter. */
export function useChapterOutline(novelId: string, chapterId: string | null) {
  return useQuery({
    queryKey: planningKeys.outline(novelId, chapterId ?? ""),
    queryFn: () => getOutline(novelId, chapterId!),
    enabled: !!novelId && !!chapterId,
  });
}

/** Fetch the scene plan aggregate for a chapter (empty aggregate is a valid state). */
export function useScenePlans(novelId: string, chapterId: string | null) {
  return useQuery({
    queryKey: planningKeys.scenes(novelId, chapterId ?? ""),
    queryFn: () => getScenePlans(novelId, chapterId!),
    enabled: !!novelId && !!chapterId,
  });
}

// --- Mutation hooks ---

/** Update a chapter's outline (stage assignment, beats, notes). */
export function useUpdateOutline(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ chapterId, data }: { chapterId: string; data: OutlineUpdateRequest }) =>
      updateOutline(novelId, chapterId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: planningKeys.storyboard(novelId),
      });
      void queryClient.invalidateQueries({
        queryKey: planningKeys.outline(novelId, variables.chapterId),
      });
    },
  });
}

/** Whole-aggregate scene save (diff-sync). Invalidates scenes + storyboard + sync. */
export function useSaveScenePlans(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ chapterId, data }: { chapterId: string; data: ScenePlanSaveRequest }) =>
      saveScenePlans(novelId, chapterId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: planningKeys.scenes(novelId, variables.chapterId),
      });
      void queryClient.invalidateQueries({
        queryKey: planningKeys.storyboard(novelId),
      });
      void queryClient.invalidateQueries({
        queryKey: planningKeys.sync(novelId),
      });
    },
  });
}

/** AI chapter draft — proposes scenes (zero DB writes; the client applies them). */
export function useDraftScenes(novelId: string) {
  return useMutation({
    mutationFn: ({ chapterId, body }: { chapterId: string; body: SceneDraftRequest }) =>
      draftScenes(novelId, chapterId, body),
  });
}

/** AI single-scene refine — returns a proposal (zero DB writes). */
export function useRefineScene(novelId: string) {
  return useMutation({
    mutationFn: ({ chapterId, body }: { chapterId: string; body: SceneRefineRequest }) =>
      refineScene(novelId, chapterId, body),
  });
}

/** Preview a structure remap (confirmed=false). */
export function usePreviewRemap(novelId: string, newStructure: string) {
  return useMutation({
    mutationFn: () => previewRemap(novelId, newStructure),
  });
}

/** Confirm a structure remap (confirmed=true). Invalidates storyboard on success. */
export function useConfirmRemap(novelId: string, newStructure: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => confirmRemap(novelId, newStructure),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: planningKeys.storyboard(novelId),
      });
      void queryClient.invalidateQueries({
        queryKey: ["novels", novelId],
      });
    },
  });
}
