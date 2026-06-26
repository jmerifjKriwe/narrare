/**
 * CoreferenceResults — renders the full coreference results view:
 * clarity-score gauge, summary, pronoun-resolution table, and character
 * mentions with POV indicators.
 *
 * Extracted from {@link ../CoreferencePanel} per RULE-04 (file-size limit).
 */

import type { CoreferenceResult } from "@/lib/api/coreference-stream";

interface CoreferenceResultsProps {
  result: CoreferenceResult;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

/** Confidence as a rounded percentage for display. */
function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** Tailwind classes for the clarity gauge based on score thresholds. */
function clarityTone(score: number): string {
  if (score >= 75) return "bg-emerald-500";
  if (score >= 50) return "bg-amber-500";
  return "bg-red-500";
}

export function CoreferenceResults({ result, t }: CoreferenceResultsProps) {
  const score = Math.round(result.clarity_score);

  return (
    <>
      {/* Clarity score gauge */}
      <section
        className="rounded-lg border border-border p-4 bg-card"
        aria-label={t("coreference.clarityScore")}
      >
        <div className="flex items-baseline justify-between mb-2">
          <span className="text-xs text-muted-foreground">{t("coreference.clarityScore")}</span>
          <span className="text-2xl font-semibold tabular-nums">{score}</span>
        </div>
        <div
          className="w-full h-2 rounded-full bg-muted overflow-hidden"
          role="progressbar"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={t("coreference.clarityScore")}
        >
          <div
            className={`h-full rounded-full transition-all ${clarityTone(score)}`}
            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
          />
        </div>
      </section>

      {/* Summary */}
      {result.summary && (
        <section>
          <h4 className="text-sm font-medium mb-1">{t("coreference.summary")}</h4>
          <p className="text-sm text-muted-foreground leading-relaxed">{result.summary}</p>
        </section>
      )}

      {/* Pronoun resolutions */}
      <section>
        <h4 className="text-sm font-medium mb-2">{t("coreference.resolutions")}</h4>
        {result.resolutions.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("coreference.noResults")}</p>
        ) : (
          <div className="space-y-1.5">
            {result.resolutions.map((r) => (
              <div
                key={`res-${r.position}-${r.pronoun}`}
                className="flex items-center gap-2 rounded-md border border-border px-3 py-2 bg-background text-sm"
              >
                <span className="font-medium italic min-w-[3rem]">{r.pronoun || "—"}</span>
                <span className="text-muted-foreground">→</span>
                <span className="flex-1 truncate">{r.referent || "—"}</span>
                <span className="text-xs text-muted-foreground tabular-nums">
                  {pct(r.confidence)}
                </span>
                {r.is_ambiguous && (
                  <span className="px-1.5 py-0.5 text-[10px] rounded bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                    {t("coreference.ambiguous")}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Character mentions */}
      <section>
        <h4 className="text-sm font-medium mb-2">{t("coreference.characterMentions")}</h4>
        {result.character_mentions.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("coreference.noMentions")}</p>
        ) : (
          <div className="space-y-1.5">
            {result.character_mentions.map((m) => (
              <div
                key={`char-${m.character_name}`}
                className="flex items-center gap-2 rounded-md border border-border px-3 py-2 bg-background text-sm"
              >
                <span className="flex-1 truncate font-medium">{m.character_name || "—"}</span>
                {m.is_pov && (
                  <span className="px-1.5 py-0.5 text-[10px] rounded bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
                    {t("coreference.pov")}
                  </span>
                )}
                <span className="text-xs text-muted-foreground tabular-nums">
                  {t("coreference.mentions", { count: m.mentions.length })}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
