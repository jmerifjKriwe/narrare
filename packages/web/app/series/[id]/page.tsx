/**
 * Bände tab — default route for /series/[id] (Spec 1, Slice 4, Task 4.7).
 *
 * Renders the ordered novels-in-series list (position pills, novel links,
 * is_demo badges, up/down reorder) plus the "Add Novel" join flow. See
 * :component:`BaendeList`.
 *
 * Spec 4 (Cross-Novel Drift) mounts the `SeriesDriftPanel` as a dedicated
 * section below the list (design D3: integrated in the Bände tab, no separate
 * tab), so `BaendeList` stays single-responsibility (list/reorder only).
 */
import { use } from "react";
import { BaendeList } from "@/components/series/BaendeList";
import { SeriesDriftPanel } from "@/components/series/SeriesDriftPanel";

export default function SeriesBaendePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <section data-testid="series-baende-tab" className="space-y-8">
      <BaendeList seriesId={id} />
      <SeriesDriftPanel seriesId={id} />
    </section>
  );
}
