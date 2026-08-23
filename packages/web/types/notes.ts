/**
 * Scratchpad note types (NOTES-001).
 *
 * Mirrors apps/api/narrare/notes/schemas.py. `title` is the stored
 * (possibly null) title — use `noteDisplayTitle` for display (spec §4:
 * empty title → first content line).
 */

export type NoteTypeKey = "idea" | "concept" | "question" | "other";

export const NOTE_TYPE_KEYS: readonly NoteTypeKey[] = [
  "idea",
  "concept",
  "question",
  "other",
] as const;

export interface Note {
  readonly id: string;
  readonly title: string | null;
  readonly content: string;
  readonly note_type: NoteTypeKey;
  readonly tags: readonly string[];
  readonly novel_id: string | null;
  readonly series_id: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface NoteCreate {
  title?: string | null;
  content: string;
  note_type?: NoteTypeKey;
  tags?: string[];
  novel_id?: string | null;
  series_id?: string | null;
}

export type NoteUpdate = Partial<NoteCreate>;

export interface NoteListParams {
  note_type?: NoteTypeKey;
  tag?: string;
  novel_id?: string;
  series_id?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface NoteTagsResponse {
  readonly tags: string[];
}

export type NoteSearchMode = "lexical" | "semantic";

export interface NoteSearchHit extends Note {
  readonly similarity: number | null;
}

export interface NoteSearchRequest {
  query: string;
  note_type?: NoteTypeKey;
  tag?: string;
  novel_id?: string;
  series_id?: string;
  limit?: number;
}

export interface NoteSearchResponse {
  readonly mode: NoteSearchMode;
  readonly query: string;
  readonly results: NoteSearchHit[];
}

/** Display title: the stored title, or the first non-empty content line. */
export function noteDisplayTitle(note: Pick<Note, "title" | "content">): string {
  if (note.title?.trim()) return note.title;
  const firstLine = note.content.split("\n").find((line) => line.trim());
  return firstLine ? firstLine.trim().slice(0, 200) : "";
}
