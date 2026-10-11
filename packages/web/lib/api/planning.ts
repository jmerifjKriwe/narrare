/**
 * Planning / Storyboard API client.
 *
 * Typed wrappers around all planning endpoints.
 * Components never call fetch directly — always use these functions
 * via TanStack Query hooks from lib/hooks/usePlanning.ts.
 */

import type {
  OutlineResponse,
  OutlineUpdateRequest,
  RemapResponse,
  StoryboardResponse,
  SyncStatusResponse,
} from "@/types";
import type {
  SceneDraftRequest,
  SceneDraftResponse,
  ScenePlanAggregate,
  ScenePlanSaveRequest,
  SceneRefineRequest,
  SceneRefineResponse,
} from "@/types/planning";
import { fetchApi } from "./client";

// ---------------------------------------------------------------------------
// Storyboard
// ---------------------------------------------------------------------------

/** Fetch the storyboard view for a novel (all stages with chapters). */
export function getStoryboard(novelId: string): Promise<StoryboardResponse> {
  return fetchApi<StoryboardResponse>(`/planning/storyboard/${novelId}`);
}

/** Fetch sync status for all chapters in a novel. */
export function getSyncStatus(novelId: string): Promise<SyncStatusResponse[]> {
  return fetchApi<SyncStatusResponse[]>(`/planning/storyboard/${novelId}/sync`);
}

// ---------------------------------------------------------------------------
// Chapter Outlines
// ---------------------------------------------------------------------------

/** Fetch the outline for a specific chapter. */
export function getOutline(novelId: string, chapterId: string): Promise<OutlineResponse> {
  return fetchApi<OutlineResponse>(`/planning/outlines/${novelId}/${chapterId}`);
}

/** Update (or create) an outline for a specific chapter. */
export function updateOutline(
  novelId: string,
  chapterId: string,
  data: OutlineUpdateRequest,
): Promise<OutlineResponse> {
  return fetchApi<OutlineResponse>(`/planning/outlines/${novelId}/${chapterId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Structure Remap
// ---------------------------------------------------------------------------

/** Preview how chapters will be remapped under a new structure. */
export function previewRemap(novelId: string, newStructure: string): Promise<RemapResponse> {
  return fetchApi<RemapResponse>(`/planning/storyboard/${novelId}/remap`, {
    method: "POST",
    body: JSON.stringify({ new_structure: newStructure, confirm: false }),
  });
}

/** Confirm a structure remap — applies the changes server-side. */
export function confirmRemap(novelId: string, newStructure: string): Promise<RemapResponse> {
  return fetchApi<RemapResponse>(`/planning/storyboard/${novelId}/remap`, {
    method: "POST",
    body: JSON.stringify({ new_structure: newStructure, confirm: true }),
  });
}

// ---------------------------------------------------------------------------
// Scene Plans
// ---------------------------------------------------------------------------

/** Fetch the chapter's scene plan aggregate (scenes ordered by position). */
export function getScenePlans(novelId: string, chapterId: string): Promise<ScenePlanAggregate> {
  return fetchApi<ScenePlanAggregate>(`/planning/scenes/${novelId}/${chapterId}`);
}

/** Whole-aggregate save — the server diff-syncs by scene id and renumbers. */
export function saveScenePlans(
  novelId: string,
  chapterId: string,
  data: ScenePlanSaveRequest,
): Promise<ScenePlanAggregate> {
  return fetchApi<ScenePlanAggregate>(`/planning/scenes/${novelId}/${chapterId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/** AI chapter draft — propose scenes for the chapter (generator, zero DB writes). */
export function draftScenes(
  novelId: string,
  chapterId: string,
  body: SceneDraftRequest,
): Promise<SceneDraftResponse> {
  return fetchApi<SceneDraftResponse>(`/planning/scenes/${novelId}/${chapterId}/draft`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** AI single-scene refine — rewrite the carried scene (generator, zero DB writes). */
export function refineScene(
  novelId: string,
  chapterId: string,
  body: SceneRefineRequest,
): Promise<SceneRefineResponse> {
  return fetchApi<SceneRefineResponse>(`/planning/scenes/${novelId}/${chapterId}/refine`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
