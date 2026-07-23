"use client";

/** TanStack Query hooks for Adaptive Context CRUD (ADR-069 Decision 15).
 *
 *  Adaptive settings are NOT an AI operation (ADR-043) — they are regular REST
 *  CRUD, so TanStack Query cache invalidation is the conform pattern. The
 *  canonical key {@link adaptiveKeys} is the SSOT; mutations invalidate it so
 *  the Status Indicator, Dashboard, and Dialogue Coach panel refetch in lockstep.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adaptiveApi } from "@/lib/api/adaptive";
import type { AdaptiveWeightsInput } from "@/types";
import { adaptiveKeys } from "./adaptiveKeys";

export { adaptiveKeys } from "./adaptiveKeys";

/** Read the current adaptive context for the dashboard + indicator. */
export function useAdaptiveContext(projectId: string) {
  return useQuery({
    queryKey: adaptiveKeys.context(projectId),
    queryFn: () => adaptiveApi.getContext(projectId),
    enabled: !!projectId,
  });
}

/** Toggle adaptivity on/off; invalidates the canonical key on success. */
export function useToggleAdaptive(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => adaptiveApi.toggle(projectId, enabled),
    onSuccess: () => void qc.invalidateQueries({ queryKey: adaptiveKeys.context(projectId) }),
  });
}

/** Update the 4 weights; invalidates the canonical key on success. */
export function useSetAdaptiveWeights(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (weights: AdaptiveWeightsInput) => adaptiveApi.setWeights(projectId, weights),
    onSuccess: () => void qc.invalidateQueries({ queryKey: adaptiveKeys.context(projectId) }),
  });
}
