"use client";

/**
 * useScratchpadSearch — the ScratchpadWorkspace semantic-search state block,
 * extracted for RULE-04 file-size headroom (zero behavior change; the
 * workspace tests pin the flows through the workspace as before).
 *
 * Owns ONE cohesive concern: semantic-search mode + results —
 * - the semantic toggle (leaving semantic mode invalidates results),
 * - the Enter-submitted explicit search (T21 guard: Enter on an empty
 *   query must not fire a request nor badge), and
 * - clearResults() — the shared invalidation path for any filter change,
 *   stale-scope auto-reset, editor save, or note delete.
 *
 * Colocated with its single consumer (ScratchpadWorkspace) like the other
 * scratchpad submodules (ScratchpadPaneMode, ScratchpadListRail, …).
 */

import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import { useSemanticNoteSearch } from "@/lib/hooks/useNotes";
import type { NoteSearchResponse, NoteTypeKey } from "@/types";
import type { NoteFilters } from "./NoteFilterBar";
import { scopeToParams } from "./NoteScopeSelect";

export interface UseScratchpadSearchReturn {
  readonly semanticMode: boolean;
  readonly searchResults: NoteSearchResponse | null;
  readonly handleSemanticModeChange: (enabled: boolean) => void;
  readonly submitSearch: () => void;
  /** Invalidate current search results (filter change, save, delete, …). */
  readonly clearResults: () => void;
}

export function useScratchpadSearch(filters: NoteFilters): UseScratchpadSearchReturn {
  const tCommon = useTranslations("common");
  const [semanticMode, setSemanticMode] = useState(false);
  const [searchResults, setSearchResults] = useState<NoteSearchResponse | null>(null);
  const search = useSemanticNoteSearch();

  // Stable identity: consumed by the workspace's stale-scope effect.
  const clearResults = useCallback(() => setSearchResults(null), []);

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
        ...scopeToParams(filters.scope),
      },
      {
        onSuccess: setSearchResults,
        onError: () => toast.error(tCommon("error")),
      },
    );
  }

  return { semanticMode, searchResults, handleSemanticModeChange, submitSearch, clearResults };
}
