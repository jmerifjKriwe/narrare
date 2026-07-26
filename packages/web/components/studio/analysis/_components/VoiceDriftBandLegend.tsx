/**
 * VoiceDriftBandLegend — the band + jump-point legend (ANAL-009 Layout γ).
 *
 * Renders the four drift bands (symbol + label + match-score range) and the
 * ⚡ jump-point key. Shared under the heatmap overview so the colour code is
 * explained once. Purely presentational — mirrors the approved mockup's
 * "mini-legend".
 *
 * `t` is the scoped `analysis` translator (same prop contract as the sibling
 * VoiceCheckResults / CharacterVoiceResults).
 *
 * @module VoiceDriftBandLegend
 */

import { DRIFT_BAND_ORDER, DRIFT_BANDS } from "./voice-drift-bands";

interface VoiceDriftBandLegendProps {
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

/** Match-score range caption per band (caption key: `voiceDrift.bandRange.{label}`). */
const RANGE_KEYS = {
  stable: "stable",
  minor: "minor",
  moderate: "moderate",
  major: "major",
} as const;

export function VoiceDriftBandLegend({ t }: VoiceDriftBandLegendProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-dashed border-border bg-muted/20 px-4 py-3">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {t("voiceDrift.bandsLabel")}
      </span>
      {DRIFT_BAND_ORDER.map((band) => {
        const meta = DRIFT_BANDS[band];
        return (
          <span
            key={band}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span
              className={`inline-block h-2.5 w-2.5 rounded-sm ${meta.cellBg} ${meta.cellBorder} border`}
              aria-hidden
            />
            <span className={meta.text}>{meta.symbol}</span>
            <span>{t(`voiceDrift.band.${meta.label}`)}</span>
            <span className="text-muted-foreground/70">
              {t(`voiceDrift.bandRange.${RANGE_KEYS[band]}`)}
            </span>
          </span>
        );
      })}
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <span aria-hidden>{"\u26A1"}</span>
        <span>{t("voiceDrift.jumpKey")}</span>
      </span>
    </div>
  );
}
