// Project Import types — RULE-17 mirror of apps/api/narrare/importing/schemas.py.
// ImportSelection is frontend-only (File objects never cross the wire via JSON).

export interface ImportPreviewItem {
  index: number;
  suggested_title: string;
  word_count: number;
  source_file: string;
}

export interface ImportPreviewResponse {
  items: ImportPreviewItem[];
  file_count: number;
  chapter_count: number;
  total_word_count: number;
}

export interface ImportCommitAdjustments {
  excluded_indices: number[];
  title_overrides: Record<string, string>;
}

export interface ImportCommitChapterInfo {
  id: string;
  title: string;
  position: number;
  word_count: number;
}

export interface ImportCommitResponse {
  novel_id: string;
  created_count: number;
  first_position: number;
  last_position: number;
  chapters: ImportCommitChapterInfo[];
}

/** Current pick state of the shared import panel (frontend-only). */
export interface ImportSelection {
  files: File[];
  excludedIndices: number[];
  titleOverrides: Record<string, string>;
  includedCount: number;
}
