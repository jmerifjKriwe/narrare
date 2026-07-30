/**
 * Voice tab — /series/[id]/voice (Spec 1, Slice 4, Task 4.6).
 *
 * Disabled placeholder for the Series Voice Hierarchy, which is implemented in
 * Spec 3. The tab itself is non-navigable in SeriesWorkspace; this route exists
 * only so a direct/deep link lands on an explanatory page instead of a 404.
 */
import { useTranslations } from "next-intl";

export default function VoiceTabPage() {
  const t = useTranslations("studio");
  return (
    <section data-testid="series-voice-tab" className="max-w-3xl">
      <h2 className="text-lg font-medium">{t("series.voice.title")}</h2>
      <p className="mt-2 text-muted-foreground">{t("series.voice.comingInSpec3")}</p>
    </section>
  );
}
