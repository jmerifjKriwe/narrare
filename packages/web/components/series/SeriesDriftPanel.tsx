"use client";

/**
 * SeriesDriftPanel — the Cross-Novel Drift panel for one series (Spec 4 Task 4).
 *
 * Surfaces the two series-scope read-only checks together:
 *
 * - **Consistency** (POST …/consistency/check) — does a band's chapter prose
 *   contradict the series Canon? Renders via `SeriesConflictList`.
 * - **Voice drift** (POST …/voice-drift/check) — how far has a band's narrator
 *   drifted from the series voice baseline? Renders via `SeriesDriftSummary`.
 *
 * The author picks a band (novel) from the dropdown and clicks **Check
 * consistency**, which fires BOTH checks in parallel (each is an independent
 * one-shot LLM analysis). Each result section shows its own loading / error /
 * result / empty state. Per Spec 4 design D3 the panel lives as a dedicated
 * section in the Bände tab (no separate tab) so `BaendeList` stays focused on
 * list/reorder (RULE-06).
 *
 * RULE-04: the two result renderers are extracted into `SeriesConflictList` +
 * `SeriesDriftSummary`. All copy via ``useTranslations("studio")`` under
 * ``series.drift.*``.
 */
import { Loader2, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { SeriesConflictList } from "@/components/series/SeriesConflictList";
import { SeriesDriftSummary } from "@/components/series/SeriesDriftSummary";
import { useSeriesConsistency, useSeriesVoiceDrift } from "@/lib/hooks/useSeriesDrift";
import { useSeriesNovels } from "@/lib/hooks/useSeriesNovels";

interface SeriesDriftPanelProps {
  readonly seriesId: string;
}

export function SeriesDriftPanel({ seriesId }: SeriesDriftPanelProps) {
  const t = useTranslations("studio");
  const { data: novels = [], isLoading: novelsLoading } = useSeriesNovels(seriesId);
  const consistency = useSeriesConsistency(seriesId);
  const drift = useSeriesVoiceDrift(seriesId);

  const [selectedNovelId, setSelectedNovelId] = useState("");
  const isChecking = consistency.isPending || drift.isPending;
  const hasAnyActivity =
    consistency.isPending ||
    drift.isPending ||
    Boolean(consistency.data) ||
    Boolean(drift.data) ||
    consistency.isError ||
    drift.isError;

  function handleCheck(): void {
    if (!selectedNovelId || isChecking) return;
    // Reset so stale results from a previous band clear while the new checks run.
    consistency.reset();
    drift.reset();
    void consistency.mutate(selectedNovelId);
    void drift.mutate(selectedNovelId);
  }

  return (
    <section data-testid="series-drift-panel" className="max-w-3xl space-y-3">
      <h2 className="text-lg font-medium">{t("series.drift.title")}</h2>

      {/* Band selector + check trigger */}
      <div className="space-y-2 rounded-md border border-border bg-card p-4">
        <label className="text-xs font-medium text-foreground" htmlFor="series-drift-band-select">
          {t("series.drift.selectBand")}
        </label>
        <div className="flex items-center gap-2">
          <select
            id="series-drift-band-select"
            data-testid="series-drift-band-select"
            value={selectedNovelId}
            onChange={(e) => setSelectedNovelId(e.target.value)}
            disabled={novelsLoading}
            className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">{t("series.drift.selectBandPlaceholder")}</option>
            {novels.map((novel) => (
              <option key={novel.id} value={novel.id}>
                {novel.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            data-testid="series-drift-check"
            onClick={handleCheck}
            disabled={!selectedNovelId || isChecking}
            className="flex items-center gap-1 rounded bg-primary px-3 py-1 text-xs text-primary-foreground disabled:opacity-50"
          >
            {isChecking ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <ShieldCheck className="h-3 w-3" />
            )}
            {t("series.drift.checkConsistency")}
          </button>
        </div>
        {!hasAnyActivity ? (
          <p
            data-testid="series-drift-idle"
            className="flex items-center gap-1 pt-1 text-xs text-muted-foreground"
          >
            <ShieldCheck className="h-3 w-3" />
            {t("series.drift.description")}
          </p>
        ) : null}
      </div>

      {/* Consistency section */}
      {hasAnyActivity ? (
        <ResultSection
          testId="series-drift-consistency-section"
          title={t("series.drift.conflicts")}
          isPending={consistency.isPending}
          isError={consistency.isError}
          loadingKey="series.drift.loading"
          errorKey="series.drift.error"
        >
          {consistency.data ? (
            <SeriesConflictList
              conflicts={consistency.data.conflicts}
              summary={consistency.data.summary}
            />
          ) : null}
        </ResultSection>
      ) : null}

      {/* Voice drift section */}
      {hasAnyActivity ? (
        <ResultSection
          testId="series-drift-voice-section"
          title={t("series.drift.checkVoiceDrift")}
          isPending={drift.isPending}
          isError={drift.isError}
          loadingKey="series.drift.loading"
          errorKey="series.drift.error"
        >
          {drift.data ? <SeriesDriftSummary response={drift.data} /> : null}
        </ResultSection>
      ) : null}
    </section>
  );
}

// --- Shared section shell (loading / error / content) -----------------------

interface ResultSectionProps {
  readonly testId: string;
  readonly title: string;
  readonly isPending: boolean;
  readonly isError: boolean;
  readonly loadingKey: string;
  readonly errorKey: string;
  readonly children: React.ReactNode;
}

function ResultSection({
  testId,
  title,
  isPending,
  isError,
  loadingKey,
  errorKey,
  children,
}: ResultSectionProps) {
  const t = useTranslations("studio");
  return (
    <div data-testid={testId} className="space-y-2">
      <h3 className="text-sm font-medium text-foreground">{title}</h3>
      {isPending ? (
        <p
          data-testid={`${testId}-loading`}
          className="flex items-center gap-2 py-2 text-sm text-muted-foreground"
        >
          <Loader2 className="h-4 w-4 animate-spin" />
          {t(loadingKey)}
        </p>
      ) : isError ? (
        <p data-testid={`${testId}-error`} className="py-2 text-sm text-destructive">
          {t(errorKey)}
        </p>
      ) : (
        children
      )}
    </div>
  );
}
