"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import {
  type KBEntryListResponse,
  type KBInverseSuggestion,
  kbApi,
  type ResolveReferencesResponse,
} from "@/lib/api/kb";
import { kbKeys } from "@/lib/hooks/kbKeys";

/** Debounced search — waits for a pause in typing before querying. */
export function useKBDebouncedSearch(novelId: string, delay = 300) {
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  const setQuery = useCallback(
    (q: string) => {
      setSearchQuery(q);
      // Immediate clear if empty
      if (q.length === 0) {
        setDebouncedQuery("");
        return;
      }
      const timer = setTimeout(() => setDebouncedQuery(q), delay);
      return () => clearTimeout(timer);
    },
    [delay],
  );

  const searchResult = useQuery<KBEntryListResponse>({
    queryKey: kbKeys.search(novelId, { q: debouncedQuery }),
    queryFn: () => kbApi.searchEntries(novelId, { q: debouncedQuery }),
    enabled: !!novelId && debouncedQuery.length > 0,
  });

  return {
    searchQuery,
    setQuery,
    ...searchResult,
  };
}

/** Get the inverse relationship suggestion for a given rel_type. */
export function useKBInverseSuggestion(novelId: string, relType: string | null) {
  return useQuery<KBInverseSuggestion>({
    queryKey: kbKeys.inverseSuggestion(novelId, relType ?? ""),
    queryFn: () =>
      relType
        ? kbApi.getInverseSuggestion(novelId, relType)
        : Promise.resolve({ rel_type: "", inverse_rel_type: "", description: "" }),
    enabled: !!novelId && !!relType,
  });
}

/** Resolve @Name mentions in a text to KB entry references. Pass null to disable. */
export function useKBResolveReferences(novelId: string, text: string | null) {
  return useQuery<ResolveReferencesResponse | null>({
    queryKey: kbKeys.references(novelId, text ?? ""),
    queryFn: () => (text ? kbApi.resolveReferences(novelId, text) : Promise.resolve(null)),
    enabled: !!novelId && !!text && text.length > 0,
  });
}
