import { useId, useState, useSyncExternalStore } from "react";

import { client } from "../lib/api/client";
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
 * keyboard's pointer, and it must look the same wherever it lands. It lives
 * beside the switcher (the one piece extracted out of the bar) so the bar can
 * import both from one place without a cycle.
 */
export const focusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

/** The language control. It lives in the shell, so it exists on every page. */
export function LanguageSwitcher() {
  const t = useTranslation();
  // The control exists twice on /settings (the bar's quick switch and the
  // page's own section), so the id that ties label to select must be unique
  // per instance — a hardcoded id would collide there and break both labels.
  const id = useId();
  const chosen = useSyncExternalStore(subscribeLocale, chosenLocale, chosenLocale);
  const [failed, setFailed] = useState(false);

  /** Apply and persist a locale (`auto` clears it); restore the prior choice if saving fails. */
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
      <label htmlFor={id} className="text-muted">
        {t("settings.language")}
      </label>
      <select
        id={id}
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
