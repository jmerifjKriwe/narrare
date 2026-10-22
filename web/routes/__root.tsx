import { createRootRoute, Outlet } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { TopBar } from "../components/TopBar";
import { useTranslation } from "../lib/i18n";
import { adoptServerLocale } from "../lib/locale";
import { useSettingsQuery } from "../lib/query";
import "../globals.css";

/** The one shell: every route renders inside it. */
function Shell() {
  const t = useTranslation();
  // The language is user data on the server, so the first paint waits for it.
  // Rendering first and switching after would flash the wrong language on
  // every load, which is the one visible artefact this gate prevents. The
  // gate rests on the query never erroring: an unreachable service resolves
  // to `locale: null` (web/lib/query.ts), so `isSuccess` is reached on an
  // outage too, and the gate opens into the browser's language.
  const [ready, setReady] = useState(false);
  const settings = useSettingsQuery();

  useEffect(() => {
    if (!settings.isSuccess) return;
    adoptServerLocale(settings.data.locale);
    setReady(true);
  }, [settings.data, settings.isSuccess]);

  useEffect(() => {
    document.title = t("app.title");
  }, [t]);

  if (!ready) return null;

  return (
    <>
      <TopBar />
      {/* The shell owns the page's one main landmark; routes render content
          inside it, and the skip link lands here. tabIndex makes the landing
          hold focus — fragment navigation focuses a target only if it can —
          and -1 keeps it out of the tab order. */}
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  );
}

export const rootRoute = createRootRoute({ component: Shell });
