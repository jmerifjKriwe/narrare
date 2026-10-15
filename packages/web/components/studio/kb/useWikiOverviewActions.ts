/**
 * useWikiOverviewActions — Generation and refresh affordances for the
 * Wiki overview panel (M11).
 *
 * Owns the single wiki-refresh mutation instance shared by the overview's
 * action buttons and the per-entity summary cards:
 * - `generateAllFromKb`: at Total 0 no ROW exists, so no per-card Generate
 *   button can render. Generate the wiki from the KB itself — the refresh
 *   service creates rows for entities that have none.
 * - `refreshNonFresh`: pending (never generated) rows need the same path as
 *   stale ones — refresh every non-fresh summary.
 */

import { useCallback, useMemo } from "react";
import type { WikiIndexResponse, WikiSummaryResponse } from "@/lib/api/wiki";
import { useKBEntries } from "@/lib/hooks/useKB";
import { useWikiRefresh } from "@/lib/hooks/useWiki";

interface UseWikiOverviewActionsParams {
  novelId: string;
  sortedSummaries: WikiSummaryResponse[];
  indexData: WikiIndexResponse | undefined;
}

export function useWikiOverviewActions({
  novelId,
  sortedSummaries,
  indexData,
}: UseWikiOverviewActionsParams) {
  const refreshMutation = useWikiRefresh(novelId);

  const { data: entriesData } = useKBEntries(novelId);
  const kbEntityIds = useMemo(
    () => (entriesData?.items ?? []).map((entry) => entry.id),
    [entriesData],
  );

  // M11 first-generation path: at Total 0 no ROW exists, so no per-card
  // Generate button can render. Generate the wiki from the KB itself —
  // the refresh service creates rows for entities that have none.
  const generateAllFromKb = useCallback(() => {
    for (const entityId of kbEntityIds) {
      refreshMutation.mutate({ entityId });
    }
  }, [kbEntityIds, refreshMutation]);

  // M11: pending (never generated) rows need the same path as
  // stale ones — refresh every non-fresh summary.
  const refreshNonFresh = useCallback(() => {
    const nonFreshIds = sortedSummaries.filter((s) => s.status !== "fresh").map((s) => s.entity_id);
    for (const entityId of nonFreshIds) {
      refreshMutation.mutate({ entityId });
    }
  }, [sortedSummaries, refreshMutation]);

  // Enabled iff at least one summary is non-fresh (stale or pending).
  const canRefreshNonFresh =
    (indexData?.stale_count ?? 0) + (indexData?.pending_count ?? 0) > 0 &&
    !refreshMutation.isPending;

  return {
    refreshMutation,
    kbEntityIds,
    generateAllFromKb,
    refreshNonFresh,
    canRefreshNonFresh,
  };
}
