import { LanguageSwitcher } from "@shell/components/LanguageSwitcher";
import { useTranslation } from "@shell/lib/i18n";

/**
 * The language cluster's page: the bar's own control, reused here — one
 * language surface, not two implementations of it. The bar keeps the quick
 * switch; this page is where the choice is explained by being the only
 * thing on it.
 */
export function LanguagePage() {
  const t = useTranslation();

  return (
    <section className="mt-8" aria-labelledby="settings-language-heading">
      <h2 id="settings-language-heading" className="text-lg font-semibold">
        {t("settings.language")}
      </h2>
      <div className="mt-3">
        <LanguageSwitcher />
      </div>
    </section>
  );
}
