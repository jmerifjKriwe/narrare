"use client";

/**
 * SeriesSettings — the "Settings" tab body (Spec 1, Slice 4, Task 4.7).
 *
 * Orchestrator only: fetches the Series via `useSeries`, renders loading /
 * error states (quality bar §error-states), and delegates the editable form to
 * :component:`SeriesMetadataForm` (RULE-04: one responsibility per file — the
 * form + save logic live there). All copy via `useTranslations("studio")`
 * under `series.settings.*` (keys added by Task 4.9; none hardcoded).
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSeries } from "@/lib/hooks/useSeries";
import { SeriesContextWindowField } from "./SeriesContextWindowField";
import { SeriesMetadataForm } from "./SeriesMetadataForm";

interface SeriesSettingsProps {
  readonly seriesId: string;
}

export function SeriesSettings({ seriesId }: SeriesSettingsProps) {
  const t = useTranslations("studio");
  const { data: series, isLoading, isError } = useSeries(seriesId);

  if (isLoading) {
    return (
      <div
        data-testid="series-settings-loading"
        className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"
      >
        <Loader2 className="h-5 w-5 animate-spin" />
        {t("series.settings.loading")}
      </div>
    );
  }

  if (isError || !series) {
    return (
      <div
        data-testid="series-settings-error"
        className="py-12 text-center text-sm text-muted-foreground"
      >
        {t("series.settings.error")}
      </div>
    );
  }

  return (
    <section data-testid="series-settings" className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-xl font-medium">{t("series.settings.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("series.settings.description")}</p>
      </div>
      {/* `key` on series.id re-mounts the form when switching series so local
          form state re-initializes cleanly instead of partially syncing. */}
      <SeriesMetadataForm key={series.id} series={series} />
      {/* Generation setting — persisted to a distinct endpoint
          (/series/{id}/settings), so it owns its own Save button. */}
      <SeriesContextWindowField key={`cw-${series.id}`} seriesId={series.id} />
    </section>
  );
}
