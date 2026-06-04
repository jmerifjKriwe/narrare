"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { KBRelationship, KBRelationshipCreateRequest } from "@/lib/api/kb";
import { kbApi } from "@/lib/api/kb";
import { kbKeys } from "@/lib/hooks/kbKeys";

/** Fetch relationships for a given KB entry. Pass null to disable. */
export function useKBRelationships(novelId: string, entryId: string | null) {
  return useQuery<KBRelationship[]>({
    queryKey: kbKeys.relationships(novelId, entryId ?? ""),
    queryFn: () => (entryId ? kbApi.listRelationships(novelId, entryId) : Promise.resolve([])),
    enabled: !!novelId && !!entryId,
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
