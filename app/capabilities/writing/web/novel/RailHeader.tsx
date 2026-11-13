import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import { Link } from "@tanstack/react-router";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { buttonClass } from "@shell/ui/Button";
import { Icon, type IconName } from "@shell/ui/icons";

/**
 * The rail's drafted meta header and the tab row under it
 * (screens/writing/workspace.html, "Novel Meta Header" and the navigation
 * tabs): the area-writing eyebrow with the draft badge, the book's name in
 * the serif, the two real counts, and the "Kapitel / Szenen & Plot" pair —
 * pure client state, ARIA tabs, the chapters' list as the first panel and
 * an honest door to the planning surface as the second.
 *
 * Everything shown derives from the props the page hands over (spec §6):
 * what the draft draws that no field backs stays out and is named for the
 * follow-up where it hides.
 */

/** The two views, as data: the tab, its catalog label, its glyph, its panel. */
const TABS: Array<{
  id: "chapters" | "scenes";
  labelKey: MessageKey;
  icon: IconName;
  panelId: string;
}> = [
  {
    id: "chapters",
    labelKey: "workspace.railTabChapters",
    icon: "menuBook",
    panelId: "rail-panel-chapters",
  },
  {
    id: "scenes",
    labelKey: "workspace.railTabScenes",
    icon: "planning",
    panelId: "rail-panel-scenes",
  },
];

export type RailTabId = (typeof TABS)[number]["id"];

/** One tab's classes: the drafted underline pair, active and at rest. */
function tabClasses(selected: boolean): string {
  return selected
    ? "border-primary font-semibold text-primary"
    : "border-transparent text-muted hover:text-foreground";
}

/**
 * The meta header card: the eyebrow row, the book's name, the counts. The
 * counts are the numbers the rail already holds — the chapter count and the
 * Σ of its own per-chapter words, spoken in the two catalog sentences the
 * hero and the band already use (one wording, no drift).
 */
export function RailHeader({
  bookTitle,
  chapterCount,
  words,
}: {
  /** The book's name as the row holds it; `undefined` while the row waits. */
  bookTitle: string | undefined;
  /** The book's chapter count, as the page derived it. */
  chapterCount: number;
  /** The book's Σ chapter words — the rail's counts map, summed. */
  words: number;
}) {
  const t = useTranslation();
  return (
    <div className="flex flex-col gap-1.5 bg-surface-container-low px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-eyebrow uppercase text-area-writing">
          {t("workspace.railOutline")}
        </span>
        {/* The draft reads "Entwurf v2.4", but the app has no version field:
            a badge that invented "v2.4" would be a number the app does not
            hold (spec §6's interim rule), so the badge keeps the neutral
            word alone. */}
        <span
          // interim: no version field — #816
          className="shrink-0 rounded-full bg-surface px-2 py-0.5 text-meta text-secondary"
        >
          {t("workspace.railDraft")}
        </span>
      </div>
      {/* A styled paragraph, not a heading: the workspace's h1 is the one
          heading that names the book, and the browser E2Es pin
          `get_by_role("heading", name=title)` to resolve to exactly it. The
          tooltip carries the whole name for a pointer, as the breadcrumb's
          does. */}
      {bookTitle !== undefined ? (
        <p
          title={bookTitle}
          className="text-title text-primary tracking-tight font-garamond"
        >
          {bookTitle}
        </p>
      ) : null}
      <div className="flex items-center gap-1.5 text-meta text-muted">
        <span className="text-outline" aria-hidden="true">
          <Icon name="autoStories" size={15} />
        </span>
        <span className="tabular-nums">
          {t("shelf.card.chapters", { count: chapterCount })}
        </span>
        {/* The draft's little separator pill between the two counts. */}
        <span aria-hidden="true" className="h-2.5 w-1 shrink-0 rounded-full bg-outline-variant" />
        <span className="text-outline" aria-hidden="true">
          <Icon name="editNote" size={15} />
        </span>
        <span className="font-medium text-foreground tabular-nums">
          {t("chapters.wordCount", { count: words })}
        </span>
      </div>
    </div>
  );
}

/**
 * The tab row: two ARIA tabs with the drafted underline, automatic
 * activation, the roving tabindex and the arrow contract. Left/Right/Home/
 * End are the tab row's keys alone — the chapters' list owns Up/Down for
 * its walk, and neither list of keys eats the other's.
 */
export function RailTabs({
  value,
  onChange,
}: {
  value: RailTabId;
  onChange: (tab: RailTabId) => void;
}) {
  const t = useTranslation();
  // APG automatic activation: the arrow moves the selection and the focus
  // rides with it, so the next Tab leaves from the tab the user landed on.
  function onKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>) {
    const at = TABS.findIndex((tab) => tab.id === value);
    let next: number;
    if (event.key === "ArrowRight") next = (at + 1) % TABS.length;
    else if (event.key === "ArrowLeft") next = (at + TABS.length - 1) % TABS.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = TABS.length - 1;
    else return;
    event.preventDefault();
    onChange(TABS[next]!.id);
    event.currentTarget.parentElement
      ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
      [next]?.focus();
  }
  return (
    <div
      role="tablist"
      aria-label={t("workspace.railViews")}
      className="flex items-center gap-1 px-3 pt-2"
    >
      {TABS.map((tab) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`rail-tab-${tab.id}`}
            aria-selected={selected}
            aria-controls={tab.panelId}
            tabIndex={selected ? 0 : -1}
            onKeyDown={onKeyDown}
            onClick={() => onChange(tab.id)}
            className={`flex flex-1 items-center justify-center gap-1.5 border-b-2 pb-1.5 text-label transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus ${tabClasses(selected)}`}
          >
            <span aria-hidden="true">
              <Icon name={tab.icon} size={16} />
            </span>
            {t(tab.labelKey)}
          </button>
        );
      })}
    </div>
  );
}

/**
 * The Szenen panel's empty state: the one honest sentence about where
 * scenes and plot live, and the door to the novel's planning surface — the
 * timeline the atlas names as the door to its siblings, addressed with this
 * book's id.
 */
export function RailScenesEmpty({ novelId }: { novelId: string }) {
  const t = useTranslation();
  return (
    <div className="mt-3 flex flex-col gap-2 px-3">
      <p className="text-body text-muted">{t("workspace.railScenesEmpty")}</p>
      {/* The rail links the planning surface, not a scenes view of its own:
          the app's scenes-and-plot home is the planning capability's page,
          and the storyboard hangs off it — the atlas keeps the timeline as
          the one door, so the rail's door is the same one. */}
      <Link
        to="/planning"
        search={{ novel: novelId }}
        // interim: no scenes view — #819
        className={`${buttonClass("secondary", "sm")} inline-flex w-full items-center justify-center gap-2 no-underline`}
      >
        <Icon name="planning" size={16} />
        {t("workspace.railScenesOpen")}
      </Link>
    </div>
  );
}
