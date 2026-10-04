"use client";

/**
 * DedupCard — review-mode dedup card for the corpus pass (F3 T5, ADR-085).
 *
 * The completion-time dedup analysis ran over the PRE-APPLY roster (T3
 * binding copy ruling): the registry count is a flagged-at-completion
 * number, never a static duplicate fact. After applies the live suggestion
 * cache self-heals (entries-hash keyed), so the card invites the on-demand
 * Re-check and swaps to the fresh count once one has run.
 *
 * An `analyzed: false` block is AMBIGUOUS on the wire — the runner marks the
 * job completed BEFORE the post-pass analysis lands, so pending and failed
 * are indistinguishable (`{analyzed: false, suggestion_count: null}` both).
 * While the poll grace window is live (`pending`, fix round 1) the card
 * shows a running copy — never the false "could not run" claim; only after
 * the bound expires is the unavailable copy honest. The Re-check recovery
 * (user-initiated adjudicated analyzer — hence the AI-cost hint) is offered
 * in every non-analyzed state.
 *
 * @module DedupCard
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { BulkDedupInfo } from "@/lib/api/bulkExtraction";
import { kbResolutionApi, resolutionSuggestionsQueryKey } from "@/lib/api/kbResolution";
import { ResolutionSuggestionsList } from "./ResolutionSuggestionsList";

interface DedupCardProps {
  readonly novelId: string;
  /** Completion-time dedup block from the job status (non-null here). */
  readonly dedup: BulkDedupInfo;
  /**
   * True while the completed-with-unanalyzed window is live (poll loop still
   * waiting for the post-pass analysis, bounded by DEDUP_PENDING_GRACE_MS).
   */
  readonly pending: boolean;
}

export function DedupCard({ novelId, dedup, pending }: DedupCardProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const [reviewOpen, setReviewOpen] = useState(false);
  const [freshCount, setFreshCount] = useState<number | null>(null);
  const recheck = useMutation({
    mutationFn: () => kbResolutionApi.analyzeSuggestions(novelId),
    onSuccess: (data) => {
      setFreshCount(data.suggestions.length);
      setReviewOpen(true);
      // Seed the list cache with the authoritative fresh analysis (the list
      // renders from this key; a re-check replaces any optimistic residue).
      queryClient.setQueryData(resolutionSuggestionsQueryKey(novelId), data);
    },
  });

  // The honest card line, narrowed outside JSX: freshCount (a re-check has
  // run) wins over the completion-time registry count; zero gets its own
  // clean copy instead of "0 possible duplicates"; the degenerate
  // analyzed-without-count shape degrades to the unavailable copy.
  let dedupLine: string;
  if (freshCount !== null) {
    dedupLine = t("kb.resolution.dedupRefreshed", { count: freshCount });
  } else if (dedup.suggestion_count === 0) {
    dedupLine = t("kb.resolution.dedupClean");
  } else if (typeof dedup.suggestion_count === "number") {
    dedupLine = t("kb.resolution.dedupFound", { count: dedup.suggestion_count });
  } else {
    dedupLine = t("kb.resolution.dedupUnavailable");
  }

  return (
    <>
      {dedup.analyzed && dedup.suggestion_count !== null ? (
        <div className="mb-4 rounded-md border border-border p-3" data-testid="dedup-card">
          <p className="text-sm text-muted-foreground">{dedupLine}</p>
          <div className="mt-2 flex gap-3">
            <button
              type="button"
              onClick={() => setReviewOpen((open) => !open)}
              className="text-sm text-primary hover:underline"
            >
              {t("kb.resolution.review")}
            </button>
            <button
              type="button"
              onClick={() => recheck.mutate()}
              disabled={recheck.isPending}
              className="text-sm text-muted-foreground hover:underline disabled:opacity-50"
            >
              {recheck.isPending ? t("kb.resolution.rechecking") : t("kb.resolution.recheck")}
            </button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{t("kb.resolution.recheckHint")}</p>
          {recheck.isError && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {t("kb.resolution.recheckFailed")}
            </p>
          )}
          {reviewOpen && (
            <div className="mt-2">
              <ResolutionSuggestionsList novelId={novelId} />
            </div>
          )}
        </div>
      ) : (
        <div className="mb-4 rounded-md border border-border p-3">
          <p className="text-sm text-muted-foreground">
            {pending ? t("kb.resolution.dedupPending") : t("kb.resolution.dedupUnavailable")}
          </p>
          <div className="mt-2">
            <button
              type="button"
              onClick={() => recheck.mutate()}
              disabled={recheck.isPending}
              className="text-sm text-primary hover:underline disabled:opacity-50"
            >
              {recheck.isPending ? t("kb.resolution.rechecking") : t("kb.resolution.recheck")}
            </button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{t("kb.resolution.recheckHint")}</p>
          {recheck.isError && (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {t("kb.resolution.recheckFailed")}
            </p>
          )}
        </div>
      )}
    </>
  );
}
