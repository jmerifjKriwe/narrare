/**
 * useWikiOverviewActions — Generation and refresh affordances for the
 * Wiki overview panel (M11).
 *
 * Owns the single wiki-refresh mutation instance shared by the overview's
 * action buttons and the per-entity summary cards:
 * - `generateAllFromKb`: at Total 0 no ROW exists, so no per-card Generate
 *   button can render. Generate the wiki from the KB itself — the refresh
 *   service creates rows for entities that have none. Collects entry ids by
 *   paging the entries endpoint on demand, so KBs larger than one page are
 *   fully covered.
 * - `refreshNonFresh`: pending (never generated) rows need the same path as
 *   stale ones — refresh every non-fresh summary.
 */

import { useCallback, useMemo } from "react";
import { kbApi } from "@/lib/api/kb";
import type { WikiSummaryResponse } from "@/lib/api/wiki";
import { useKBEntries } from "@/lib/hooks/useKB";
import { useWikiRefresh } from "@/lib/hooks/useWiki";

/** Backend caps page_size at 100 (kb router `Query(default=50, ge=1, le=100)`). */
const KB_PAGE_SIZE = 100;

interface UseWikiOverviewActionsParams {
  novelId: string;
  sortedSummaries: WikiSummaryResponse[];
}

export function useWikiOverviewActions({ novelId, sortedSummaries }: UseWikiOverviewActionsParams) {
  const refreshMutation = useWikiRefresh(novelId);

  // Mount fetch (backend-default first page) stays as-is: it only feeds the
  // "KB is empty" disable check on the Generate button. It is NOT the source
  // of generate-all's ids — a first page is capped (default 50), so the
  // action below pages the endpoint itself.
  const { data: entriesData } = useKBEntries(novelId);
  const kbEntityIds = useMemo(
    () => (entriesData?.items ?? []).map((entry) => entry.id),
    [entriesData],
  );

  // M11 first-generation path: at Total 0 no ROW exists, so no per-card
  // Generate button can render. Generate the wiki from the KB itself —
  // the refresh service creates rows for entities that have none.
  const generateAllFromKb = useCallback(async () => {
    // Fetch on demand, paged at the backend maximum; stop at the first
    // short page (fewer items than page_size ⇒ last page).
    const entityIds: string[] = [];
    for (let page = 1; ; page += 1) {
      const data = await kbApi.listEntries(novelId, { page, page_size: KB_PAGE_SIZE });
      entityIds.push(...data.items.map((entry) => entry.id));
      if (data.items.length < KB_PAGE_SIZE) break;
    }
    for (const entityId of entityIds) {
      refreshMutation.mutate({ entityId });
    }
  }, [novelId, refreshMutation]);

  // M11: pending (never generated) rows need the same path as
  // stale ones — refresh every non-fresh summary.
  const refreshNonFresh = useCallback(() => {
    const nonFreshIds = sortedSummaries.filter((s) => s.status !== "fresh").map((s) => s.entity_id);
    for (const entityId of nonFreshIds) {
      refreshMutation.mutate({ entityId });
    }
  }, [sortedSummaries, refreshMutation]);

  // Reconciled with refreshNonFresh: enablement and action read the same
  // source (the summaries list), instead of enablement trusting the index
  // counters while the action iterates the list rows.
  const canRefreshNonFresh =
    sortedSummaries.some((s) => s.status !== "fresh") && !refreshMutation.isPending;

  return {
    refreshMutation,
    kbEntityIds,
    generateAllFromKb,
    refreshNonFresh,
    canRefreshNonFresh,
  };
}
