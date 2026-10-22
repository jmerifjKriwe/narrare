import { createRootRoute, Outlet } from "@tanstack/react-router";
import { useEffect, useState, useSyncExternalStore } from "react";

import { client } from "../lib/api/client";
import { catalogs, locales } from "../lib/generated/catalogs";
import { useTranslation } from "../lib/i18n";
import {
  adoptServerLocale,
  applyLocale,
  chosenLocale,
  subscribeLocale,
  type Locale,
} from "../lib/locale";
import "../globals.css";

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
    } catch {
      // The write did not happen, so the display must not pretend it did.
      applyLocale(previous);
      setFailed(true);
    }
  }

  return (
    <div className="fixed right-4 top-4 z-10 flex items-center gap-2 text-sm">
      <label htmlFor="locale" className="text-muted">
        {t("settings.language")}
      </label>
      <select
        id="locale"
        value={chosen ?? "auto"}
        onChange={(event) => void choose(event.target.value)}
        className="rounded-md border border-border bg-card px-2 py-1 text-sm"
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

/** The one shell: every route renders inside it. */
function Shell() {
  const t = useTranslation();
  // The language is user data on the server, so the first paint waits for it.
  // Rendering first and switching after would flash the wrong language on
  // every load, which is the one visible artefact this gate prevents.
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let live = true;
    void (async () => {
      let stored: string | null = null;
      try {
        const { data } = await client.GET("/api/settings");
        stored = data?.locale ?? null;
      } catch {
        // An unreachable service: the browser's language is the best answer,
        // and each page reports the outage in its own words.
      }
      if (!live) return;
      adoptServerLocale(stored);
      setReady(true);
    })();
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    document.title = t("app.title");
  }, [t]);

  if (!ready) return null;

  return (
    <>
      <LanguageSwitcher />
      <Outlet />
    </>
  );
}

export const rootRoute = createRootRoute({ component: Shell });
