"use client";

/**
 * TanStack Query hooks for Series CRUD.
 *
 * Reads use `useQuery`; writes use `useMutation` and invalidate the relevant
 * Series query caches via `seriesKeys`. Standard Narrare pattern (see
 * `@/lib/hooks/useKB`). Components import these — never `seriesApi` directly.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import type { SeriesCreate, SeriesSettingsUpdate, SeriesUpdate } from "@/types";
import { seriesKeys } from "./seriesKeys";

/** GET /api/v1/series — list of all Series for the current user. */
export function useSeriesList() {
  return useQuery({
    queryKey: seriesKeys.all,
    queryFn: () => seriesApi.list(),
  });
}

/** GET /api/v1/series/{id} — single Series detail. Disabled when id is empty. */
export function useSeries(seriesId: string) {
  return useQuery({
    queryKey: seriesKeys.detail(seriesId),
    queryFn: () => seriesApi.get(seriesId),
    enabled: !!seriesId,
  });
}

/** POST /api/v1/series — create a Series, then invalidate the list. */
export function useCreateSeries() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SeriesCreate) => seriesApi.create(body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: seriesKeys.all }),
  });
}

/** PATCH /api/v1/series/{id} — update a Series, then invalidate detail + list. */
export function useUpdateSeries(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SeriesUpdate) => seriesApi.update(seriesId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.detail(seriesId) });
      void queryClient.invalidateQueries({ queryKey: seriesKeys.all });
    },
  });
}

/** DELETE /api/v1/series/{id} — delete a Series, then invalidate the list. */
export function useDeleteSeries() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (seriesId: string) => seriesApi.delete(seriesId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: seriesKeys.all }),
  });
}

// --- Series settings (Spec 2: context_window_size) ---
//
// Separate from the metadata CRUD hooks above: settings live on a distinct
// endpoint (GET/PATCH /series/{id}/settings) and are persisted independently
// of the main Series PATCH. The query key is scoped under the series detail
// so a settings update invalidates the same per-series cache neighbourhood.

/** GET /api/v1/series/{id}/settings — current SeriesSettings. */
export function useSeriesSettings(seriesId: string) {
  return useQuery({
    queryKey: seriesKeys.settings(seriesId),
    queryFn: () => seriesApi.getSettings(seriesId),
    enabled: !!seriesId,
  });
}

/** PATCH /api/v1/series/{id}/settings — patch settings, then invalidate. */
export function useUpdateSeriesSettings(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SeriesSettingsUpdate) => seriesApi.updateSettings(seriesId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.settings(seriesId) });
    },
  });
}
