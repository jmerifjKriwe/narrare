"use client";

/**
 * TanStack Query hooks for the Series Voice Hierarchy (Spec 3 Tasks 5–6).
 *
 * Four hooks back the series-voice lifecycle for one series:
 *
 * - ``useSeriesVoice``                  — GET (read; disabled while loading).
 * - ``useProfileSeriesVoice``           — POST profile a band (novel) → series voice.
 * - ``useUpdateSeriesVoiceOverride``    — PATCH set a manual voice-profile override.
 * - ``useClearSeriesVoiceOverride``     — DELETE clear the override (null the column).
 *
 * The three mutations invalidate the per-series voice query on success so the
 * panel re-fetches immediately. Mirrors the established Narrare pattern
 * (``useBandSummary`` / ``useSeriesNovels``): reads use ``useQuery`` (disabled
 * when ``seriesId`` is empty); mutations use ``useMutation`` + ``seriesKeys``.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";
import type { SeriesVoiceOverrideRequest } from "@/types";
import { seriesKeys } from "./seriesKeys";

/**
 * GET /api/v1/series/{id}/voice.
 * Disabled when `seriesId` is empty.
 */
export function useSeriesVoice(seriesId: string) {
  return useQuery({
    queryKey: seriesKeys.voice(seriesId),
    queryFn: () => seriesApi.getVoice(seriesId),
    enabled: !!seriesId,
  });
}

/** POST /api/v1/series/{id}/voice/profile — profile a novel's voice. Call `.mutate(novelId)`. */
export function useProfileSeriesVoice(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.profileVoice(seriesId, novelId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.voice(seriesId) });
    },
  });
}

/** PATCH /api/v1/series/{id}/voice — set a manual override. Call `.mutate(voice)`. */
export function useUpdateSeriesVoiceOverride(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (voice: SeriesVoiceOverrideRequest) =>
      seriesApi.updateVoiceOverride(seriesId, voice),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.voice(seriesId) });
    },
  });
}

/** DELETE /api/v1/series/{id}/voice/override — clear the series voice. */
export function useClearSeriesVoiceOverride(seriesId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => seriesApi.clearVoiceOverride(seriesId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: seriesKeys.voice(seriesId) });
    },
  });
}
