import { Link } from "@tanstack/react-router";

import { LanguageSwitcher } from "@shell/components/LanguageSwitcher";
import { useTranslation } from "@shell/lib/i18n";

import { ProvidersPanel } from "./ProvidersPanel";

/**
 * The settings destination: the language and the provider profiles. The top
 * bar's gear is the door; the quick switch stays in the bar for the language
 * alone.
 */
export function SettingsPage() {
  const t = useTranslation();

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("settings.heading")}</h1>
      <p className="mt-2 text-sm text-muted">
        <Link to="/" className="underline-offset-4 hover:underline">
          {t("settings.back")}
        </Link>
      </p>

      <section className="mt-8" aria-labelledby="settings-language-heading">
        <h2 id="settings-language-heading" className="text-lg font-semibold">
          {t("settings.language")}
        </h2>
        {/* The bar's own control, reused here: one language surface, not two
            implementations of it. */}
        <div className="mt-3">
          <LanguageSwitcher />
        </div>
      </section>

      <ProvidersPanel />
    </div>
  );
}
