/**
 * Bände tab — default route for /series/[id] (Spec 1, Slice 4, Task 4.7).
 *
 * Renders the ordered novels-in-series list (position pills, novel links,
 * is_demo badges, up/down reorder) plus the "Add Novel" join flow. See
 * :component:`BaendeList`.
 */
import { use } from "react";
import { BaendeList } from "@/components/series/BaendeList";

export default function SeriesBaendePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <section data-testid="series-baende-tab">
      <BaendeList seriesId={id} />
    </section>
  );
}
