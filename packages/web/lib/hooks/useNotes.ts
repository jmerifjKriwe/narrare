"use client";

/**
 * TanStack Query hooks for scratchpad notes (NOTES-001 §7).
 *
 * - useNotes / useNote / useNoteTags — reads (disabled while ids are empty).
 * - useCreateNote / useUpdateNote / useDeleteNote — mutations invalidating
 *   the notes + tags queries.
 * - useSemanticNoteSearch — explicit-trigger search (mutation semantics),
 *   returns the honest lexical/semantic mode badge.
 *
 * Mirrors the established Narrare pattern (useBandSummary): reads use
 * useQuery; mutations use useMutation + notesKeys.
 */

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notesApi } from "@/lib/api/notes";
import type { NoteCreate, NoteListParams, NoteSearchRequest, NoteUpdate } from "@/types";
import { notesKeys } from "./notesKeys";

/** GET /notes — filtered list. */
export function useNotes(params?: NoteListParams) {
  return useQuery({
    queryKey: notesKeys.list(params),
    queryFn: () => notesApi.list(params),
    // TanStack v5 pattern: keep the previous list visible while a changed
    // key refetches — no loading-pulse flash on every keystroke/filter change.
    placeholderData: keepPreviousData,
  });
}

/** GET /notes/{id} — disabled while id is empty. */
export function useNote(noteId: string) {
  return useQuery({
    queryKey: notesKeys.detail(noteId),
    queryFn: () => notesApi.get(noteId),
    enabled: !!noteId,
  });
}

/** GET /notes/tags — autocomplete source. */
export function useNoteTags(q?: string) {
  return useQuery({
    queryKey: notesKeys.tags(q),
    queryFn: () => notesApi.tags(q),
  });
}

/** POST /notes — used by the editor and quick capture. */
export function useCreateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: NoteCreate) => notesApi.create(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notesKeys.all });
    },
  });
}

/** PATCH /notes/{id}. */
export function useUpdateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: NoteUpdate }) => notesApi.update(id, body),
    onSuccess: (note) => {
      void queryClient.invalidateQueries({ queryKey: notesKeys.detail(note.id) });
      void queryClient.invalidateQueries({ queryKey: notesKeys.all });
    },
  });
}

/** DELETE /notes/{id}. */
export function useDeleteNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notesApi.delete(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notesKeys.all });
    },
  });
}

/** POST /notes/search — explicit trigger; carries the mode badge. */
export function useSemanticNoteSearch() {
  return useMutation({
    mutationFn: (body: NoteSearchRequest) => notesApi.search(body),
  });
}
