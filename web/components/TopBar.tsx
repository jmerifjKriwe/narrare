import { Link } from "@tanstack/react-router";
import { useState, useSyncExternalStore } from "react";

import { client } from "../lib/api/client";
import { nav } from "../lib/generated/capabilities";
import { catalogs, locales } from "../lib/generated/catalogs";
import { useTranslation } from "../lib/i18n";
import {
  applyLocale,
  chosenLocale,
  subscribeLocale,
  type Locale,
} from "../lib/locale";
import { queryClient } from "../lib/query";

/**
 * One focus treatment for everything interactive in the bar: the ring is the
 * keyboard's pointer, and it must look the same wherever it lands.
 */
const focusRing = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

/** The language control. It lives in the shell, so it exists on every page. */
function LanguageSwitcher() {
  const t = useTranslation();
  const chosen = useSyncExternalStore(subscribeLocale, chosenLocale, chosenLocale);
  const [failed, setFailed] = useState(false);

  async function choose(value: string) {
    const previous = chosenLocale();
    const next: Locale | null = value === "auto" ? null : (value as Locale);
    // Applied first: a local service answers in milliseconds, and the page
    // must not feel like it waits for the write.
    applyLocale(next);
    setFailed(false);
    try {
      const { response } = await client.PATCH("/api/settings", { body: { locale: next } });
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      // The row changed, so the cached answer about it is stale. Invalidate
      // instead of writing the cache by hand (spec 5.10): the refetch brings
      // back exactly what was just persisted, so cache and row cannot
      // disagree.
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      // The write did not happen, so the display must not pretend it did.
      applyLocale(previous);
      setFailed(true);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <label htmlFor="locale" className="text-muted">
        {t("settings.language")}
      </label>
      <select
        id="locale"
        value={chosen ?? "auto"}
        onChange={(event) => void choose(event.target.value)}
        className={`rounded-md border border-border bg-card px-2 py-1 ${focusRing}`}
      >
        {/* "Automatic" is a real choice, not an empty one: it means the row
            holds no preference and the browser decides. */}
        <option value="auto">{t("settings.automatic")}</option>
        {locales.map((code) => (
          <option key={code} value={code}>
            {/* Endonyms: a reader looking for their language finds it written
                in their language, whatever the app currently speaks. */}
            {catalogs[code]["locale.name"]}
          </option>
        ))}
      </select>
      {failed ? (
        <p role="alert" className="text-danger">
          {t("settings.errorSave")}
        </p>
      ) : null}
    </div>
  );
}

/** The shell's chrome: the skip link, the capability navigation, the language. */
export function TopBar() {
  const t = useTranslation();

  return (
    <header className="border-b border-border bg-panel text-sm">
      {/* Hidden from sight until focused, and first in the bar so the first
          Tab finds it. Transform and opacity, not sr-only: the reveal then
          needs no second utility to undo the hiding. The ring is pre-applied
          rather than focus-visible-gated because reveal and focus coincide. */}
      <a
        href="#main"
        className="fixed left-4 top-4 z-20 -translate-y-24 rounded-md bg-card px-3 py-2 text-sm text-foreground opacity-0 outline-none ring-2 ring-focus transition focus:translate-y-0 focus:opacity-100"
      >
        {t("shell.skipToContent")}
      </a>
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-4 px-4 py-3">
        <nav className="flex items-center gap-4">
          {nav.map((entry) => (
            <Link
              key={entry.id}
              to={entry.path}
              className={`rounded-md underline-offset-4 hover:underline ${focusRing}`}
            >
              {t(entry.titleKey)}
            </Link>
          ))}
        </nav>
        <LanguageSwitcher />
      </div>
    </header>
  );
}
