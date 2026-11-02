import { createRootRoute, Link, Outlet } from "@tanstack/react-router";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { Suspense, useEffect, useState, useSyncExternalStore } from "react";

import { Palette } from "../components/Palette";
import { TopBar } from "../components/TopBar";
import { IconRail } from "../components/IconRail";
import { useTranslation } from "../lib/i18n";
import { adoptServerLocale, activeLocale, subscribeLocale } from "../lib/locale";
import { PageTitleProvider, applyBaseTitle } from "../lib/pageTitle";
import { useSettingsQuery } from "../lib/query";
import "../globals.css";

/**
 * True while a page asked the shell for a chrome-free surface: the page
 * publishes `data-focus="2"` on <body>, the shell subscribes and drops both
 * of its chrome columns — the bar and the rail. An observer, not an event:
 * attribute writes fire no events, and the shell must react whether it
 * mounted before or after the page. TopBar carries its own copy of this
 * subscription (its file is not this task's); P9 consolidates the two.
 */
function useChromeless(): boolean {
  const [chromeless, setChromeless] = useState(
    () => document.body.dataset.focus === "2",
  );
  useEffect(() => {
    const sync = () => setChromeless(document.body.dataset.focus === "2");
    const observer = new MutationObserver(sync);
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["data-focus"],
    });
    return () => observer.disconnect();
  }, []);
  return chromeless;
}

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
  // The deepest focus step owns the whole viewport: neither column of shell
  // chrome survives it.
  const chromeless = useChromeless();

  useEffect(() => {
    if (!settings.isSuccess) return;
    adoptServerLocale(settings.data.locale);
    setReady(true);
  }, [settings.data, settings.isSuccess]);

  // The language the catalog renders in, as reactive state: `t` is a stable
  // module function, so an effect keyed on it would never re-run — the
  // locale is what changes, and the title effect below keys on it.
  const locale = useSyncExternalStore(subscribeLocale, activeLocale, activeLocale);

  useEffect(() => {
    // The tab's floor: the app's own name until a page names itself, and a
    // recomposition — not a clobber — once one has, so a language change
    // cannot strip the page's name out of the tab.
    applyBaseTitle();
  }, [locale]);

  // The palette's key. A window listener, not a route's: ⌘K must answer on
  // every page, and no page should have to know the palette exists. A held
  // key repeats, a composition emits keydown mid-word, and a key another
  // handler has already claimed is left alone — the same refusals the
  // workbench's own shortcuts make. ⌘K toggles, so the same press that
  // opened it closes it again.
  const [paletteOpen, setPaletteOpen] = useState(false);
  useEffect(() => {
    const onKeydown = (event: KeyboardEvent) => {
      if (event.repeat || event.isComposing) return;
      if (event.defaultPrevented) return;
      if ((event.metaKey || event.ctrlKey) && (event.key === "k" || event.key === "K")) {
        event.preventDefault();
        setPaletteOpen((value) => {
          // Opening over a live dialog would stack a second focus trap on
          // the first: typing would drive a page the dialog shadows, and
          // the dialog would survive onto whatever route the palette then
          // jumps to. A dialog owns the stage, ⌘K refuses to open — its own
          // closing is untouched. The installed React Aria deliberately
          // omits aria-modal on the dialog element (a documented Safari
          // workaround; modality comes from aria-hidden outside), so the
          // check reads the role alone — and every modal in the app is a
          // React Aria dialog, wherever it was opened from.
          if (!value && document.querySelector('[role="dialog"]') !== null) {
            return value;
          }
          return !value;
        });
      }
    };
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, []);

  if (!ready) return null;

  return (
    <PageTitleProvider>
      {/* The shell frame, led by the bar: its skip link is the first
          focusable element in the document, so the bar precedes the rail in
          the DOM and flex puts the rail on its visual axis — a row beneath
          the bar — without moving the keyboard's first stop. The shell is
          exactly one viewport tall and `main` owns the page scroll, so the
          rail fills the row it lives in (a viewport-tall rail under the bar
          would push its own bottom anchor under the fold and tax every page
          with the overflow). Both columns of chrome are gone at the deepest
          focus step; below 1280 the rail is not rendered, so pages see
          exactly the width they saw before it. */}
      <div className="flex h-dvh flex-col">
        {chromeless ? null : <TopBar />}
        <div className="flex min-h-0 min-w-0 flex-1">
          {chromeless ? null : <IconRail />}
          {/* The shell owns the page's one main landmark; routes render content
              inside it, and the skip link lands here. tabIndex makes the landing
              hold focus — fragment navigation focuses a target only if it can —
              and -1 keeps it out of the tab order. */}
          <main id="main" tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto">
            {/* Capability pages load lazily, each as its own bundle chunk; the
                one boundary lives in the shell so no capability needs one. The
                fallback is null on purpose — the shell's own pre-paint gate is
                quiet, and the gap while a chunk arrives is the same quiet. */}
            <Suspense fallback={null}>
              <Outlet />
            </Suspense>
          </main>
        </div>
        {/* The keyboard surface, mounted with the shell: one instance, every
            route, and its ⌘K listener above. */}
        <Palette open={paletteOpen} onOpenChange={setPaletteOpen} />
      </div>
    </PageTitleProvider>
  );
}

/** The shell's answer to an unknown URL: the copy comes from the catalog —
 * TanStack's English default would break the i18n rule inside the localized
 * shell — and the way home is the shelf. */
function NotFound() {
  const t = useTranslation();
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("shell.notFound")}</h1>
      <Link
        to="/"
        className="mt-4 inline-block text-sm text-muted underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        {t("nav.back")}
      </Link>
    </div>
  );
}

/** A route that throws lands here, not on TanStack's English default: the
 * failure is named in the catalog's language and the thrown message rides
 * along — a local-first app shows its own errors. */
function RouteError({ error }: ErrorComponentProps) {
  const t = useTranslation();
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("shell.error")}</h1>
      <p role="alert" className="mt-4 text-sm text-danger">
        {message}
      </p>
      <Link
        to="/"
        className="mt-4 inline-block text-sm text-muted underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
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
