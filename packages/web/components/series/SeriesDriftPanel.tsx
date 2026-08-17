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
 * - ``useSeriesDriftSnapshot`` — GET the persisted latest-wins snapshot (C2);
 *   the panel hydrates from it instead of an empty state and badges it stale
 *   when the band's texts changed.
 *
 * The author picks a band (novel) from the dropdown and clicks **Check
 * consistency**, which fires BOTH checks in parallel (each is an independent
 * one-shot LLM analysis). Each result section shows its own loading / error /
 * result / empty state. Per Spec 4 design D3 the panel lives as a dedicated
 * section in the Bände tab (no separate tab) so `BaendeList` stays focused on
 * list/reorder (RULE-06).
 *
 * RULE-04: the two result renderers are extracted into `SeriesConflictList` +
 * `SeriesDriftSummary`, and the shared loading/error section shell into
 * `SeriesDriftResultSection`. All copy via ``useTranslations("studio")`` under
 * ``series.drift.*``.
 */
import { Loader2, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { SeriesConflictList } from "@/components/series/SeriesConflictList";
import { SeriesDriftResultSection } from "@/components/series/SeriesDriftResultSection";
import { SeriesDriftSummary } from "@/components/series/SeriesDriftSummary";
import {
  useSeriesConsistency,
  useSeriesDriftSnapshot,
  useSeriesVoiceDrift,
} from "@/lib/hooks/useSeriesDrift";
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
  // C2: the persisted snapshot for the selected band (all-null when nothing
  // was saved yet). Fresh run data takes precedence over it below.
  const snapshot = useSeriesDriftSnapshot(seriesId, selectedNovelId);

  const consistencyView = consistency.data ?? snapshot.data?.consistency ?? null;
  const driftView = drift.data ?? snapshot.data?.voice_drift ?? null;

  const isChecking = consistency.isPending || drift.isPending;
  const hasAnyActivity =
    consistency.isPending ||
    drift.isPending ||
    Boolean(consistencyView) ||
    Boolean(driftView) ||
    consistency.isError ||
    drift.isError;

  // The snapshot hint shows only while the persisted snapshot is the visible
  // source (no fresh run data this session). Invariant: sections non-null
  // implies generated_at non-null (a persisted record always carries it).
  const snapshotVisible =
    !consistency.data &&
    !drift.data &&
    !isChecking &&
    (snapshot.data?.consistency != null || snapshot.data?.voice_drift != null);

  function handleSelect(novelId: string): void {
    setSelectedNovelId(novelId);
    // Clear the previous band's fresh results so the panel never mixes
    // bands; the snapshot query re-keys automatically.
    consistency.reset();
    drift.reset();
  }

  function handleCheck(): void {
    if (!selectedNovelId || isChecking) return;
    // Reset so the (now stale) persisted display clears while the checks run.
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
            onChange={(e) => handleSelect(e.target.value)}
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
        {snapshotVisible && snapshot.data ? (
          <p
            data-testid="series-drift-snapshot-hint"
            className="pt-1 text-xs text-muted-foreground"
          >
            {snapshot.data.stale
              ? t("series.drift.snapshot.stale")
              : t("series.drift.snapshot.restored", {
                  generatedAt: new Date(snapshot.data.generated_at ?? 0),
                })}
          </p>
        ) : null}
      </div>

      {/* Consistency section */}
      {hasAnyActivity ? (
        <SeriesDriftResultSection
          testId="series-drift-consistency-section"
          title={t("series.drift.conflicts")}
          isPending={consistency.isPending}
          isError={consistency.isError}
          loadingKey="series.drift.loading"
          errorKey="series.drift.error"
        >
          {consistencyView ? (
            <SeriesConflictList
              conflicts={consistencyView.conflicts}
              summary={consistencyView.summary}
            />
          ) : null}
        </SeriesDriftResultSection>
      ) : null}

      {/* Voice drift section */}
      {hasAnyActivity ? (
        <SeriesDriftResultSection
          testId="series-drift-voice-section"
          title={t("series.drift.checkVoiceDrift")}
          isPending={drift.isPending}
          isError={drift.isError}
          loadingKey="series.drift.loading"
          errorKey="series.drift.error"
        >
          {driftView ? <SeriesDriftSummary response={driftView} /> : null}
        </SeriesDriftResultSection>
      ) : null}
    </section>
  );
}
