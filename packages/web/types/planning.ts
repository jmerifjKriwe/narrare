// Planning / Storyboard types

export type SyncStatus = "empty" | "planned" | "on_track" | "deviated" | "completed";

export interface ChapterInStoryboard {
  chapter_id: string;
  title: string;
  word_count: number;
  sync_status: SyncStatus;
  position: number;
}

export interface StoryboardStageResponse {
  stage_id: string;
  stage_name: string;
  chapters: ChapterInStoryboard[];
}

export interface StoryboardResponse {
  structure_type: string;
  stages: StoryboardStageResponse[];
}

export interface SyncStatusResponse {
  chapter_id: string;
  status: SyncStatus;
}

export interface OutlineResponse {
  id: string;
  chapter_id: string;
  stage_assignment: string;
  outline_notes: string;
  created_at: string;
  updated_at: string;
}

export interface OutlineUpdateRequest {
  stage_assignment?: string;
  outline_notes?: string;
}

export interface RemapPreviewItem {
  chapter_id: string;
  chapter_title: string;
  old_stage: string;
  new_stage: string;
  ai_confidence?: number;
  ai_suggested_stage?: string;
}

export interface RemapResponse {
  new_structure: string;
  remapped: RemapPreviewItem[];
  ai_confidence?: number;
  confirmed: boolean;
}

// ---------------------------------------------------------------------------
// Scene Plans (PLAN-001) — mirrors planning/schemas_scenes.py field-exactly
// ---------------------------------------------------------------------------

export type SceneStatus = "planned" | "in_progress" | "complete";

/** Hybrid KB ref (AD-1 pattern) — id null = name-only ref (entry dead/unknown). */
export interface SceneRef {
  id: string | null;
  name: string;
}

export interface ScenePresence {
  id: string | null;
  name: string;
  goal: string;
}

export interface ScenePlan {
  id: string;
  position: number;
  title: string;
  pov_character_ref: SceneRef | null;
  location_ref: SceneRef | null;
  present_characters: ScenePresence[];
  purpose: string;
  conflict: string;
  resolution: string;
  beats: string[];
  status: SceneStatus;
  created_at: string;
  updated_at: string;
}

/** Whole-chapter aggregate — scenes ordered by position. */
export interface ScenePlanAggregate {
  chapter_id: string;
  scenes: ScenePlan[];
  version_updated_at: string;
}

/** Whole-aggregate save payload — diff-synced server-side by scene id. */
export interface ScenePlanSaveRequest {
  scenes: ScenePlan[];
}

/** AI scene proposal — ScenePlan minus identity/status/timestamps. */
export interface SceneProposal {
  title: string;
  pov_character_ref: SceneRef | null;
  location_ref: SceneRef | null;
  present_characters: ScenePresence[];
  purpose: string;
  conflict: string;
  resolution: string;
  beats: string[];
}

/** Chapter-level AI draft request (all fields optional — server defaults). */
export interface SceneDraftRequest {
  structure_type?: string;
  outline_notes?: string;
  chapter_summary?: string;
  neighbor_summaries?: string;
  instruction?: string;
  /** 0 = model chooses; 3–8 is prompt-level guidance, not a validated server constraint. */
  scene_count?: number;
}

export interface SceneDraftResponse {
  proposals: SceneProposal[];
  ai_unavailable: boolean;
}

/** Single-scene AI refine — full scene carried so unsaved drafts are refinable. */
export interface SceneRefineRequest {
  scene: ScenePlan;
  prev_scene_summary?: string;
  next_scene_summary?: string;
  chapter_summary?: string;
  instruction?: string;
}

export interface SceneRefineResponse {
  proposal: SceneProposal | null;
  ai_unavailable: boolean;
}
