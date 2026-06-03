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

export interface OutlineBeat {
  title: string;
  description: string;
  completed: boolean;
}

export interface OutlineResponse {
  id: string;
  chapter_id: string;
  stage_assignment: string;
  planned_beats: OutlineBeat[];
  outline_notes: string;
  created_at: string;
  updated_at: string;
}

export interface OutlineUpdateRequest {
  stage_assignment?: string;
  planned_beats?: OutlineBeat[];
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
