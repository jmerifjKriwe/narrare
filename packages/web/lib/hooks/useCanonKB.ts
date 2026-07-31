"use client";

/**
 * TanStack Query hooks for Series-Canon KB CRUD.
 *
 * Series Foundation Spec 1, Slice 5 (Task 5.2). Mirrors the novel-scoped
 * ``useKB`` hooks (lib/hooks/useKB.ts) but targets /series/{seriesId}/kb.
 *
 * Reads use ``useQuery`` (disabled when ``seriesId`` is empty); mutations use
 * ``useMutation`` and invalidate the Series-Canon query caches via
 * ``seriesKeys``. Components import these — never ``seriesApi`` directly.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import type { CanonEntryCreate, CanonEntryUpdate } from "@/types";
import { seriesKeys } from "./seriesKeys";

/**
 * GET /api/v1/series/{id}/kb — all Series-Canon entries for a series.
 * Disabled when ``seriesId`` is empty.
 */
export function useCanonKB(seriesId: string) {
  return useQuery({
    queryKey: seriesKeys.canonList(seriesId),
    queryFn: () => seriesApi.listCanonKB(seriesId),
    enabled: !!seriesId,
  });
}

/** POST /api/v1/series/{id}/kb — create a Series-Canon entry, then invalidate the list. */
export function useCreateCanonEntry(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CanonEntryCreate) => seriesApi.createCanonEntry(seriesId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.canonList(seriesId) });
    },
  });
}

/**
 * PATCH /api/v1/series/{id}/kb/{entryId} — update a Series-Canon entry.
 * Invalidates both the canon list and the single-entry detail cache.
 */
export function useUpdateCanonEntry(seriesId: string, entryId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CanonEntryUpdate) => seriesApi.updateCanonEntry(seriesId, entryId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.canonList(seriesId) });
      void queryClient.invalidateQueries({ queryKey: seriesKeys.canonDetail(seriesId, entryId) });
    },
  });
}

/** DELETE /api/v1/series/{id}/kb/{entryId} — delete a Series-Canon entry, then invalidate the list. */
export function useDeleteCanonEntry(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) => seriesApi.deleteCanonEntry(seriesId, entryId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.canonList(seriesId) });
    },
  });
}
