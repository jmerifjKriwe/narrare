import { createRootRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { useEffect, useState, useSyncExternalStore } from "react";

import { ChromeFrame } from "../components/ChromeFrame";
import { useLocalizedError } from "../lib/api/errors";
import { useTranslation } from "../lib/i18n";
import { adoptServerLocale, activeLocale, subscribeLocale } from "../lib/locale";
import { PageTitleProvider, applyBaseTitle, usePageTitle } from "../lib/pageTitle";
import { useSettingsQuery } from "../lib/query";
import { adoptServerTheme } from "../lib/theme";
import { ToastProvider } from "../ui/toast";
import "../globals.css";

/** The shell root: providers, locale and theme adoption, the tab title's
 * floor, and the one outlet. The app-wide chrome (W4 Task 10, D15) frames
 * every post-setup surface — the shelf today, the workspace from Task 11 —
 * while the welcome and the wizard (`/setup/*`) stay standalone, their
 * drafts chrome-less guided flows. The plumbing the demolished interim
 * chrome rode on stays: the settings gate, the locale/theme adoption, the
 * title floor. */
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

  // The chrome's one route question: the guided flows stand alone, every
  // other surface wears the frame. The pathname is reactive — a navigation
  // between the shelf and the wizard re-picks the frame without a remount
  // of the providers above it.
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const standalone = pathname.startsWith("/setup");

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
      <ToastProvider>
        {/* The chrome frames the post-setup surfaces; the guided flows stand
            alone. The frame keeps the outlet at a constant tree depth in
            both modes — a branch flip must never remount the page being
            navigated away from (ChromeFrame's own note). */}
        <ChromeFrame standalone={standalone}>
          <Outlet />
        </ChromeFrame>
      </ToastProvider>
    </PageTitleProvider>
  );
}

/** The shell's answer to an unknown URL: the copy comes from the catalog —
 * TanStack's English default would break the i18n rule inside the localized
 * shell — and the way home is the atelier: the `/` gate answers with the
 * welcome or the landing, whichever the instance's state calls for. An
 * unmatched URL renders this component through the root Outlet, inside the
 * Shell — the settings gate and the main landmark stay — and the tab reads
 * the page's own title. */
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
 * failure is named in the catalog's language — the thrown message never
 * reaches the face; a local-first app still speaks the reader's language. A
 * thrown error or notFound reaches the catch boundary, which mounts this component in place of the
 * whole Shell — unlike the unknown URL above, which renders inside it — and
 * the tab reads the title. */
function RouteError({ error }: ErrorComponentProps) {
  const t = useTranslation();
  const localized = useLocalizedError();
  usePageTitle(t("shell.error"));
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("shell.error")}</h1>
      <p role="alert" className="mt-4 text-body text-muted">
        {localized(error)}
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
