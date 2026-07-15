"use client";

/**
 * useDismissedFindings — TanStack Query hooks for dismissed consistency
 * findings (CR-AUFG-07-26).
 *
 * Fetches the list of dismissed fingerprints and exposes dismiss/undismiss
 * mutations that invalidate the cache. Components consume the
 * ``dismissedFingerprints`` Set for O(1) lookup when filtering issues.
 *
 * All data fetching/mutation logic lives here — components stay
 * presentation-only (RULE-06).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { DismissFindingRequest } from "@/lib/api/consistency";
import { consistencyApi } from "@/lib/api/consistency";
import { kbKeys } from "@/lib/hooks/kbKeys";

export interface UseDismissedFindingsReturn {
  /** Set of dismissed fingerprints for O(1) membership checks. */
  readonly dismissedFingerprints: Set<string>;
  /** Dismiss a finding by its fingerprint. */
  readonly dismiss: (fingerprint: string, reason?: string) => void;
  /** Un-dismiss (restore) a previously dismissed finding. */
  readonly undismiss: (fingerprint: string) => void;
  /** Whether the dismissed list is loading. */
  readonly isLoading: boolean;
}

/**
 * Read dismissed findings + expose dismiss/undismiss mutations for a novel.
 */
export function useDismissedFindings(novelId: string): UseDismissedFindingsReturn {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: kbKeys.dismissedFindings(novelId),
    queryFn: () => consistencyApi.listDismissed(novelId),
    enabled: !!novelId,
  });

  const fingerprints = query.data?.fingerprints ?? [];
  const dismissedFingerprints = new Set<string>(fingerprints);

  const dismissMutation = useMutation({
    mutationFn: (request: DismissFindingRequest) => consistencyApi.dismissFinding(novelId, request),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: kbKeys.dismissedFindings(novelId) });
    },
  });

  const undismissMutation = useMutation({
    mutationFn: (fingerprint: string) => consistencyApi.undismissFinding(novelId, fingerprint),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: kbKeys.dismissedFindings(novelId) });
    },
  });

  const dismiss = (fingerprint: string, reason?: string) => {
    dismissMutation.mutate({ fingerprint, reason });
  };

  const undismiss = (fingerprint: string) => {
    undismissMutation.mutate(fingerprint);
  };

  return {
    dismissedFingerprints,
    dismiss,
    undismiss,
    isLoading: query.isLoading,
  };
}
