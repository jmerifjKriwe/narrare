import type { ComponentProps } from "react";
import { Link, useMatches } from "@tanstack/react-router";
import { workspaceRouteId } from "../lib/generated/routes";

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

/** The rail's four areas and the one utility each may wear: an identity mark
 *  on the icon, never a fill, a text colour, a cover or a notice. The hues
 *  are measured ≥ 3:1 against `--panel` in both themes. */
/** One destination: an icon link in the button's icon-variant paint. */
function RailLink({
  to,
  label,
  icon,
  area,
  activeOptions,
}: {
  to: RailTo;
  label: string;
  icon: IconName;
  area: string;
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
       * string's order, decides. The icon's own span carries the area hue,
       * a direct declaration the link's inherited ink cannot override. */
      className={`${buttonClass("icon", "md")} w-full grid-cols-[auto_1fr] gap-2 aria-[current=page]:bg-soft aria-[current=page]:font-semibold aria-[current=page]:text-foreground`}
    >
      <span style={{ color: `var(--area-${area}, var(--foreground))` }}>
        <Icon name={icon} />
      </span>
      {/* The name, always in the DOM and clipped by the collapsed rail: a
          hover or a focused entry opens the rail, and a coarse pointer gets
          the names permanently. The link's own ink carries the state, so an
          active entry's label reads foreground like its glyph's cell. */}
      <span className="min-w-0 justify-self-start whitespace-nowrap opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none pointer-coarse:opacity-100">
        {label}
      </span>
    </Link>
  );
}

/** The global icon rail: shell chrome, one navigation on every route. */
export function IconRail() {
  const t = useTranslation();
  // R29: the breakpoint answers the surface, not one number for all. The
  // workspace is where prose is written — the novel route and every dock
  // child under it (the parent is in the match chain on all of them) — and
  // there the prose floor owns 1024–1279: the viewport floor pins the prose
  // column at a 320 px content box with the dock open, and this 48 px column
  // would take it under (280 / 288). So the rail waits for 1280 on the
  // workspace. On every other route the rail shows from 1024 like the rest
  // of the chrome — at a real content cost there: the pages' caps (the
  // shelf's 1200 px, the reading pages' 672) centre their content and yield
  // the rail margin only past them, so at 1024 the shelf gives up 48 px of
  // content while the narrower reading pages never notice (their cap binds
  // first). The router's matches, not a pathname sniff: one rail, one
  // breakpoint that reads which route is showing.
  const onWorkspace = useMatches().some((match) => match.routeId === workspaceRouteId);
  return (
    /* The show-leg is the route's answer (the ternary above): from 1280 on
     * the workspace, where the prose floor owns 1024–1279; from 1024 on
     * every other route. `hidden` is shared, so there is one rail and one
     * element — the cascade never sees two.
     *
     * The slot keeps the 48 px column in the layout; the rail inside it
     * grows over the page on hover and focus, so opening it moves no page
     * pixel. A coarse pointer has no hover to open it with, so there the
     * slot and the rail are widened for good — the names are the point. */
    <div
      className={`relative hidden w-[var(--rail-width)] shrink-0 ${
        onWorkspace ? "xl:block" : "lg:block"
      }`}
    >
      <nav
        aria-label={t("shell.navAria")}
        /* p-1.5, not p-2: the entry pill runs 36 px wide (16 px glyph + the
           icon variant's px-2.5), and 48 − 2×6 = 36 exactly — the pill sits
           inside the rail's rhythm instead of overhanging the padding. */
        /* inset-y-0, not h-screen: the rail fills the row beneath the bar — a
           viewport-tall rail there would start 53 px down and end 53 px under
           the fold, hiding the anchored Settings and scrolling the page that
           does not otherwise scroll (main owns that). */
        className="group absolute inset-y-0 left-0 z-20 flex w-[var(--rail-width)] flex-col items-start justify-between overflow-hidden border-r border-border bg-panel p-1.5 transition-[width] duration-150 hover:w-[168px] focus-within:w-[168px] hover:shadow-overlay focus-within:shadow-overlay motion-reduce:transition-none pointer-coarse:shadow-none pointer-coarse:transition-none"
      >
        <div className="flex w-full flex-col items-stretch gap-1">
          {/* Home is a shell constant, not a generated row: the shelf is
              where the app opens, exact — a prefix match would light it on
              every route. */}
          <RailLink
            to="/"
            label={t("shell.navHome")}
            icon="books"
            area="writing"
            activeOptions={{ exact: true, includeSearch: false }}
          />
          {nav.map((entry) => (
            <RailLink
              key={entry.id}
              to={entry.path}
              label={t(entry.titleKey)}
              icon={entry.id}
              area={entry.id}
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
          area="settings"
          activeOptions={{ includeSearch: false }}
        />
      </nav>
    </div>
  );
}
