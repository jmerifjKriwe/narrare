/**
 * Bände tab — default route for /series/[id] (Spec 1, Slice 4, Task 4.6).
 *
 * Placeholder content. Task 4.7 replaces the body with
 * `<BändeList seriesId={id} />` (ordered novels with position pills + reorder).
 */

import { useTranslations } from "next-intl";
import { use } from "react";

export default function SeriesBaendePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("studio");
  void id; // Task 4.7 renders <BändeList seriesId={id} />
  return (
    <section data-testid="series-baende-tab" className="max-w-3xl">
      <h2 className="text-lg font-medium">{t("series.baende.placeholder")}</h2>
    </section>
  );
}
