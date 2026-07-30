/**
 * Settings tab — /series/[id]/settings (Spec 1, Slice 4, Task 4.6).
 *
 * Placeholder content. Task 4.7 fills this with `<SeriesSettings seriesId={id} />`
 * (metadata form + disabled Voice subsection for Spec 3).
 */

import { useTranslations } from "next-intl";
import { use } from "react";

export default function SettingsTabPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("studio");
  void id; // Task 4.7 renders <SeriesSettings seriesId={id} />
  return (
    <section data-testid="series-settings-tab" className="max-w-3xl">
      <h2 className="text-lg font-medium">{t("series.settings.placeholder")}</h2>
    </section>
  );
}
