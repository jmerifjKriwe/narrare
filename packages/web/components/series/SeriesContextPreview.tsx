"use client";

/**
 * SeriesContextPreview — live honesty preview for the context-window slider
 * (C1, design §4.1): renders what the series-history block would contain at
 * the selected window size — band classification (full / short / truncated /
 * dropped / missing) and the estimated token total against the EFFECTIVE
 * series-history budget (ADR-082 EffectiveContextBudgets, computed
 * server-side from the series' actual summaries; never fabricated
 * client-side). Pure presentational; no data fetching.
 */
import { useTranslations } from "next-intl";
import type { SeriesHistoryPreviewEntry, SeriesHistoryPreviewResponse } from "@/types";

interface SeriesContextPreviewProps {
  readonly entry: SeriesHistoryPreviewEntry;
  readonly meta: SeriesHistoryPreviewResponse;
}

export function SeriesContextPreview({ entry, meta }: SeriesContextPreviewProps) {
  const t = useTranslations("studio");

  return (
    <div
      data-testid="series-context-preview"
      data-window={entry.window_size}
      className="space-y-1 rounded-md border border-border bg-card p-3 text-xs text-muted-foreground"
    >
      <p data-testid="series-context-preview-line" className="text-sm text-foreground">
        {t("series.settings.contextPreview.bandsLine", {
          full: entry.bands_full,
          short: entry.bands_short,
        })}
        {" — "}
        {t("series.settings.contextPreview.tokenLine", {
          tokens: entry.estimated_tokens,
          budget: entry.token_budget,
        })}
      </p>
      {entry.bands_truncated > 0 ? (
        <p data-testid="series-context-preview-truncated">
          {t("series.settings.contextPreview.truncatedNote", {
            count: entry.bands_truncated,
          })}
        </p>
      ) : null}
      {entry.bands_dropped > 0 ? (
        <p data-testid="series-context-preview-dropped">
          {t("series.settings.contextPreview.droppedNote", { count: entry.bands_dropped })}
        </p>
      ) : null}
      {entry.bands_missing > 0 ? (
        <p data-testid="series-context-preview-missing">
          {t("series.settings.contextPreview.missingNote", { count: entry.bands_missing })}
        </p>
      ) : null}
      {entry.budget_clipped ? (
        <p data-testid="series-context-preview-clipped" className="text-amber-600">
          {t("series.settings.contextPreview.clippedWarning")}
        </p>
      ) : null}
      <p data-testid="series-context-preview-budget">
        {t("series.settings.contextPreview.budgetLine", {
          seriesBudget: meta.effective_series_history_budget,
          totalBudget: meta.effective_context_total,
          tierBase: meta.effective_tier_base,
        })}
      </p>
      {meta.model_context_window === null ? (
        <p data-testid="series-context-preview-window-unknown">
          {t("series.settings.contextPreview.windowUnknown")}
        </p>
      ) : null}
    </div>
  );
}
