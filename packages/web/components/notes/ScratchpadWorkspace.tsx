"use client";

/**
 * ScratchpadWorkspace — the /scratchpad page body (NOTES-001 §7).
 *
 * Orchestrator: owns filters, selection, and search state; composes the
 * ScratchpadListRail (header + filter bar + honest badge + list), the right
 * pane (editor for the selected note, first-capture card when no note
 * exists, quiet select prompt when notes exist but none is selected — no
 * false "empty" copy), and the NotesChatDrawer.
 *
 * Binding review constraints implemented here:
 * - T21: Enter-on-empty-search guard (no request, no badge) + availableTags
 *   deduped once before feeding the filter bar AND the editor.
 * - T21b: feeds novels/series/hasLinks into the filter bar and CLEARS a
 *   stale scope when its target vanishes from both lists (parent duty per
 *   NoteScopeSelect JSDoc).
 * - T23: the editor is keyed by note id, so background refetches (new note
 *   OBJECT, same id) never remount the pane or clobber the in-progress draft.
 *
 * Composition (RULE-04): the rail lives in ScratchpadListRail, the capture
 * card in ScratchpadEmptyState; list/editor/filter/drawer are the T21–T25
 * modules. This file owns state and data orchestration only.
 */

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useCreateNote, useNotes, useNoteTags, useSemanticNoteSearch } from "@/lib/hooks/useNotes";
import { useNovels } from "@/lib/hooks/useNovels";
import { useSeriesList } from "@/lib/hooks/useSeries";
import type { NoteListParams, NoteSearchResponse, NoteTypeKey } from "@/types";
import { NoteEditor } from "./NoteEditor";
import type { NoteFilters } from "./NoteFilterBar";
import { NotesChatDrawer } from "./NotesChatDrawer";
import { ScratchpadEmptyState } from "./ScratchpadEmptyState";
import { ScratchpadListRail } from "./ScratchpadListRail";

const INITIAL_FILTERS: NoteFilters = { q: "", note_type: "", tag: "", scope: null };

export function ScratchpadWorkspace() {
  const t = useTranslations("notes");
  const tCommon = useTranslations("common");
  const [filters, setFilters] = useState<NoteFilters>(INITIAL_FILTERS);
  const [semanticMode, setSemanticMode] = useState(false);
  const [searchResults, setSearchResults] = useState<NoteSearchResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chatNoteId, setChatNoteId] = useState<string | null>(null);

  // Stable params object per filter value (notesKeys.list hashes it into the
  // query key; a stable identity avoids needless observer churn).
  const listParams = useMemo<NoteListParams>(
    () => ({
      q: filters.q || undefined,
      note_type: (filters.note_type || undefined) as NoteTypeKey | undefined,
      tag: filters.tag || undefined,
      novel_id: filters.scope?.kind === "novel" ? filters.scope.id : undefined,
      series_id: filters.scope?.kind === "series" ? filters.scope.id : undefined,
    }),
    [filters],
  );
  const notesQuery = useNotes(listParams);
  const tagsQuery = useNoteTags();
  const novelsQuery = useNovels();
  const seriesQuery = useSeriesList();
  const createNote = useCreateNote();
  const search = useSemanticNoteSearch();

  const notes = searchResults ? searchResults.results : (notesQuery.data ?? []);
  const selectedNote = notes.find((note) => note.id === selectedId) ?? null;
  const chatNote = notes.find((note) => note.id === chatNoteId) ?? null;
  const hasAnyNotes = (notesQuery.data?.length ?? 0) > 0;

  // T21: the tags endpoint returns distinct tags, but the editor's tag drafts
  // can drift — dedupe once so filter suggestions never show duplicates.
  const availableTags = useMemo(() => [...new Set(tagsQuery.data?.tags ?? [])], [tagsQuery.data]);

  const novelOptions = useMemo(
    () => (novelsQuery.data ?? []).map(({ id, title }) => ({ id, title })),
    [novelsQuery.data],
  );
  const seriesOptions = useMemo(
    () => (seriesQuery.data ?? []).map(({ id, title }) => ({ id, title })),
    [seriesQuery.data],
  );

  // T21b: hasLinks gate — the scope select renders only while at least one
  // displayed note is linked to a novel or series.
  const hasLinks = notes.some((note) => note.novel_id !== null || note.series_id !== null);

  // T21b parent duty: clear a scope whose target vanished from both lists.
  const scopeStale =
    filters.scope !== null &&
    !(
      (filters.scope.kind === "novel" && novelOptions.some((n) => n.id === filters.scope?.id)) ||
      (filters.scope.kind === "series" && seriesOptions.some((s) => s.id === filters.scope?.id))
    );
  useEffect(() => {
    if (scopeStale) setFilters((prev) => (prev.scope ? { ...prev, scope: null } : prev));
  }, [scopeStale]);

  function handleFiltersChange(next: NoteFilters) {
    setFilters(next);
    setSearchResults(null); // Any filter change invalidates search results.
  }

  function handleSemanticModeChange(enabled: boolean) {
    setSemanticMode(enabled);
    if (!enabled) setSearchResults(null);
  }

  function submitSearch() {
    // T21 guard: Enter on an empty query must not fire a search request.
    if (!semanticMode || !filters.q.trim()) {
      setSearchResults(null);
      return;
    }
    search.mutate(
      {
        query: filters.q.trim(),
        note_type: (filters.note_type || undefined) as NoteTypeKey | undefined,
        tag: filters.tag || undefined,
        novel_id: filters.scope?.kind === "novel" ? filters.scope.id : undefined,
        series_id: filters.scope?.kind === "series" ? filters.scope.id : undefined,
      },
      {
        onSuccess: setSearchResults,
        onError: () => toast.error(tCommon("error")),
      },
    );
  }

  function handleCapture(text: string, noteType: NoteTypeKey) {
    if (!text) return;
    createNote.mutate(
      { content: text, note_type: noteType },
      {
        onSuccess: (note) => setSelectedId(note.id),
        onError: () => toast.error(t("editor.saveFailed")),
      },
    );
  }

  return (
    <div className="flex h-full min-h-0">
      <ScratchpadListRail
        filters={filters}
        onFiltersChange={handleFiltersChange}
        availableTags={availableTags}
        novels={novelOptions}
        series={seriesOptions}
        hasLinks={hasLinks}
        semanticMode={semanticMode}
        onSemanticModeChange={handleSemanticModeChange}
        onSearchSubmit={submitSearch}
        searchMode={searchResults?.mode ?? null}
        notes={notes}
        selectedId={selectedId}
        onSelect={setSelectedId}
        listPending={notesQuery.isPending}
        listError={notesQuery.isError}
        onRetryList={() => void notesQuery.refetch()}
      />

      <div className="min-w-0 flex-1">
        {selectedNote ? (
          <NoteEditor
            key={selectedNote.id}
            note={selectedNote}
            availableTags={availableTags}
            onSaved={() => setSearchResults(null)}
            onDeleted={() => {
              setSelectedId(null);
              setSearchResults(null);
            }}
            onDiscuss={(noteId) => setChatNoteId(noteId)}
          />
        ) : hasAnyNotes ? (
          <p
            data-testid="scratchpad-select-prompt"
            className="flex h-full items-center justify-center p-6 text-sm italic text-muted-foreground"
          >
            {t("empty.selectPrompt")}
          </p>
        ) : (
          <ScratchpadEmptyState onCapture={handleCapture} pending={createNote.isPending} />
        )}
      </div>

      <NotesChatDrawer
        open={chatNoteId !== null}
        onClose={() => setChatNoteId(null)}
        note={chatNote}
      />
    </div>
  );
}
