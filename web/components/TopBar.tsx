import { Link } from "@tanstack/react-router";

import { useTranslation } from "../lib/i18n";
import { usePageTitleValue } from "../lib/pageTitle";
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
export function TopBar() {
  const t = useTranslation();
  // The page's published name (the page-title stack's top, P8): the tab
  // wears `<page> — Narrare`, the bar wears the page's half. A page that
  // has not named itself leaves the place empty — an unnamed page is not
  // the shell's to name.
  const place = usePageTitleValue();

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
        {/* The place. `min-w-0` lets a long title shrink instead of pushing
            the actions out of the bar; until a page names itself this side
            is empty, and the actions hold the right edge regardless. */}
        <div className="min-w-0 font-medium">
          <span className="block truncate">{place}</span>
        </div>
        <div className="flex items-center gap-4">
          {/* The palette's key, named where the keyboard's map is looked
              for. Decorative: the shell owns the ⌘K listener, the chip owns
              nothing, and a keycap is the same glyph in every language —
              the palette footer names the shortcuts it unlocks. */}
          <span
            aria-hidden="true"
            className="rounded-[var(--radius)] border border-border bg-card px-1.5 py-0.5 font-mono text-meta leading-none text-muted"
          >
            ⌘K
          </span>
          {/* The gear: settings is a control, not a browsing destination.
              A link wearing the icon button's paint through `buttonClass`
              (Button.tsx sanctions exactly this for non-button controls —
              Button itself renders a `<button>`, so it cannot be a Link),
              and the label is the one accessible name: the glyph is
              aria-hidden, the rail's Settings anchor keeps its own. */}
          <Link
            to="/settings"
            aria-label={t("shell.settings")}
            className={buttonClass("icon", "md")}
          >
            <Icon name="settings" />
          </Link>
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  );
}
