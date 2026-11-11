import { Link, useMatches } from "@tanstack/react-router";
import { workspaceRouteId } from "../lib/generated/workspace";

import { useTranslation } from "../lib/i18n";
import { usePageTitleValue } from "../lib/pageTitle";
import { shortcutKeycap } from "../lib/shortcuts";
import { buttonClass } from "../ui/Button";
import { Icon } from "../ui/icons";
import { LanguageSwitcher } from "./LanguageSwitcher";

/**
 * The shell's bar: the place, then the actions. The rail owns the map, so
 * the bar carries no destinations — where the reader is on the left, and
 * on the right the palette's key, settings and the language, the three
 * things every page answers for. The skip link stays the document's first
 * focusable element; `data-focus="2"` gates the whole bar in `__root.tsx`
 * (one subscription, one decision — the bar carries no copy of it).
 */
export function TopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const t = useTranslation();
  // The keycap is the registry's answer for the palette's key: a Mac shows
  // ⌘K, everywhere else the control key. The chip is the palette's pointer
  // door, so it says what it opens and refuses while a dialog holds the stage.
  const paletteKey = shortcutKeycap("palette.toggle");
  // The page's published name (the page-title stack's top, P8): the tab
  // wears `<page> — Narrare`, the bar wears the page's half. A page that
  // has not named itself leaves the place empty — an unnamed page is not
  // the shell's to name.
  const place = usePageTitleValue();
  // The icon rail takes 48 px from the page axis on the routes that show it
  // — from lg everywhere but the workspace, from xl here (IconRail's R29).
  // The bar sits above that row and spans the viewport, so it must move with
  // the rail or its 1200 container centres 24 px left of every page's own
  // (measured: bar title 217 px, shelf heading 241 px).
  const onWorkspace = useMatches().some((match) => match.routeId === workspaceRouteId);

  return (
    <header
      className={`border-b border-border bg-panel ${onWorkspace ? "xl:pl-[var(--rail-width)]" : "lg:pl-[var(--rail-width)]"}`}
    >
      {/* Hidden from sight until focused, and first in the bar so the first
          Tab finds it. Transform and opacity, not sr-only: the reveal then
          needs no second utility to undo the hiding. The ring is pre-applied
          rather than focus-visible-gated because reveal and focus coincide. */}
      <a
        href="#main"
        className="fixed left-4 top-4 z-20 -translate-y-24 rounded-[var(--radius)] bg-card px-3 py-2 text-body text-foreground opacity-0 outline-hidden ring-2 ring-focus transition focus:translate-y-0 focus:opacity-100"
      >
        {t("shell.skipToContent")}
      </a>
      {/* The bar's content aligns with the app's nominal page container —
          the shelf's 1200 (R49): the pages grew past the old 672 bar, and
          controls parked at a column nothing else uses read as stray. The
          rail's width shifts that axis; the header's padding shifts the
          centring with it, and the background still spans the viewport. */}
      <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-4 px-4 py-3">
        {/* The place. `min-w-0` lets a long title shrink instead of pushing
            the actions out of the bar; until a page names itself this side
            is empty, and the actions hold the right edge regardless. Below
            sm the place yields: the page's own h1 is one line under the bar,
            and a title squeezed to "Dea…" beside five controls says less
            than nothing. */}
        <div className="hidden min-w-0 text-body font-medium sm:block">
          <span className="block truncate">{place}</span>
        </div>
        <div className="ml-auto flex items-center gap-4">
          {/* The palette's key, named where the keyboard's map is looked
              for, and the palette's door for a pointer: a keycap is the same
              glyph in every language, and the catalog names what it opens.
              The shell owns the ⌘K listener; this control asks the same
              refusal before it opens what the key opens. */}
          <button
            type="button"
            onClick={onOpenPalette}
            aria-label={t("shell.paletteOpen", { key: paletteKey })}
            className="rounded-[var(--radius)] border border-border bg-card px-1.5 py-0.5 font-mono text-meta leading-none text-muted hover:bg-soft focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {paletteKey}
          </button>
          {/* The gear: settings is a control, not a browsing destination.
              A link wearing the icon button's paint through `buttonClass`
              (Button.tsx sanctions exactly this for non-button controls —
              Button itself renders a `<button>`, so it cannot be a Link),
              and the label is the one accessible name: the glyph is
              aria-hidden, the rail's Settings anchor keeps its own. */}
          <Link
            to="/settings"
            aria-label={t("shell.settings")}
            className={buttonClass("icon", "sm")}
          >
            <Icon name="settings" />
          </Link>
          <LanguageSwitcher showFormality={false} />
        </div>
      </div>
    </header>
  );
}
