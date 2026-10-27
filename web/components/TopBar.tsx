import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { nav } from "../lib/generated/capabilities";
import { useTranslation } from "../lib/i18n";
import { focusRing, LanguageSwitcher } from "./LanguageSwitcher";

/**
 * True while a page asked the shell for a chrome-free surface: the page
 * publishes `data-focus="2"` on <body>, the bar subscribes. An observer, not
 * an event: attribute writes fire no events, and the bar must react whether
 * it mounted before or after the page.
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

/** The shell's chrome: the skip link, the capability navigation, the settings, the language. */
export function TopBar() {
  const t = useTranslation();
  // The novel workbench's deepest focus step hides the bar: only the text
  // remains. Scoped by the body attribute, so no other page can lose chrome.
  const chromeless = useChromeless();
  if (chromeless) return null;

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
        <div className="flex items-center gap-4">
          {/* The gear: settings is a control, not a browsing destination, so
              it rides beside the language instead of the generated nav. The
              glyph carries the meaning in every language; the screen-reader
              name is the localized word. */}
          <Link
            to="/settings"
            className={`rounded-md text-base leading-none underline-offset-4 hover:underline ${focusRing}`}
          >
            <span aria-hidden="true">⚙</span>
            <span className="sr-only">{t("shell.settings")}</span>
          </Link>
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  );
}
