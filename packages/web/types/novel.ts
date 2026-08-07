// Novel, Chapter & Volume types

export interface Novel {
  id: string;
  /**
   * Series membership. `null` = standalone novel. Surfaced by the backend
   * `NovelResponse.series_id` (Spec 1, ADR-075; DB column from migration 0037).
   */
  series_id: string | null;
  title: string;
  author: string;
  genre: string;
  writing_language: string;
  tone: string;
  story_structure: string;
  logline: string;
  synopsis: string;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface NovelSummary {
  id: string;
  /**
   * Series membership, surfaced by the backend `NovelSummaryResponse.series_id`
   * (Spec 1, ADR-075). `null` = standalone novel. Used by the dashboard to tell
   * standalone novels from novels that belong to a series.
   */
  series_id: string | null;
  title: string;
  author: string;
  genre: string;
  writing_language: string;
  is_demo: boolean;
  updated_at: string;
}

export interface Chapter {
  id: string;
  novel_id: string;
  volume_id: string | null;
  title: string;
  content: string;
  summary: string;
  position: number;
  word_count: number;
  status: "draft" | "reviewed" | "final";
  pov_character_id: string;
  timeline_position: string;
  created_at: string;
  updated_at: string;
}

export interface ChapterSummary {
  id: string;
  novel_id: string;
  volume_id: string | null;
  title: string;
  position: number;
  word_count: number;
  status: "draft" | "reviewed" | "final";
  updated_at: string;
}

export interface Volume {
  id: string;
  novel_id: string;
  title: string;
  subtitle: string | null;
  description: string | null;
  word_count_target: number | null;
  is_default: boolean;
  position: number;
  created_at: string;
}

export interface VolumeStats {
  word_count: number;
  chapter_count: number;
  word_count_target: number | null;
  completion_percentage: number | null;
}

export interface CreateVolumeRequest {
  title: string;
  subtitle?: string | null;
  description?: string | null;
  word_count_target?: number | null;
}

export interface UpdateVolumeRequest {
  title?: string | null;
  subtitle?: string | null;
  description?: string | null;
  word_count_target?: number | null;
}
