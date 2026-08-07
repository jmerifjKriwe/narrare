"use client";

/**
 * SeriesDriftSummary — renders the series-scope voice-drift result for one band
 * (Spec 4 Task 4).
 *
 * Pure presentational component. The series voice-drift endpoint reuses the
 * novel-level response shape (AuthorVoiceDriftResponse), so exactly one of
 * ``result`` / ``no_profile`` is set:
 *
 * - ``no_profile`` → the RULE-11 graceful skip (the series voice could not be
 *   analysed); rendered as an explanatory note.
 * - ``result`` with an ``overall_band`` of ``stable`` (or unscorable) → the
 *   positive "no drift" state.
 * - ``result`` with a non-stable band (minor / moderate / major) → the drift
 *   warnings: a band badge, the agent's longitudinal classification, the
 *   concrete reasons, and the chapters most worth review.
 *
 * All copy via ``useTranslations("studio")`` under ``series.drift.*``.
 */
import { useTranslations } from "next-intl";
import type { VoiceDriftBand } from "@/lib/api/voice-drift-stream";
import type { SeriesVoiceDriftResult } from "@/types";

interface SeriesDriftSummaryProps {
  /** The series-scope voice-drift response (result XOR no_profile is set). */
  readonly response: SeriesVoiceDriftResult;
}

const DRIFT_BANDS: readonly VoiceDriftBand[] = ["minor", "moderate", "major"];

function bandBadgeClass(band: VoiceDriftBand): string {
  switch (band) {
    case "minor":
      return "bg-amber-500/15 text-amber-700 dark:text-amber-400";
    case "moderate":
      return "bg-orange-500/15 text-orange-700 dark:text-orange-400";
    case "major":
      return "bg-destructive/15 text-destructive";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export function SeriesDriftSummary({ response }: SeriesDriftSummaryProps) {
  const t = useTranslations("studio");

  if (response.no_profile) {
    const reasonKey = `series.drift.noProfileReason.${response.no_profile.reason}`;
    return (
      <p
        data-testid="series-drift-no-profile"
        className="rounded-md border border-dashed p-4 text-sm text-muted-foreground"
      >
        {t(reasonKey)}
      </p>
    );
  }

  const result = response.result;
  const band = result?.overall_band ?? null;
  const hasDrift = band !== null && DRIFT_BANDS.includes(band);

  if (!result || !hasDrift) {
    return (
      <p
        data-testid="series-drift-empty"
        className="rounded-md border border-dashed p-4 text-sm text-muted-foreground"
      >
        {t("series.drift.noDrift")}
      </p>
    );
  }

  return (
    <div data-testid="series-drift-warnings" className="space-y-2">
      <div className="flex items-center gap-2">
        <span
          data-testid={`series-drift-band-${band}`}
          className={`rounded px-1.5 py-0.5 text-xs font-medium ${bandBadgeClass(band)}`}
        >
          {t(`series.drift.band.${band}`)}
        </span>
        <span className="text-sm text-foreground">
          {t(`series.drift.driftType.${result.drift.drift_type}`)}
        </span>
      </div>

      {result.drift.longitudinal_reasons.length > 0 ? (
        <div data-testid="series-drift-reasons" className="space-y-1">
          <p className="text-xs font-medium text-foreground/70">{t("series.drift.reasons")}</p>
          <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
            {result.drift.longitudinal_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {result.drift.suggested_attention.length > 0 ? (
        <p data-testid="series-drift-attention" className="text-sm text-muted-foreground">
          <span className="text-foreground/70">{t("series.drift.attention")}:</span>{" "}
          {result.drift.suggested_attention.join(", ")}
        </p>
      ) : null}
    </div>
  );
}
