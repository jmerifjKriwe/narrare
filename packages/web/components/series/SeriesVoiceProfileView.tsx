"use client";

/**
 * SeriesVoiceProfileView — read-only display of a stored series-voice profile
 * (Spec 3, Tasks 5–6).
 *
 * Renders ONLY the ADR-074 descriptive group: ``voice_analysis`` descriptive
 * fields (vocabulary level, sentence profile, emotional range, markers, voice
 * examples) and the curated ``author_examples``. The metric blocks
 * (``voice_analysis.voice_metrics`` and ``author_metrics``) are
 * comparison-only and are NEVER rendered here — the boundary is enforced at
 * the consumer contract, mirrored from the Core
 * :func:`render_author_voice_for_generation` renderer.
 *
 * Pure presentational component (no hooks). All copy via
 * ``useTranslations("studio")`` under ``series.voice.*``.
 */
import { useTranslations } from "next-intl";
import type { SeriesVoiceProfile } from "@/types";

interface SeriesVoiceProfileViewProps {
  readonly profile: SeriesVoiceProfile;
}

/** A labelled line shown only when the value is non-empty. */
function Line({ label, value }: { label: string; value: string | undefined | null }) {
  if (!value || value.trim() === "") return null;
  return (
    <p className="text-xs text-foreground">
      <span className="font-medium text-muted-foreground">{label}:</span> {value}
    </p>
  );
}

export function SeriesVoiceProfileView({ profile }: SeriesVoiceProfileViewProps) {
  const t = useTranslations("studio");
  const va = profile.voice_analysis ?? undefined;

  const voiceExamples = va?.voice_examples ?? [];
  const authorExamples = profile.author_examples ?? [];
  const hasDescriptive =
    Boolean(va?.vocabulary_level) ||
    Boolean(va?.sentence_profile) ||
    Boolean(va?.emotional_range) ||
    Boolean(va?.cultural_regional_markers) ||
    voiceExamples.length > 0 ||
    authorExamples.length > 0;

  if (!hasDescriptive) {
    return (
      <div
        data-testid="series-voice-profile-empty"
        className="rounded-md border border-dashed border-border bg-muted/30 p-4 text-xs text-muted-foreground"
      >
        {t("series.voice.profileEmpty")}
      </div>
    );
  }

  const updatedAt = profile.updated_at ? new Date(profile.updated_at).toLocaleString() : null;
  // Dedupe identical prose (curated examples) so content-based React keys stay
  // unique — the strings carry no stable id (biome: noArrayIndexKey).
  const uniq = (xs: string[]) => Array.from(new Set(xs.filter((x) => x?.trim())));

  return (
    <div
      data-testid="series-voice-profile"
      className="space-y-2 rounded-md border border-border bg-card p-4"
    >
      <h3 className="text-xs font-semibold text-foreground">{t("series.voice.showProfile")}</h3>
      {updatedAt ? (
        <div
          data-testid="series-voice-profile-updated-at"
          className="text-[10px] text-muted-foreground"
        >
          {t("series.voice.profiledAt", { date: updatedAt })}
        </div>
      ) : null}

      <Line label={t("series.voice.fields.vocabularyLevel")} value={va?.vocabulary_level} />
      <Line label={t("series.voice.fields.sentenceProfile")} value={va?.sentence_profile} />
      <Line label={t("series.voice.fields.emotionalRange")} value={va?.emotional_range} />
      <Line label={t("series.voice.fields.markers")} value={va?.cultural_regional_markers} />

      {voiceExamples.length > 0 ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">
            {t("series.voice.fields.voiceExamples")}
          </p>
          <ul className="ml-4 list-disc text-xs text-foreground">
            {uniq(voiceExamples).map((ex) => (
              <li key={ex}>{ex}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {authorExamples.length > 0 ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">
            {t("series.voice.fields.authorExamples")}
          </p>
          <ul className="ml-4 list-disc text-xs text-foreground">
            {uniq(authorExamples).map((ex) => (
              <li key={`ae-${ex}`}>{ex}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
