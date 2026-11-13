import type { ComponentProps, CSSProperties } from "react";
import { useState } from "react";
import { Link, useMatches, useNavigate, useParams } from "@tanstack/react-router";
import { Button, Menu, MenuItem, MenuTrigger, Popover } from "react-aria-components";

import { workspaceRouteId } from "../lib/generated/workspace";

import { client } from "../lib/api/client";
import type { Novel } from "../lib/api/client";
import { useTranslation, type MessageKey } from "../lib/i18n";
import { nav } from "../lib/generated/capabilities";
import { queryClient, useNovelsQuery, useSettingsQuery } from "../lib/query";
import { applyTheme, type Theme } from "../lib/theme";
import { buttonClass } from "../ui/Button";
import { coverTone, type CoverTone } from "../ui/Cover";
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
 * The drafted blocks complete the rail (spec §5.0, the workspace screen's
 * own left `<aside>`): the book-switcher at the head — the active novel's
 * cover chip and name, and an unfold-more menu of the user's novels that
 * navigates on select; and at the foot, behind the hairline, the sync dot
 * the autosave state drives, the theme toggle cycling the settings row's
 * own tri-state, and the user block. All four run on the real sources the
 * app already owns; none renders a number or a name the app does not have.
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

/** The autosave state the workspace publishes; the rail's sync dot renders it. */
export type RailSync = "saved" | "pending" | "failed";

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

/** The dot's state colour, one state token per autosave state — the
 *  diagnostics the design reserves for exactly this: a state of the work,
 *  never a decoration. */
const SYNC_DOT: Record<RailSync, string> = {
  saved: "bg-success",
  pending: "bg-warning",
  failed: "bg-danger",
};

const SYNC_KEY: Record<RailSync, MessageKey> = {
  saved: "shell.syncSaved",
  pending: "shell.syncPending",
  failed: "shell.syncFailed",
};

/** The sync line at the foot: the dot reads at a glance in the collapsed
 *  rail, the label opens with the rail. No live region here on purpose —
 *  the editor's own SaveIndicator is the save state's announcement, next
 *  to the text the writer is looking at; a second one in the chrome would
 *  repeat it on every save. The dot sits in the names' 28 px column, so
 *  the open line aligns with every label above it. */
function SyncLine({ sync }: { sync: RailSync }) {
  const t = useTranslation();
  return (
    <div
      data-sync={sync}
      className="flex h-8 w-full items-center gap-2 px-1 text-muted"
    >
      <span className="grid w-7 shrink-0 place-items-center">
        <span aria-hidden="true" className={`h-2 w-2 rounded-full ${SYNC_DOT[sync]}`} />
      </span>
      <span className={`${REVEAL} min-w-0 justify-self-start truncate uppercase tracking-wide text-meta`}>
        {t(SYNC_KEY[sync])}
      </span>
    </div>
  );
}

/**
 * The theme states and their cycle, as the settings row owns the
 * tri-state (AppearancePage): the stored null is "system", and the rail's
 * press walks system → light → dark → system. The state labels are the
 * appearance select's own catalog keys — one vocabulary for one choice.
 */
const THEME_STATE_KEY = {
  system: "settings.appearance.system",
  light: "settings.appearance.light",
  dark: "settings.appearance.dark",
} as const;
type ThemeChoice = keyof typeof THEME_STATE_KEY;
const THEME_CYCLE: Record<ThemeChoice, ThemeChoice> = {
  system: "light",
  light: "dark",
  dark: "system",
};

/**
 * The theme toggle at the foot, driving the exact contract the appearance
 * page drives: apply before the write, PATCH `/api/settings/theme` with
 * the row's shape, invalidate `["settings"]` on success, roll the document
 * and the control back to the stored choice on a refusal. The refusal
 * speaks on the settings page — its Notice is the one surface a theme
 * refusal has; the rail rolls back quietly rather than growing failure
 * chrome no draft draws. The face is the drafts' moon and the catalog's
 * "Theme"; the current choice rides the accessible name, so a reader
 * hears what a press will move from before it moves.
 */
function ThemeToggle() {
  const t = useTranslation();
  const settings = useSettingsQuery();
  const stored = settings.data?.theme ?? null;
  // The control's own choice until the refetch lands (the appearance
  // page's answer to the same roundtrip lag): a press must not wait for
  // the write to name itself.
  const [chosen, setChosen] = useState<ThemeChoice | null>(null);
  const value: ThemeChoice = chosen ?? (stored === "light" || stored === "dark" ? stored : "system");

  async function cycle(): Promise<void> {
    const next = THEME_CYCLE[value];
    const theme: Theme | null = next === "system" ? null : next;
    const previous: Theme | null =
      stored === "light" || stored === "dark" ? stored : null;
    setChosen(next);
    applyTheme(theme);
    try {
      const { response } = await client.PATCH("/api/settings/theme", {
        body: { theme },
      });
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      // The row changed, so the cached answer is stale; the refetch brings
      // back what was just persisted, so cache and row cannot disagree.
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      // The write did not happen, so neither the document nor the control
      // may pretend it did.
      setChosen(null);
      applyTheme(previous);
    }
  }

  return (
    <Button
      aria-label={`${t("shell.railTheme")}: ${t(THEME_STATE_KEY[value])}`}
      onPress={() => void cycle()}
      className={`${buttonClass("icon", "sm")} w-full grid-cols-[auto_1fr] gap-2`}
    >
      <span>
        <Icon name="theme" />
      </span>
      <span className={`${REVEAL} min-w-0 justify-self-start whitespace-nowrap`}>
        {t("shell.railTheme")}
      </span>
    </Button>
  );
}

/** The cover chip's grounds: the tile's own four tone utilities keyed by
 *  the tone `coverTone` names — the same tokens the shelf's Cover wears,
 *  never a hex. At 20 px the tile's lettering and spine would be detail
 *  that disappears, so the chip is the tone's ground alone. */
const CHIP_GROUND: Record<CoverTone, string> = {
  pale: "bg-cover-pale",
  sepia: "bg-cover-sepia",
  ink: "bg-cover-ink",
  slate: "bg-cover-slate",
};

/**
 * The book-switcher at the rail's head (the workspace draft's soft pill):
 * the active novel's cover chip — its face while the rail is closed — and
 * its name beside the unfold-more, opening a menu of the user's novels
 * that navigates on select. The trigger is the menu primitive's own
 * pattern (Menu.tsx, which cannot fit here: its trigger paints a glyph or
 * a label, never the drafted chip-plus-name face) — React Aria's whole
 * contract rides on: the arrows, Escape back to the trigger, focus
 * contained while the menu stands. With no book open the face is the
 * library glyph and the catalog's label; with no book in the library
 * there is nothing to switch, and the block waits.
 */
function BookSwitcher({ novels, active }: { novels: Novel[]; active: Novel | null }) {
  const t = useTranslation();
  const navigate = useNavigate();
  if (novels.length === 0) return null;
  const tone = active !== null ? coverTone(active.title) : null;
  return (
    <MenuTrigger>
      <Button
        aria-label={
          active !== null
            ? `${t("shell.railBookMenu")}: ${active.title}`
            : t("shell.railBookMenu")
        }
        className="flex h-8 w-full items-center gap-2 rounded-[var(--radius-control)] bg-soft px-1 text-muted hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent"
      >
        {/* The chip is the collapsed rail's face for the book: decorative —
         * the trigger's accessible name is the one that names it. */}
        {tone !== null && active !== null ? (
          <span
            aria-hidden="true"
            data-rail-cover={tone}
            className={`aspect-[3/4] w-5 shrink-0 rounded-[var(--radius)] border border-border ${CHIP_GROUND[tone]}`}
          />
        ) : (
          <span aria-hidden="true" className="grid w-5 shrink-0 place-items-center">
            <Icon name="autoStories" />
          </span>
        )}
        <span className={`${REVEAL} min-w-0 truncate text-left text-label`}>
          {active?.title}
        </span>
        <span aria-hidden="true" className={`${REVEAL} shrink-0`}>
          <Icon name="unfoldMore" />
        </span>
      </Button>
      <Popover className="min-w-40 rounded-[var(--radius)] border border-border bg-card p-1 shadow-overlay">
        <Menu className="flex flex-col outline-hidden">
          {novels.map((novel) => (
            <MenuItem
              key={novel.id}
              onAction={() =>
                void navigate({ to: "/novels/$id", params: { id: novel.id } })
              }
              aria-label={novel.title}
              className="flex items-center justify-between gap-4 rounded-[var(--radius)] px-2 py-1 text-body outline-hidden data-[focused]:bg-soft data-focus-visible:ring-2 data-focus-visible:ring-focus"
            >
              <span className="min-w-0 truncate">{novel.title}</span>
            </MenuItem>
          ))}
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}

/**
 * The user block at the foot: the drafts' avatar chip, name line and
 * standing line. The writer's name is the one the app carries — the open
 * book's author row (the drafts' "H. Calder" is Dead Signal's own author)
 * — and a book without one names the block by its own label, never an
 * invented person. The standing line is the drafts' copy for the
 * persona's tier ("Author Tier"), catalog copy in all three locales.
 */
function UserBlock({ author }: { author: string | null }) {
  const t = useTranslation();
  return (
    <div className="flex h-8 w-full items-center gap-2 px-1">
      <span className="grid w-7 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground">
        <Icon name="person" />
      </span>
      <span className={`${REVEAL} min-w-0`}>
        <span className="block truncate text-label text-foreground">
          {author ?? t("shell.railUserFallback")}
        </span>
        <span className="block truncate text-meta text-muted">
          {/* interim: static copy — the app holds no user/tier row to read
              this from (follow-up: user/tier row) */}
          {t("shell.railUserTier")}
        </span>
      </span>
    </div>
  );
}

/** The global icon rail: shell chrome, one navigation on every route. */
export function IconRail({ sync }: { sync: RailSync }) {
  const t = useTranslation();
  // The switcher's reads: the library list under its own cache key, the
  // open novel from the workspace address, read tolerantly — off the
  // workspace there is none (the palette's own precedent).
  const novelsQuery = useNovelsQuery();
  const workspace = useParams({ from: "/novels/$id", shouldThrow: false });
  const active =
    novelsQuery.data?.find((novel) => novel.id === workspace?.id) ?? null;
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
          {/* The book-switcher at the head, above the groups: the drafts put
           * the open book at the rail's top, the destinations beneath it. */}
          {novelsQuery.data !== undefined ? (
            <BookSwitcher novels={novelsQuery.data} active={active} />
          ) : null}
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
        {/* The anchored Settings above the hairline, and the drafted foot
         * beneath it: sync, theme and user, the drafts' own foot order. */}
        <div className="flex w-full flex-col gap-1">
          {/* Settings is area-wide — the anchor stays lit on the settings
              cluster's sub-pages, which are settings too. */}
          <RailLink
            to="/settings"
            label={t("shell.settings")}
            icon="settings"
            area="settings"
            activeOptions={{ includeSearch: false }}
          />
          <div className="flex w-full flex-col gap-1 border-t border-rule pt-1.5">
            <SyncLine sync={sync} />
            <ThemeToggle />
            <UserBlock author={active?.author ?? null} />
          </div>
        </div>
      </nav>
    </div>
  );
}
