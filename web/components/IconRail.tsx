import type { ComponentProps } from "react";
import { Link } from "@tanstack/react-router";

import { useTranslation } from "../lib/i18n";
import { nav } from "../lib/generated/capabilities";
import { buttonClass } from "../ui/Button";
import { Icon, type IconName } from "../ui/icons";

/**
 * The app's one navigation: a fixed Home (the shelf — `writing` stays
 * `nav: false` because the shelf *is* home, not a destination), the
 * generated `nav` rows beneath it, and Settings anchored at the bottom.
 * Destinations are links — that is what they are, and P9's one-navigation
 * bar counts on it — wearing the icon button's paint through `buttonClass`
 * (the sanctioned way to put a non-button control in the button's states,
 * Button.tsx). The glyph is never the name: each entry carries its catalog
 * name as `aria-label`, and the active entry says so with
 * `aria-current="page"` — set by the router, worn as the L2 treatment
 * (`--soft` fill, foreground ink) through the attribute selector, so the
 * paint can only agree with the semantics.
 */

/** The rail's destinations: exactly the paths Link itself accepts. */
type RailTo = ComponentProps<typeof Link>["to"];
type RailActiveOptions = ComponentProps<typeof Link>["activeOptions"];

/** One destination: an icon link in the button's icon-variant paint. */
function RailLink({
  to,
  label,
  icon,
  activeOptions,
}: {
  to: RailTo;
  label: string;
  icon: IconName;
  activeOptions?: RailActiveOptions;
}) {
  return (
    <Link
      to={to}
      activeOptions={activeOptions}
      aria-label={label}
      /* The L2 pair rides the attribute Link sets when the route matches:
       * a state variant outspecifies the variant paint (text-muted), a
       * plainly appended class would not — the cascade, not the class
       * string's order, decides. */
      className={`${buttonClass("icon", "md")} aria-[current=page]:bg-soft aria-[current=page]:font-semibold aria-[current=page]:text-foreground`}
    >
      <Icon name={icon} />
    </Link>
  );
}

/** The global icon rail: shell chrome, one navigation on every route. */
export function IconRail() {
  const t = useTranslation();
  return (
    /* From 1280 up only: below it the workbench has no width to give. The
     * viewport floor pins the prose column at a 320 px content box with the
     * dock open — 328 px of slack at 360, 336 at 1024 — and this 48 px
     * column would take both under (280 / 288). At ≥1280 every page
     * container is max-w-capped, so the rail takes only margin; P12's
     * workspace reflow revisits the breakpoint. */
    <nav
      aria-label={t("shell.navAria")}
      /* p-1.5, not p-2: the entry pill runs 36 px wide (16 px glyph + the
         icon variant's px-2.5), and 48 − 2×6 = 36 exactly — the pill sits
         inside the rail's rhythm instead of overhanging the padding. */
      /* h-full, not h-screen: the rail fills the row beneath the bar — a
         viewport-tall rail there would start 53 px down and end 53 px under
         the fold, hiding the anchored Settings and scrolling the page that
         does not otherwise scroll (main owns that). */
      className="hidden h-full w-12 shrink-0 flex-col items-center justify-between border-r border-border bg-panel p-1.5 xl:flex"
    >
      <div className="flex flex-col items-center gap-1">
        {/* Home is a shell constant, not a generated row: the shelf is
            where the app opens, exact — a prefix match would light it on
            every route. */}
        <RailLink
          to="/"
          label={t("shell.navHome")}
          icon="books"
          activeOptions={{ exact: true, includeSearch: false }}
        />
        {nav.map((entry) => (
          <RailLink
            key={entry.id}
            to={entry.path}
            label={t(entry.titleKey)}
            icon={entry.id}
            activeOptions={{ exact: true, includeSearch: false }}
          />
        ))}
      </div>
      {/* Settings is area-wide — the anchor stays lit on the settings
          cluster's sub-pages, which are settings too. */}
      <RailLink
        to="/settings"
        label={t("shell.settings")}
        icon="settings"
        activeOptions={{ includeSearch: false }}
      />
    </nav>
  );
}
