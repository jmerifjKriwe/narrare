/**
 * CharacterVoiceResultCard — renders ONE character's voice profile (ANAL-008).
 *
 * Shows the persisted descriptive voice-analysis group (formality, vocabulary
 * level, sentence profile, emotional range, cultural/regional markers, curated
 * example quotes) plus the per-run, DISPLAY-ONLY {@link distinctivenessNotes}
 * callout (ADR-055 Decision 1 — never persisted, recomputed each run).
 *
 * Extracted per RULE-04. `voice_metrics` (the deterministic comparison block) is
 * intentionally NOT rendered here — it is for ANAL-009/WRITE-010, not the panel.
 */

import { Info } from "lucide-react";
import type { CharacterVoiceResult } from "@/lib/api/character-voice-stream";

interface CharacterVoiceResultCardProps {
  result: CharacterVoiceResult;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

/** Formality (0.0 casual – 1.0 formal) as a rounded percentage for display. */
function formalityPct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function CharacterVoiceResultCard({ result, t }: CharacterVoiceResultCardProps) {
  const {
    character_name: name,
    voice_analysis: profile,
    distinctiveness_notes: distinctiveness,
  } = result;
  const formality = profile?.formality ?? null;
  const examples = profile?.voice_examples ?? null;

  return (
    <section
      className="rounded-lg border border-border p-4 bg-card space-y-3"
      aria-label={name || t("characterVoice.title")}
    >
      <h4 className="text-sm font-semibold text-violet-600 dark:text-violet-400">
        {name || "\u2014"}
      </h4>

      {profile ? (
        <div className="space-y-3">
          {/* Formality gauge */}
          {formality != null && (
            <div>
              <div className="flex items-baseline justify-between mb-1">
                <span className="text-xs text-muted-foreground">
                  {t("characterVoice.formality")}
                </span>
                <span className="text-xs font-medium tabular-nums">{formalityPct(formality)}</span>
              </div>
              <div
                className="w-full h-2 rounded-full bg-muted overflow-hidden"
                role="progressbar"
                aria-valuenow={Math.round(formality * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={t("characterVoice.formality")}
              >
                <div
                  className="h-full rounded-full bg-violet-500 transition-all"
                  style={{ width: `${Math.min(100, Math.max(0, formality * 100))}%` }}
                />
              </div>
              <div className="flex justify-between mt-0.5">
                <span className="text-[10px] text-muted-foreground">
                  {t("characterVoice.formalityCasual")}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {t("characterVoice.formalityFormal")}
                </span>
              </div>
            </div>
          )}

          {/* Categorical profile fields */}
          <dl className="grid grid-cols-1 gap-1.5 text-sm">
            {profile.vocabulary_level && (
              <FieldRow
                label={t("characterVoice.vocabularyLevel")}
                value={profile.vocabulary_level}
              />
            )}
            {profile.sentence_profile && (
              <FieldRow
                label={t("characterVoice.sentenceProfile")}
                value={profile.sentence_profile}
              />
            )}
            {profile.emotional_range && (
              <FieldRow
                label={t("characterVoice.emotionalRange")}
                value={profile.emotional_range}
              />
            )}
          </dl>

          {/* Cultural / regional markers */}
          {profile.cultural_regional_markers && (
            <div>
              <dt className="text-xs text-muted-foreground mb-0.5">
                {t("characterVoice.culturalRegionalMarkers")}
              </dt>
              <dd className="text-sm text-muted-foreground leading-relaxed">
                {profile.cultural_regional_markers}
              </dd>
            </div>
          )}

          {/* Curated example dialogue */}
          {examples && examples.length > 0 && (
            <div>
              <dt className="text-xs text-muted-foreground mb-1">
                {t("characterVoice.voiceExamples")}
              </dt>
              <dd className="space-y-1">
                {examples.map((quote) => (
                  <blockquote
                    key={quote}
                    className="border-l-2 border-violet-300 dark:border-violet-700 pl-2 text-sm italic text-muted-foreground"
                  >
                    {quote}
                  </blockquote>
                ))}
              </dd>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t("characterVoice.noVoiceProfile")}</p>
      )}

      {/* Per-run distinctiveness comparison — DISPLAY ONLY (ADR-055 Decision 1). */}
      {distinctiveness && (
        <div
          className="rounded-md border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/20 px-3 py-2"
          role="note"
        >
          <div className="flex items-center gap-1.5 mb-0.5">
            <Info className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <span className="text-xs font-medium text-amber-800 dark:text-amber-300">
              {t("characterVoice.distinctivenessNotes")}
            </span>
          </div>
          <p className="text-sm text-amber-900 dark:text-amber-100 leading-relaxed">
            {distinctiveness}
          </p>
          <p className="text-[10px] text-amber-700/80 dark:text-amber-400/70 mt-1">
            {t("characterVoice.distinctivenessCaveat")}
          </p>
        </div>
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
