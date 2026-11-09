import { LanguageSwitcher } from "@shell/components/LanguageSwitcher";
import { useTranslation } from "@shell/lib/i18n";
import { activeLocale, subscribeLocale } from "@shell/lib/locale";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useSyncExternalStore } from "react";

/**
 * The language cluster's page: the bar's own control, reused here — one
 * language surface, not two implementations of it. The bar keeps the quick
 * switch; this page is where the choice is explained by being the only
 * thing on it. The page is a section under an <h2> with no container of
 * its own — the frame owns the shape; the tab names the cluster itself.
 */
export function LanguagePage() {
  const t = useTranslation();
  const locale = useSyncExternalStore(subscribeLocale, activeLocale, activeLocale);
  // The tab's name: this page is "Sprache", not the area's name — a
  // sub-page owns its own, the way the prompts page does.
  usePageTitle(t("settings.language"));

  return (
    <section aria-labelledby="settings-language-heading">
      <h2 id="settings-language-heading" className="text-emph font-semibold">
        {t("settings.language")}
      </h2>
      <div className="mt-3">
        <LanguageSwitcher />
        {locale !== "en" ? (
          <p className="mt-2 text-caption text-muted">
            {t("settings.formality.hint")}
          </p>
        ) : null}
      </div>
    </section>
  );
}
