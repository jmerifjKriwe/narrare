"use client";

/**
 * SeriesContextWindowField — editor for the Series recency-window setting
 * (Spec 2: ``context_window_size``).
 *
 * Separate from :component:`SeriesMetadataForm` because the setting persists
 * to a distinct endpoint (PATCH ``/series/{id}/settings``) — mixing it into
 * the metadata form would couple two PATCH surfaces behind one Save button.
 * The component owns its own local state, dirty-gated Save, and loading /
 * error states, mirroring the NovelDetailsTab / SeriesMetadataForm pattern.
 *
 * Input choice — number input (not slider):
 *  • Consistency: ``planned_novel_count`` in the same tab uses a number input;
 *    a slider here would break the form's visual language.
 *  • Precision: the value controls token cost + AI memory budget, so users
 *    need an exact integer, not the approximation a slider implies.
 *  • Accessibility: native number input ships keyboard nav,
 *    screen-reader semantics, and a mobile numeric keypad for free.
 * Bounds [1, 50] match the backend ``SeriesSettingsUpdateRequest`` validation.
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useSeriesSettings, useUpdateSeriesSettings } from "@/lib/hooks/useSeries";
import { SeriesField as Field } from "./SeriesField";

interface SeriesContextWindowFieldProps {
  readonly seriesId: string;
}

const MIN_WINDOW = 1;
const MAX_WINDOW = 50;

export function SeriesContextWindowField({ seriesId }: SeriesContextWindowFieldProps) {
  const t = useTranslations("studio");
  const { data: settings, isLoading, isError } = useSeriesSettings(seriesId);
  const update = useUpdateSeriesSettings(seriesId);

  const [value, setValue] = useState("");
  const [dirty, setDirty] = useState(false);

  // Re-sync from server data only while clean — mirrors SeriesMetadataForm's
  // dirty guard so a background refetch (new object identity) can't clobber
  // the user's in-flight edit.
  useEffect(() => {
    if (dirty) return;
    if (settings) setValue(String(settings.context_window_size));
  }, [settings, dirty]);

  function isValidWindow(raw: string): boolean {
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed >= MIN_WINDOW && parsed <= MAX_WINDOW;
  }

  function handleSave(): void {
    if (!isValidWindow(value)) return;
    const parsed = Number(value);
    // No-op if unchanged (e.g. user typed the same value back).
    if (settings && parsed === settings.context_window_size) {
      setDirty(false);
      return;
    }
    update.mutate({ context_window_size: parsed }, { onSuccess: () => setDirty(false) });
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

  const inputClass =
    "w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";
  const label = t("series.settings.contextWindow.label");
  const canSave = dirty && isValidWindow(value);

  return (
    <section data-testid="series-context-window" className="space-y-4">
      <div className="space-y-2 rounded-lg border border-border bg-card p-6">
        <Field label={label}>
          <input
            data-testid="series-context-window-input"
            type="number"
            min={MIN_WINDOW}
            max={MAX_WINDOW}
            step={1}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setDirty(true);
            }}
            aria-label={label}
            aria-describedby="series-context-window-help"
            className={inputClass}
          />
        </Field>
        <p
          id="series-context-window-help"
          className="text-xs leading-relaxed text-muted-foreground"
        >
          {t("series.settings.contextWindow.help")}
        </p>
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
