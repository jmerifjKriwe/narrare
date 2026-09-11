/**
 * Notes API client (NOTES-001).
 *
 * Typed wrappers around apps/api/narrare/notes/router.py: CRUD, filters,
 * tag autocomplete, semantic search with lexical fallback. Every call goes
 * through `fetchApi` from ./core (auth-token injection, 401 auto-refresh,
 * `/api/v1` prefixing, unified error parsing).
 */

import type {
  Note,
  NoteCreate,
  NoteListParams,
  NoteSearchRequest,
  NoteSearchResponse,
  NoteTagsResponse,
  NoteUpdate,
} from "@/types";
import { fetchApi } from "./core";

function toQuery(params: NoteListParams | undefined): string {
  if (!params) return "";
  const search = new URLSearchParams();
  if (params.note_type) search.set("note_type", params.note_type);
  if (params.tag) search.set("tag", params.tag);
  if (params.novel_id) search.set("novel_id", params.novel_id);
  if (params.series_id) search.set("series_id", params.series_id);
  if (params.q) search.set("q", params.q);
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const notesApi = {
  /** GET /notes — filtered list, updated_at DESC. */
  list: (params?: NoteListParams) => fetchApi<Note[]>(`/notes${toQuery(params)}`),

  /** GET /notes/{id} */
  get: (noteId: string) => fetchApi<Note>(`/notes/${noteId}`),

  /** POST /notes — used by quick capture AND the full editor. */
  create: (body: NoteCreate) =>
    fetchApi<Note>("/notes", { method: "POST", body: JSON.stringify(body) }),

  /** PATCH /notes/{id} — explicit null clears a field. */
  update: (noteId: string, body: NoteUpdate) =>
    fetchApi<Note>(`/notes/${noteId}`, { method: "PATCH", body: JSON.stringify(body) }),

  /** DELETE /notes/{id} */
  delete: (noteId: string) => fetchApi<void>(`/notes/${noteId}`, { method: "DELETE" }),

  /** GET /notes/tags — distinct existing tags, optional prefix. */
  tags: (q?: string) =>
    fetchApi<NoteTagsResponse>(`/notes/tags${q ? `?q=${encodeURIComponent(q)}` : ""}`),

  /** POST /notes/search — semantic with honest lexical fallback. */
  search: (body: NoteSearchRequest) =>
    fetchApi<NoteSearchResponse>("/notes/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
