/**
 * Settings tab — /series/[id]/settings (Spec 1, Slice 4, Task 4.7).
 *
 * Renders the Series metadata form (title, subtitle, description, genre,
 * writing_language, status with transition constraints, planned novel count)
 * plus a disabled Voice subsection (Spec 3). See :component:`SeriesSettings`.
 */
import { use } from "react";
import { SeriesSettings } from "@/components/series/SeriesSettings";

export default function SettingsTabPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <section data-testid="series-settings-tab">
      <SeriesSettings seriesId={id} />
    </section>
  );
}
