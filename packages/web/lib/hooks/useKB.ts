"use client";

/**
 * TanStack Query hooks for KB entries and relationships.
 *
 * All hooks accept novelId as the primary key parameter.
 * Query keys follow the pattern ["kb", novelId, ...] for cache management.
 */

import { type UseQueryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import {
  type KBEntityType,
  type KBEntry,
  type KBEntryCreateRequest,
  type KBEntryListParams,
  type KBEntryListResponse,
  type KBEntryUpdateRequest,
  type KBInverseSuggestion,
  type KBRelationship,
  type KBRelationshipCreateRequest,
  type KBSearchParams,
  kbApi,
} from "@/lib/api/kb";

// --- Query key factory ---

const kbKeys = {
  all: (novelId: string) => ["kb", novelId] as const,
  entries: (novelId: string) => [...kbKeys.all(novelId), "entries"] as const,
  entriesList: (novelId: string, params?: KBEntryListParams) =>
    [...kbKeys.entries(novelId), params] as const,
  entry: (novelId: string, entryId: string) => [...kbKeys.entries(novelId), entryId] as const,
  search: (novelId: string, params: KBSearchParams) =>
    [...kbKeys.all(novelId), "search", params] as const,
  relationships: (novelId: string, entryId: string) =>
    [...kbKeys.all(novelId), "relationships", entryId] as const,
  inverseSuggestion: (novelId: string, relType: string) =>
    [...kbKeys.all(novelId), "inverse", relType] as const,
};

// --- Entry hooks ---

/** Fetch paginated KB entries, optionally filtered by entity type. */
export function useKBEntries(
  novelId: string,
  params?: KBEntryListParams,
  options?: Partial<UseQueryOptions<KBEntryListResponse>>,
) {
  return useQuery<KBEntryListResponse>({
    queryKey: kbKeys.entriesList(novelId, params),
    queryFn: () => kbApi.listEntries(novelId, params),
    enabled: !!novelId,
    ...options,
  });
}

/** Fetch a single KB entry by ID. Pass null to disable. */
export function useKBEntry(novelId: string, entryId: string | null) {
  return useQuery<KBEntry | null>({
    queryKey: kbKeys.entry(novelId, entryId ?? ""),
    queryFn: () => (entryId ? kbApi.getEntry(novelId, entryId) : Promise.resolve(null)),
    enabled: !!novelId && !!entryId,
    placeholderData: (previousData) => previousData,
  });
}

/** Search KB entries by query string. */
export function useKBSearch(novelId: string, query: string, params?: Partial<KBSearchParams>) {
  return useQuery<KBEntryListResponse>({
    queryKey: kbKeys.search(novelId, { q: query, ...params }),
    queryFn: () => kbApi.searchEntries(novelId, { q: query, ...params }),
    enabled: !!novelId && query.length > 0,
  });
}

// --- Relationship hooks ---

/** Fetch relationships for a given entry. Pass null to disable. */
export function useKBRelationships(novelId: string, entryId: string | null) {
  return useQuery<KBRelationship[]>({
    queryKey: kbKeys.relationships(novelId, entryId ?? ""),
    queryFn: () => (entryId ? kbApi.listRelationships(novelId, entryId) : Promise.resolve([])),
    enabled: !!novelId && !!entryId,
  });
}

// --- Mutation hooks ---

/** Create a new KB entry. Invalidates the entries list on success. */
export function useCreateKBEntry(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: KBEntryCreateRequest) => kbApi.createEntry(novelId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: kbKeys.entries(novelId) });
    },
  });
}

/** Update an existing KB entry. Invalidates both list and single entry caches. */
export function useUpdateKBEntry(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ entryId, data }: { entryId: string; data: KBEntryUpdateRequest }) =>
      kbApi.updateEntry(novelId, entryId, data),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: kbKeys.entries(novelId) });
      void queryClient.invalidateQueries({
        queryKey: kbKeys.entry(novelId, variables.entryId),
      });
    },
  });
}

/** Delete a KB entry. Invalidates the entries list on success. */
export function useDeleteKBEntry(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) => kbApi.deleteEntry(novelId, entryId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: kbKeys.entries(novelId) });
    },
  });
}

/** Create a relationship between two KB entries. */
export function useCreateKBRelationship(novelId: string, entryId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: KBRelationshipCreateRequest) => kbApi.createRelationship(novelId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: kbKeys.relationships(novelId, entryId),
      });
    },
  });
}

/** Delete a relationship. */
export function useDeleteKBRelationship(novelId: string, entryId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (relId: string) => kbApi.deleteRelationship(novelId, relId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: kbKeys.relationships(novelId, entryId),
      });
    },
  });
}

// --- Debounced search hook ---

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

  const searchResult = useKBSearch(novelId, debouncedQuery);

  return {
    searchQuery,
    setQuery,
    ...searchResult,
  };
}

// --- Inverse suggestion ---

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

// --- Convenience: entry count per entity type ---

/** Fetch total entry count for a given entity type. Returns 0 if no entries. */
export function useKBEntryCount(novelId: string, entityType?: KBEntityType) {
  const { data } = useKBEntries(novelId, {
    entity_type: entityType,
    page_size: 1,
  });
  return data?.total ?? 0;
}

/** Fetch total entry count for a novel (all types). Useful for sidebar badge. */
export function useKBTotalCount(novelId: string) {
  const { data } = useKBEntries(novelId, { page_size: 1 });
  return data?.total ?? 0;
}
