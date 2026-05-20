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
