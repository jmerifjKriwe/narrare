"use client";

/** useAdaptiveSnapshots — recent adaptive activity timeline query (ADR-070).
 *
 *  Shares the canonical `["adaptive-context", projectId, "snapshots"]` key
 *  (ADR-069 Decision 15) so a single dashboard invalidation refreshes history
 *  in lockstep with the indicator, sliders, and source list. */
import { useQuery } from "@tanstack/react-query";
import { adaptiveApi } from "@/lib/api/adaptive";
import { adaptiveKeys } from "./adaptiveKeys";

export function useAdaptiveSnapshots(projectId: string, limit = 20) {
  return useQuery({
    queryKey: adaptiveKeys.snapshots(projectId),
    queryFn: () => adaptiveApi.getSnapshots(projectId, limit),
    enabled: !!projectId,
  });
}
