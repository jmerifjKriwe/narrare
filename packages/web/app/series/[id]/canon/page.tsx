/**
 * Canon KB tab — /series/[id]/canon (Spec 1, Slice 4, Task 4.6).
 *
 * Placeholder content. Slice 5 (Task 5.5) fills this with the Series-Canon KB
 * editor (reusing the existing KBEditor with a series scope).
 */
import { useTranslations } from "next-intl";

export default function CanonTabPage() {
  const t = useTranslations("studio");
  return (
    <section data-testid="series-canon-tab" className="max-w-3xl">
      <p className="text-muted-foreground">{t("series.canon.comingInSlice5")}</p>
    </section>
  );
}
