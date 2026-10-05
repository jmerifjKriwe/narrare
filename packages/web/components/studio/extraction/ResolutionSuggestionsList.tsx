"use client";

/**
 * ResolutionSuggestionsList — minimal ADR-085 suggestions review (F3 plan
 * Task 5, spec §8): the duplicate pairs from the served analysis, each with
 * names, confidence and band, and per-row Merge / Dismiss actions.
 *
 * THE GATE (ADR-085 D3, suggestions-only): merges happen ONLY on endorse —
 * `endorseSuggestion` executes the merge server-side, `rejectSuggestion`
 * persists the dismissal. Actions remove their row OPTIMISTICALLY and roll
 * back on failure; a 409 (stale / already resolved elsewhere) gets its own
 * copy. There is deliberately NO refetch after an action: the endorse
 * endpoint invalidates the server analysis cache, so a refetch would serve
 * the EMPTY miss-response and wipe still-unreviewed pairs — the dedup
 * card's explicit Re-check is the authoritative refresh (spec §7).
 *
 * Mount = fetch: the parent toggles this list, so the (lazy) review is only
 * fetched once opened. Loading / error(+retry) / empty states per §16.
 *
 * @module ResolutionSuggestionsList
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import {
  kbResolutionApi,
  type ResolutionAnalysisResponse,
  ResolutionApiError,
  resolutionSuggestionsQueryKey,
} from "@/lib/api/kbResolution";

interface ResolutionSuggestionsListProps {
  readonly novelId: string;
}

type SuggestionAction = "endorse" | "reject";

interface ActionVariables {
  readonly id: string;
  readonly action: SuggestionAction;
}

export function ResolutionSuggestionsList({ novelId }: ResolutionSuggestionsListProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const queryKey = resolutionSuggestionsQueryKey(novelId);

  const [actionError, setActionError] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<SuggestionAction | null>(null);

  const list = useQuery({
    queryKey,
    queryFn: ({ signal }) => kbResolutionApi.listSuggestions(novelId, signal),
  });

  // One mutation for both actions: optimistic row removal + error rollback.
  // NO onSettled invalidate — see the module docstring (the post-endorse
  // cache invalidation makes an immediate refetch lossy).
  const act = useMutation({
    mutationFn: ({ id, action }: ActionVariables) =>
      action === "endorse"
        ? kbResolutionApi.endorseSuggestion(novelId, id)
        : kbResolutionApi.rejectSuggestion(novelId, id),
    onMutate: async ({ id }) => {
      setActionError(null);
      setLastAction(null);
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<ResolutionAnalysisResponse>(queryKey);
      queryClient.setQueryData<ResolutionAnalysisResponse>(queryKey, (old) =>
        old === undefined
          ? old
          : { ...old, suggestions: old.suggestions.filter((s) => s.suggestion_id !== id) },
      );
      return { previous };
    },
    onError: (error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(queryKey, context.previous);
      setActionError(
        error instanceof ResolutionApiError && error.status === 409
          ? t("kb.resolution.staleError")
          : t("kb.resolution.actionFailed"),
      );
    },
    onSuccess: (_data, { action }) => setLastAction(action),
  });

  if (list.isPending) {
    return <p className="text-sm text-muted-foreground">{t("kb.resolution.loading")}</p>;
  }

  if (list.isError) {
    return (
      <div>
        <p role="alert" className="text-sm text-destructive">
          {t("kb.resolution.loadFailed")}
        </p>
        <button
          type="button"
          onClick={() => void list.refetch()}
          className="mt-1 text-sm text-primary hover:underline"
        >
          {t("kb.resolution.retry")}
        </button>
      </div>
    );
  }

  const { suggestions } = list.data;

  return (
    <div data-testid="resolution-suggestions">
      {suggestions.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("kb.resolution.empty")}</p>
      ) : (
        <ul className="divide-y" aria-label={t("kb.resolution.title")}>
          {suggestions.map((s) => {
            const rowPending = act.isPending && act.variables?.id === s.suggestion_id;
            return (
              <li key={s.suggestion_id} className="flex items-center justify-between gap-3 py-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {t("kb.resolution.pair", { nameA: s.name_a, nameB: s.name_b })}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t("kb.resolution.confidence", {
                      percent: Math.round(s.confidence * 100),
                    })}
                    {" · "}
                    {s.band === "AUTO_ELIGIBLE"
                      ? t("kb.resolution.bandAuto")
                      : t("kb.resolution.bandReview")}
                  </p>
                  {s.adjudication_note !== null && (
                    <p className="mt-0.5 text-xs italic text-muted-foreground">
                      {s.adjudication_note}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    disabled={rowPending}
                    onClick={() => act.mutate({ id: s.suggestion_id, action: "endorse" })}
                    className="text-sm text-primary hover:underline disabled:opacity-50"
                  >
                    {rowPending && act.variables?.action === "endorse"
                      ? t("kb.resolution.endorsing")
                      : t("kb.resolution.endorse")}
                  </button>
                  <button
                    type="button"
                    disabled={rowPending}
                    onClick={() => act.mutate({ id: s.suggestion_id, action: "reject" })}
                    className="text-sm text-muted-foreground hover:underline disabled:opacity-50"
                  >
                    {rowPending && act.variables?.action === "reject"
                      ? t("kb.resolution.rejecting")
                      : t("kb.resolution.reject")}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {actionError !== null && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          {actionError}
        </p>
      )}
      {actionError === null && lastAction !== null && (
        <p role="status" className="mt-2 text-sm text-muted-foreground">
          {lastAction === "endorse" ? t("kb.resolution.endorsed") : t("kb.resolution.rejected")}
        </p>
      )}
    </div>
  );
}
