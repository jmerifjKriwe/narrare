import type { ComponentProps, CSSProperties } from "react";
import { Link, useMatches } from "@tanstack/react-router";
import { workspaceRouteId } from "../lib/generated/workspace";

import { useTranslation, type MessageKey } from "../lib/i18n";
import { nav } from "../lib/generated/capabilities";
import { buttonClass } from "../ui/Button";
import { Icon, type IconName } from "../ui/icons";

/**
 * The app's one navigation: a fixed Home (the shelf — `writing` stays
 * `nav: false` because the shelf *is* home, not a destination), the
 * generated `nav` rows beneath it, and Settings anchored at the bottom.
 * The drafted chrome (spec §6.4, §6.5): a Tier 1 panel — the panel
 * ground behind the hairline edge, flat, no elevation — whose
 * destinations sit under the drafts' eyebrow-tracked section labels
 * (`RAIL_GROUPS`), each icon keeping its area's identity hue. The labels
 * ride the same reveal as the destination names, so the rail opens as
 * one column.
 *
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

/**
 * The classes that reveal a rail label — a destination's name or a
 * group's eyebrow — when the rail opens: hover, keyboard focus, or a
 * coarse pointer's standing-open rail. One string, because the names and
 * the groups they sit under must open together, never on different
 * triggers.
 */
const REVEAL =
  "opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none pointer-coarse:opacity-100";

/** The icon's colour expression, derived from the capability id. */
export function areaStyle(area: string): CSSProperties {
  return { color: `var(--area-${area}, var(--foreground))` };
}
type RailActiveOptions = ComponentProps<typeof Link>["activeOptions"];

/** The area's identity hue: an identity mark on the icon, never a fill, a
 *  text colour, a cover or a notice. A capability adds its `--area-<id>`
 *  token in `globals.css`; without one the foreground ink is the fallback.
 *  The five existing hues are measured ≥ 3:1 against `--panel` in both
 *  themes. */
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
      className={`${buttonClass("icon", "sm")} w-full grid-cols-[auto_1fr] gap-2 aria-[current=page]:bg-soft aria-[current=page]:font-semibold aria-[current=page]:text-foreground`}
    >
      <span style={areaStyle(area)}>
        <Icon name={icon} />
      </span>
      {/* The name, always in the DOM and clipped by the collapsed rail: a
           hover or a focused entry opens the rail, and a coarse pointer gets
           the names permanently. The link's own ink carries the state, so an
           active entry's label reads foreground like its glyph's cell. */}
      <span
        className={`${REVEAL} min-w-0 justify-self-start whitespace-nowrap`}
      >
        {label}
      </span>
    </Link>
  );
}

/**
 * One drafted section label: the eyebrow-tracked group header over its
 * destinations, clipped like the names until the rail opens. The label
 * aligns with the destination names' own column — 28 px icon cell plus
 * the 8 px gap — so a group reads as one column with its entries.
 */
function RailGroup({ label }: { label: string }) {
  return (
    <span className={`${REVEAL} mb-1 mt-2 pl-9 pr-2 text-eyebrow uppercase text-muted`}>
      {label}
    </span>
  );
}

/**
 * The drafted rail groups (spec §6.5, the screens' eyebrow section
 * labels): the manuscript's tools — the shelf that is Home and the AI
 * dialogue that serves the manuscript — under "Manuskript & Werk"; the
 * world's structure — knowledge and planning — under "Architektur &
 * Welt". The drafts' third group, "Produktion & Studio", names
 * capabilities the app does not carry yet and renders nothing: an empty
 * group is not chrome (the non-goal), and the group joins when its
 * destinations do. Every generated `nav` row must land in exactly one
 * group — the rail's test fails an unplaced capability, because a
 * grouping is a decision, not a default.
 */
export const RAIL_GROUPS: ReadonlyArray<{
  labelKey: MessageKey;
  home?: boolean;
  ids: readonly string[];
}> = [
  { labelKey: "shell.railGroupManuscript", home: true, ids: ["chat"] },
  { labelKey: "shell.railGroupWorld", ids: ["knowledge", "planning"] },
];

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
        /* p-1.5, not p-2: the entry's icon cell runs 28 px wide (16 px glyph
           + the icon variant's p-1.5), and 48 − 2×6 = 36 leaves the 8 px gap
           and nothing more — the label column collapses to zero in the closed
           rail and only earns its width in the 168 px hover. */
        /* inset-y-0, not h-screen: the rail fills the row beneath the bar — a
           viewport-tall rail there would start 53 px down and end 53 px under
           the fold, hiding the anchored Settings and scrolling the page that
           does not otherwise scroll (main owns that). */
        /* Flat, per the drafts' Tier 1: the open rail is a panel bound by its
           hairline edge, not a floating surface — the expansion keeps the
           border and drops the old overlay elevation the tier forbids. */
        className="group absolute inset-y-0 left-0 z-20 flex w-[var(--rail-width)] flex-col items-start justify-between overflow-hidden border-r border-border bg-panel p-1.5 transition-[width] duration-150 hover:w-[168px] focus-within:w-[168px] motion-reduce:transition-none pointer-coarse:transition-none"
      >
        <div className="flex w-full flex-col items-stretch gap-1">
          {RAIL_GROUPS.map((group) => (
            <div key={group.labelKey} className="flex flex-col gap-1">
              <RailGroup label={t(group.labelKey)} />
              {/* Home is a shell constant, not a generated row: the shelf is
                  where the app opens, exact — a prefix match would light it
                  on every route. It sits in the manuscript's group, the
                  drafts' Bücherregal. */}
              {group.home ? (
                <RailLink
                  to="/"
                  label={t("shell.navHome")}
                  icon="books"
                  area="writing"
                  activeOptions={{ exact: true, includeSearch: false }}
                />
              ) : null}
              {nav
                .filter((entry) => group.ids.includes(entry.id))
                .map((entry) => (
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
