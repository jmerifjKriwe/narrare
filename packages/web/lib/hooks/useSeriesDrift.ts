"use client";

/**
 * TanStack Query hooks for the Series Cross-Novel Drift checks (Spec 4 Task 4).
 *
 * Two mutation hooks back the read-only analysis actions for one series:
 *
 * - ``useSeriesConsistency``  — POST check a band's chapter prose vs the series
 *   Canon KB (returns the canon contradictions found, possibly empty).
 * - ``useSeriesVoiceDrift``   — POST analyse a band's narrator drift against the
 *   series voice baseline (reuses the novel-level response shape).
 *
 * Both are one-shot mutations: the checks are read-only and stateless (nothing
 * is persisted), so there is no query to invalidate. The panel holds the result
 * in the mutation's ``data`` and resets it when a new check starts. Mirrors the
 * established Narrare mutation pattern (``useProfileSeriesVoice``) minus the
 * invalidation (no persisted state to refresh).
 */
import { useMutation } from "@tanstack/react-query";
import { seriesApi } from "@/lib/api/series";

/**
 * POST /api/v1/series/{id}/consistency/check.
 * Call `.mutate(novelId)`; the result lands in `.data` (a graceful empty
 * `conflicts` list means no contradictions were found).
 */
export function useSeriesConsistency(seriesId: string) {
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.checkSeriesConsistency(seriesId, novelId),
  });
}

/**
 * POST /api/v1/series/{id}/voice-drift/check.
 * Call `.mutate(novelId)`; the result lands in `.data` (exactly one of
 * `result` / `no_profile` is set — `no_profile` is the RULE-11 graceful skip).
 */
export function useSeriesVoiceDrift(seriesId: string) {
  return useMutation({
    mutationFn: (novelId: string) => seriesApi.checkSeriesVoiceDrift(seriesId, novelId),
  });
}
