"use client";

/**
 * SeriesVoicePlaceholder — disabled Voice subsection (Spec 1, Slice 4, Task 4.7).
 *
 * Extracted from SeriesMetadataForm (RULE-04). The author-voice settings land
 * in Spec 3 (`SeriesSettings.author_voice`); until then this renders a clearly
 * disabled placeholder so users see the section exists. Copy via
 * `useTranslations("studio")` under `series.settings.voice.*`.
 */
import { useTranslations } from "next-intl";

export function SeriesVoicePlaceholder() {
  const t = useTranslations("studio");
  return (
    <div
      data-testid="series-settings-voice-placeholder"
      className="space-y-1 rounded-lg border border-dashed border-border bg-muted/30 p-6 opacity-70"
    >
      <h3 className="font-medium">{t("series.settings.voice.title")}</h3>
      <p className="text-sm text-muted-foreground">{t("series.settings.voice.comingInSpec3")}</p>
    </div>
  );
}
