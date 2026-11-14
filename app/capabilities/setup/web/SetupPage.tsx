import { useTranslation } from "@shell/lib/i18n";

/**
 * The interim placeholder: the whole UI is being demolished and rebuilt
 * from the Stitch drafts, and this page is the state the app boots to
 * until the rebuilt screens land — it owns `/` and `/setup`. Render-only
 * on purpose: no form, no logic, no unit test owed (TESTING.md); the
 * setup flow returns with the rebuilt wizard. Neutral tokens only — this
 * page is the approved interim state, not a design.
 */
export function SetupPage() {
  const t = useTranslation();
  return (
    <div className="mx-auto w-full max-w-112 px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("setup.interimTitle")}</h1>
      <p className="mt-2 text-body text-muted">{t("setup.interimBody")}</p>
    </div>
  );
}
