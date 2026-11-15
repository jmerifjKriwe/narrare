import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";

/**
 * The interim shelf placeholder — the W0 SetupPage precedent: a simple page
 * naming what is coming, neutral tokens only, render-only on purpose (no
 * form, no logic, no unit test owed — TESTING.md). The writing capability
 * owns `/` after the W3 handover; this is the state the set-up instance
 * boots to until Task 6 ports the real shelf from the Stitch drafts onto
 * this page's shoulders. The gate that guards it (routes.tsx) is the logic
 * the route tests pin; this face only names the interim state.
 */
export function ShelfPage() {
  const t = useTranslation();
  usePageTitle(t("novels.heading"));
  return (
    <div className="mx-auto w-full max-w-112 px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("writing.interimTitle")}</h1>
      <p className="mt-2 text-body text-muted">{t("writing.interimBody")}</p>
    </div>
  );
}
