import { createRootRoute, Link, Outlet } from "@tanstack/react-router";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { Suspense, useEffect, useState, useSyncExternalStore } from "react";

import { useTranslation } from "../lib/i18n";
import { adoptServerLocale, activeLocale, subscribeLocale } from "../lib/locale";
import { PageTitleProvider, applyBaseTitle, usePageTitle } from "../lib/pageTitle";
import { useSettingsQuery } from "../lib/query";
import { adoptServerTheme } from "../lib/theme";
import "../globals.css";

/** The shell root: providers, locale and theme adoption, the tab title's
 * floor, and the one outlet. The interim app has no chrome — the bar, rail
 * and palette are demolished with the UI they served and return with the
 * rebuilt screens; the plumbing they rode on stays. */
function Shell() {
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
    adoptServerTheme(settings.data.theme);
    setReady(true);
  }, [settings.data, settings.isSuccess]);

  // The language the catalog renders in, as reactive state: the title effect
  // below must re-run when the language changes, and the locale is what
  // changes.
  const locale = useSyncExternalStore(subscribeLocale, activeLocale, activeLocale);

  // biome-ignore lint/correctness/useExhaustiveDependencies: locale is the deliberate re-run key, not a value the body reads — a language change must recompose the tab title.
  useEffect(() => {
    // The tab's floor: the app's own name until a page names itself, and a
    // recomposition — not a clobber — once one has, so a language change
    // cannot strip the page's name out of the tab.
    applyBaseTitle();
  }, [locale]);

  if (!ready) return null;

  return (
    <PageTitleProvider>
      {/* The shell owns the page's one main landmark; routes render content
          inside it. tabIndex makes the landing hold focus — fragment
          navigation focuses a target only if it can. Capability pages load
          lazily, each as its own bundle chunk; the one boundary lives in the
          shell so no capability needs one, and the fallback is null on
          purpose — the gap while a chunk arrives stays quiet. */}
      <main id="main" tabIndex={0}>
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
      </main>
    </PageTitleProvider>
  );
}

/** The shell's answer to an unknown URL: the copy comes from the catalog —
 * TanStack's English default would break the i18n rule inside the localized
 * shell — and the way home is the interim placeholder. TanStack renders
 * this component in place of the whole Shell, so the title the tab reads
 * is the page's alone. */
function NotFound() {
  const t = useTranslation();
  usePageTitle(t("shell.notFound"));
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("shell.notFound")}</h1>
      <p className="mt-4 text-body text-muted">{t("shell.notFoundBody")}</p>
      <Link
        to="/"
        className="mt-4 inline-block text-body text-muted underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
      >
        {t("nav.back")}
      </Link>
    </div>
  );
}

/** A route that throws lands here, not on TanStack's English default: the
 * failure is named in the catalog's language and the thrown message rides
 * along — a local-first app shows its own errors. Same system as the
 * unknown URL above, mounted the same way: in place of the Shell, and the
 * tab reads the title. */
function RouteError({ error }: ErrorComponentProps) {
  const t = useTranslation();
  const message = error instanceof Error ? error.message : String(error);
  usePageTitle(t("shell.error"));
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("shell.error")}</h1>
      <p role="alert" className="mt-4 text-body text-muted">
        {message}
      </p>
      <Link
        to="/"
        className="mt-4 inline-block text-body text-muted underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
      >
        {t("nav.back")}
      </Link>
    </div>
  );
}

export const rootRoute = createRootRoute({
  component: Shell,
  notFoundComponent: NotFound,
  errorComponent: RouteError,
});
