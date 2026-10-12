"use client";

/** TanStack Query hooks for KB entries and templates. */

import { type UseQueryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type KBEntityType,
  type KBEntry,
  type KBEntryCreateRequest,
  type KBEntryListParams,
  type KBEntryListResponse,
  type KBEntryUpdateRequest,
  type KBSearchParams,
  type KBTemplate,
  type KBTemplateInfo,
  kbApi,
} from "@/lib/api/kb";

export { kbKeys } from "@/lib/hooks/kbKeys";

import { kbKeys } from "@/lib/hooks/kbKeys";

export {
  useCreateKBRelationship,
  useDeleteKBRelationship,
  useKBRelationships,
} from "./useKBRelationships";
export {
  useKBDebouncedSearch,
  useKBInverseSuggestion,
  useKBResolveReferences,
} from "./useKBSearch";

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

/** Fetch template for a given entity type. Pass null to disable. */
export function useKBTemplate(novelId: string, entityType: string | null) {
  return useQuery<KBTemplate | null>({
    queryKey: kbKeys.template(novelId, entityType ?? ""),
    queryFn: () => (entityType ? kbApi.getTemplate(novelId, entityType) : Promise.resolve(null)),
    enabled: !!novelId && !!entityType,
  });
}

/** Fetch all available templates for a novel. */
export function useKBTemplates(novelId: string) {
  return useQuery<KBTemplateInfo[]>({
    queryKey: kbKeys.templates(novelId),
    queryFn: () => kbApi.listTemplates(novelId),
    enabled: !!novelId,
  });
}

/** Create a new KB entry. Invalidates the entries list on success. */
export function useCreateKBEntry(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: KBEntryCreateRequest) => kbApi.createEntry(novelId, data),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: kbKeys.entries(novelId) }),
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
      void queryClient.invalidateQueries({ queryKey: kbKeys.entry(novelId, variables.entryId) });
    },
  });
}

/** Delete a KB entry. Invalidates the entries list on success. */
export function useDeleteKBEntry(novelId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) => kbApi.deleteEntry(novelId, entryId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: kbKeys.entries(novelId) }),
  });
}

/** Fetch total entry count for a given entity type. Returns 0 if no entries. */
export function useKBEntryCount(novelId: string, entityType?: KBEntityType) {
  const { data } = useKBEntries(novelId, { entity_type: entityType, page_size: 1 });
  return data?.total ?? 0;
}

/** Fetch total entry count for a novel (all types). Useful for sidebar badge. */
export function useKBTotalCount(novelId: string) {
  const { data } = useKBEntries(novelId, { page_size: 1 });
  return data?.total ?? 0;
}
