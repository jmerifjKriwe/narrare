/**
 * VoiceCheckResultCard — renders ONE character's voice-check result (WRITE-010).
 *
 * Shows the blended match score (color-coded by band), the agent's qualitative
 * judgment, the qualitative + metric-delta sub-scores, the number of comparable
 * metrics, and each flagged dialogue line with its profile-grounded reason.
 *
 * Graceful states (RULE-11):
 *  - `has_profile === false` → "no voice profile" note (no score block).
 *  - `has_profile === true` but unscorable (`match_score === null`) → "not scored".
 *
 * Every field is a display-only report artifact — the checker is read-only
 * (ADR-057 Decision 5); nothing here is persisted.
 *
 * Extracted per RULE-04. `t` is the scoped `analysis` translator (same prop
 * contract as CharacterVoiceResultCard).
 */

import type { VoiceCheckBand, VoiceCheckResult } from "@/lib/api/voice-check-stream";

interface VoiceCheckResultCardProps {
  result: VoiceCheckResult;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

// Band → badge pill classes (color-coded severity, ADR-057 Decision 2 thresholds).
const BAND_BADGE: Record<VoiceCheckBand, string> = {
  green: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  yellow: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  fair: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  red: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
};

// Band → progressbar fill colour.
const BAND_BAR: Record<VoiceCheckBand, string> = {
  green: "bg-emerald-500",
  yellow: "bg-yellow-500",
  fair: "bg-amber-500",
  red: "bg-red-500",
};

export function VoiceCheckResultCard({ result, t }: VoiceCheckResultCardProps) {
  const {
    character_name: name,
    match_score: score,
    band,
    match_judgment: judgment,
    qualitative_sub_score: qualitative,
    metric_delta_subscore: metricDelta,
    flagged_lines: flagged,
    has_profile: hasProfile,
    n_comparable_metrics: nComparable,
  } = result;

  const scored = hasProfile && score != null;
  const roundedScore = score != null ? Math.round(score) : null;
  const pct = roundedScore != null ? Math.min(100, Math.max(0, roundedScore)) : 0;

  return (
    <section
      className="rounded-lg border border-border p-4 bg-card space-y-3"
      aria-label={name || t("voiceCheck.title")}
    >
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-violet-600 dark:text-violet-400">
          {name || "\u2014"}
        </h4>
        {band && (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${BAND_BADGE[band]}`}
          >
            {t(`voiceCheck.band.${band}`)}
          </span>
        )}
      </div>

      {!hasProfile ? (
        <p className="text-sm text-muted-foreground">{t("voiceCheck.noVoiceProfile")}</p>
      ) : (
        <div className="space-y-3">
          {/* Match score gauge (or "not scored" when unscorable). */}
          {scored && roundedScore != null ? (
            <div>
              <div className="flex items-baseline justify-between mb-1">
                <span className="text-xs text-muted-foreground">{t("voiceCheck.matchScore")}</span>
                <span className="text-xs font-medium tabular-nums">
                  {t("voiceCheck.matchScoreValue", { score: roundedScore })}
                </span>
              </div>
              <div
                className="w-full h-2 rounded-full bg-muted overflow-hidden"
                role="progressbar"
                aria-valuenow={roundedScore}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={t("voiceCheck.matchScore")}
              >
                <div
                  className={`h-full rounded-full transition-all ${band ? BAND_BAR[band] : "bg-violet-500"}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{t("voiceCheck.noScore")}</p>
          )}

          {/* Qualitative judgment. */}
          {judgment && (
            <p className="text-sm text-muted-foreground">{t(`voiceCheck.judgment.${judgment}`)}</p>
          )}

          {/* Sub-scores. */}
          {(qualitative != null || metricDelta != null) && (
            <dl className="grid grid-cols-1 gap-1.5 text-sm">
              {qualitative != null && (
                <FieldRow
                  label={t("voiceCheck.qualitativeSubScore")}
                  value={`${Math.round(qualitative)}%`}
                />
              )}
              {metricDelta != null && (
                <FieldRow
                  label={t("voiceCheck.metricDeltaSubScore")}
                  value={`${Math.round(metricDelta)}%`}
                />
              )}
            </dl>
          )}

          {/* Comparable-metrics count. */}
          <p className="text-xs text-muted-foreground">
            {t("voiceCheck.nComparableMetrics", { count: nComparable })}
          </p>

          {/* Flagged dialogue lines. */}
          {flagged.length > 0 && (
            <div>
              <dt className="text-xs text-muted-foreground mb-1">
                {t("voiceCheck.flaggedLines", { count: flagged.length })}
              </dt>
              <dd className="space-y-2">
                {flagged.map((line) => (
                  <div
                    key={line.quote}
                    className="rounded-md border border-border bg-muted/30 px-3 py-2"
                  >
                    <blockquote className="border-l-2 border-violet-300 dark:border-violet-700 pl-2 text-sm italic text-muted-foreground">
                      {line.quote}
                    </blockquote>
                    <p className="text-xs text-muted-foreground mt-1 flex gap-1">
                      <span className="font-medium flex-shrink-0">
                        {t("voiceCheck.flaggedLineReason")}
                      </span>
                      <span>{line.reason}</span>
                    </p>
                  </div>
                ))}
              </dd>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

/** Label / value row for a sub-score. */
function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-xs text-muted-foreground flex-shrink-0">{label}</dt>
      <dd className="text-sm font-medium tabular-nums text-right">{value}</dd>
    </div>
  );
}
