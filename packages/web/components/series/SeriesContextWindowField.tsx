"use client";

/**
 * SeriesContextWindowField — slider editor for the Series recency-window
 * setting (SERIES-002; C1 — Context-Window Slider, design §4 2026-08-14).
 *
 * Replaces the original number input [1, 50] with a 1-10 slider plus a
 * live preview (SeriesContextPreview) computed server-side from the
 * series' ACTUAL band summaries against the EFFECTIVE post-C5/ADR-082
 * budgets — the slider alone would be a lie by omission: the token budget
 * silently clips oversized windows (design §4.2). The original
 * input-choice rationale (number input for precision) was superseded by
 * the approved C1 design; the API bound stays [1, 50] (superset,
 * MCP/CLI-settable) — a saved value outside 1-10 is shown honestly via a
 * notice + the extended preview range and is replaced on the next save.
 *
 * Persists via PATCH /series/{id}/settings (existing endpoint, design
 * §4.1). Owns its local state, dirty-gated Save, and loading/error
 * states, mirroring the NovelDetailsTab / SeriesMetadataForm pattern.
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import {
  useSeriesHistoryPreview,
  useSeriesSettings,
  useUpdateSeriesSettings,
} from "@/lib/hooks/useSeries";
import { SeriesContextPreview } from "./SeriesContextPreview";
import { SeriesField as Field } from "./SeriesField";

interface SeriesContextWindowFieldProps {
  readonly seriesId: string;
}

const MIN_WINDOW = 1;
const MAX_WINDOW = 10;

export function SeriesContextWindowField({ seriesId }: SeriesContextWindowFieldProps) {
  const t = useTranslations("studio");
  const { data: settings, isLoading, isError } = useSeriesSettings(seriesId);
  const previewQuery = useSeriesHistoryPreview(seriesId);
  const update = useUpdateSeriesSettings(seriesId);

  const [draft, setDraft] = useState<number>(3);
  const [dirty, setDirty] = useState(false);

  // Re-sync from server data only while clean — mirrors SeriesMetadataForm's
  // dirty guard so a background refetch (new object identity) can't clobber
  // the user's in-flight edit.
  useEffect(() => {
    if (dirty) return;
    if (settings) setDraft(settings.context_window_size);
  }, [settings, dirty]);

  const saved = settings?.context_window_size ?? null;
  const previewData = previewQuery.data;
  // The server range is 1..max(10, saved) — the lookup also covers a saved
  // value above the slider top (shown until the user moves the slider).
  const entry = previewData?.previews.find((p) => p.window_size === draft) ?? undefined;

  // Clear dirty only once the server round-trip confirms the draft (fresh
  // settings equal it, no PATCH in flight). Clearing it in mutate's
  // onSuccess instead would run the re-sync effect above against
  // still-stale settings and flash the old slider position before the
  // refetched data lands.
  useEffect(() => {
    if (dirty && !update.isPending && saved !== null && draft === saved) {
      setDirty(false);
    }
  }, [dirty, saved, draft, update.isPending]);

  function handleSlide(raw: number): void {
    setDraft(Math.min(Math.max(raw, MIN_WINDOW), MAX_WINDOW));
    setDirty(true);
  }

  function handleSave(): void {
    if (draft < MIN_WINDOW || draft > MAX_WINDOW) return;
    // No-op if unchanged (e.g. Save clicked in the window between sliding
    // back to the saved value and the confirmation effect above flushing).
    if (saved !== null && draft === saved) return;
    update.mutate({ context_window_size: draft });
  }

  if (isLoading) {
    return (
      <div
        data-testid="series-context-window-loading"
        className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground"
      >
        <Loader2 className="h-5 w-5 animate-spin" />
        {t("series.settings.loading")}
      </div>
    );
  }

  if (isError || !settings) {
    return (
      <div
        data-testid="series-context-window-error"
        className="py-8 text-center text-sm text-muted-foreground"
      >
        {t("series.settings.error")}
      </div>
    );
  }

  const label = t("series.settings.contextWindow.label");
  const canSave = dirty && draft >= MIN_WINDOW && draft <= MAX_WINDOW;

  return (
    <section data-testid="series-context-window" className="space-y-4">
      <div className="space-y-3 rounded-lg border border-border bg-card p-6">
        <Field label={label}>
          <div className="flex items-center gap-3">
            <input
              data-testid="series-context-window-slider"
              type="range"
              min={MIN_WINDOW}
              max={MAX_WINDOW}
              step={1}
              value={Math.min(draft, MAX_WINDOW)}
              onChange={(e) => handleSlide(Number(e.target.value))}
              aria-label={label}
              aria-describedby="series-context-window-help"
              className="flex-1 accent-foreground"
            />
            <span
              data-testid="series-context-window-value"
              className="w-8 text-right text-sm tabular-nums"
            >
              {draft}
            </span>
          </div>
        </Field>
        <p
          id="series-context-window-help"
          className="text-xs leading-relaxed text-muted-foreground"
        >
          {t("series.settings.contextWindow.help")}
        </p>
        {saved !== null && saved > MAX_WINDOW ? (
          <p data-testid="series-context-window-out-of-range" className="text-xs text-amber-600">
            {t("series.settings.contextPreview.savedOutOfRange", {
              value: saved,
              max: MAX_WINDOW,
            })}
          </p>
        ) : null}
        {previewQuery.isLoading ? (
          <p data-testid="series-context-preview-loading" className="text-xs text-muted-foreground">
            {t("series.settings.contextPreview.loading")}
          </p>
        ) : previewQuery.isError ? (
          <p data-testid="series-context-preview-error" className="text-xs text-muted-foreground">
            {t("series.settings.contextPreview.error")}
          </p>
        ) : entry && previewData ? (
          <SeriesContextPreview entry={entry} meta={previewData} />
        ) : null}
      </div>

      {dirty ? (
        <div className="flex justify-end">
          <button
            type="button"
            data-testid="series-context-window-save"
            onClick={handleSave}
            disabled={!canSave || update.isPending}
            className="flex items-center gap-2 rounded-md bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {update.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t("series.settings.save")}
          </button>
        </div>
      ) : null}
    </section>
  );
}
