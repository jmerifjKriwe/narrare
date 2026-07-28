/**
 * AuthorVoiceDescriptiveSummary — renders the DESCRIPTIVE voice-profile group
 * (ANAL-007 / ADR-074): formality gauge + categorical descriptors + cultural
 * markers.
 *
 * These fields ARE rendered into {{author_voice}} by the Core
 * `render_author_voice_for_generation` (the descriptive/metric boundary's
 * descriptive side). The metric groups live in {@link ./AuthorVoiceAdvancedMetrics}.
 *
 * Mirrors the CharacterVoiceResultCard descriptive layout (ANAL-008), adapted
 * to the author-voice single-profile shape. Extracted per RULE-04.
 */

import type { AuthorVoiceProfile } from "@/lib/api/author-voice-stream";

interface AuthorVoiceDescriptiveSummaryProps {
  profile: AuthorVoiceProfile;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

/** Formality (0.0 casual – 1.0 formal) as a rounded percentage for display. */
function formalityPct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function AuthorVoiceDescriptiveSummary({ profile, t }: AuthorVoiceDescriptiveSummaryProps) {
  const voiceAnalysis = profile.voice_analysis;
  // bool is a subclass of int — exclude it (mirrors the Core renderer).
  const formality =
    voiceAnalysis?.formality != null && typeof voiceAnalysis.formality !== "boolean"
      ? voiceAnalysis.formality
      : null;

  return (
    <section className="rounded-lg border border-border p-4 bg-card space-y-3">
      <h4 className="text-sm font-semibold text-violet-600 dark:text-violet-400">
        {t("authorVoice.descriptiveSummary")}
      </h4>

      {voiceAnalysis ? (
        <div className="space-y-3">
          {/* Formality gauge */}
          {formality != null && (
            <div>
              <div className="flex items-baseline justify-between mb-1">
                <span className="text-xs text-muted-foreground">{t("authorVoice.formality")}</span>
                <span className="text-xs font-medium tabular-nums">{formalityPct(formality)}</span>
              </div>
              <div
                className="w-full h-2 rounded-full bg-muted overflow-hidden"
                role="progressbar"
                aria-valuenow={Math.round(formality * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={t("authorVoice.formality")}
              >
                <div
                  className="h-full rounded-full bg-violet-500 transition-all"
                  style={{ width: `${Math.min(100, Math.max(0, formality * 100))}%` }}
                />
              </div>
              <div className="flex justify-between mt-0.5">
                <span className="text-[10px] text-muted-foreground">
                  {t("authorVoice.formalityCasual")}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {t("authorVoice.formalityFormal")}
                </span>
              </div>
            </div>
          )}

          {/* Categorical profile fields */}
          <dl className="grid grid-cols-1 gap-1.5 text-sm">
            {voiceAnalysis.vocabulary_level && (
              <FieldRow
                label={t("authorVoice.vocabularyLevel")}
                value={voiceAnalysis.vocabulary_level}
              />
            )}
            {voiceAnalysis.sentence_profile && (
              <FieldRow
                label={t("authorVoice.sentenceProfile")}
                value={voiceAnalysis.sentence_profile}
              />
            )}
            {voiceAnalysis.emotional_range && (
              <FieldRow
                label={t("authorVoice.emotionalRange")}
                value={voiceAnalysis.emotional_range}
              />
            )}
          </dl>

          {/* Cultural / regional markers */}
          {voiceAnalysis.cultural_regional_markers && (
            <div>
              <dt className="text-xs text-muted-foreground mb-0.5">
                {t("authorVoice.culturalRegionalMarkers")}
              </dt>
              <dd className="text-sm text-muted-foreground leading-relaxed">
                {voiceAnalysis.cultural_regional_markers}
              </dd>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t("authorVoice.noProfile")}</p>
      )}
    </section>
  );
}

/** Label / value row for a categorical voice field. */
function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-xs text-muted-foreground flex-shrink-0">{label}</dt>
      <dd className="text-sm font-medium text-right">{value}</dd>
    </div>
  );
}
