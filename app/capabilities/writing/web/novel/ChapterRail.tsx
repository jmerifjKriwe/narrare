import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import { useState } from "react";

import type { Chapter } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { formatWordCount } from "@shell/lib/words";
import { Button } from "@shell/ui/Button";
import { Icon } from "@shell/ui/icons";
import { Notice } from "@shell/ui/Notice";

import { RailHeader, RailScenesEmpty, RailTabs, type RailTabId } from "./RailHeader";
import { SessionStats } from "./SessionStats";
import { StoryArc } from "./StoryArc";

// The drag's drop marker: a 2 px primary edge at the slot's top — the row
// a drop would land at. Its look is the spec's "left to the builder"; it
// lives on the slot so the row card's own classes stay untouched.
const DROP_HINT = "shadow-[inset_0_2px_0_var(--primary)]";

/**
 * The drafted row card (screens/writing/workspace.html, the chapter items):
 * a rounded card on its own ground, composed here rather than squeezed
 * through the shared `Row` — the draft draws a three-line card (meta row,
 * title, status) whose selection is a `secondary-container` wash, while
 * `Row`'s contract is the single-line control row with the `--soft` wash
 * and a start edge. Forcing one into the other's className would fight the
 * row matrix this file's siblings share, so the rail owns its frame and
 * `Row` stays untouched for its other consumers.
 *
 * AA, checked in both halves: the wash pairs with its own foreground for
 * the status line (muted ink on the wash is below AA, the exact case the
 * Row docs name), the count and eyebrow take primary and area-writing on
 * it, and the resting text mutes only over the panel and the hover step.
 */
const ROW_FRAME =
  "group relative flex w-full items-start gap-2 rounded-[var(--radius-control)] p-2.5 text-left transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";
const ROW_REST = "text-muted hover:bg-surface-container hover:text-foreground";
const ROW_CURRENT = "bg-secondary-container text-secondary-container-foreground shadow-sm";

/**
 * The grip: the draft's hover-revealed `drag_indicator`, drawn in the set
 * (`dragIndicator` — two columns of three solid dots, a 0.5 circle the
 * set's 1.5 stroke reads as a full disc) and revealed like the shell
 * rail's names — hover, keyboard focus, or a coarse pointer, with the
 * transition dropped under reduced motion. Chrome: `aria-hidden`, because
 * the row is the grab and Alt+arrows are the keyboard reorder.
 */
const GRIP_REST =
  "mt-0.5 shrink-0 cursor-grab text-outline-variant opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 pointer-coarse:opacity-100 motion-reduce:transition-none";
const GRIP_CURRENT =
  "mt-0.5 shrink-0 cursor-grab text-outline opacity-60 group-hover:opacity-100 group-focus-within:opacity-100 active:cursor-grabbing";

export function ChapterRail({
  visibleChapters,
  chapterCounts,
  active,
  activeVisibleIndex,
  walkedIndex,
  railListRef,
  dragId,
  dropIndex,
  railFilter,
  orderFailed,
  createFailed,
  chapterCount,
  novelId,
  bookTitle,
  move,
  moveTo,
  setWalkedIndex,
  setDropIndex,
  select,
  walkRail,
  onCreateChapter,
}: {
  visibleChapters: Chapter[];
  chapterCounts: Map<string, number>;
  active: string | null;
  activeVisibleIndex: number;
  walkedIndex: number | null;
  railListRef: RefObject<HTMLUListElement | null>;
  dragId: RefObject<string | null>;
  dropIndex: number | null;
  railFilter: string | null;
  orderFailed: boolean;
  createFailed: boolean;
  chapterCount: number;
  /** The open book's id — the Szenen tab's planning door addresses it. */
  novelId: string;
  /** The book's name, as the row holds it; `undefined` while the row waits. */
  bookTitle: string | undefined;
  move: (chapterId: string, delta: -1 | 1) => Promise<void>;
  moveTo: (chapterId: string, index: number) => Promise<void>;
  setWalkedIndex: (value: number | null) => void;
  setDropIndex: (value: number | null) => void;
  select: (chapterId: string) => void;
  walkRail: (event: ReactKeyboardEvent, index: number) => void;
  onCreateChapter: () => void;
}) {
  const t = useTranslation();
  // The drafted tab pair: pure client state — which of the rail's two
  // views stands, nothing the URL owes an answer to (the planning door is
  // a navigation of its own; the chapters' list is the work the tab guards).
  const [railTab, setRailTab] = useState<RailTabId>("chapters");
  // The header's Σ words: the same map the rows read, summed — one
  // derivation, a second view of the numbers the rail already holds.
  const railWords = [...chapterCounts.values()].reduce((sum, count) => sum + count, 0);
  // The arc's marker: the open chapter's own place in the book, one-based.
  // Not the visible slot — under a filter that slot is the filtered list's
  // order, and the caption names the chapter's number, so the chapter's
  // own `position` is the number that survives the filter. No open chapter
  // (or one the filter hides) marks no place at all.
  const openChapter = visibleChapters.find((chapter) => chapter.id === active);
  const arcPosition = openChapter === undefined ? 0 : openChapter.position + 1;
  return (
    <aside
      /* Beside the editor at ≥1024 (the columns the desktop E2Es
         pin); below, a drawer over it. The 288 the rail takes are
         the draft's own (screens/writing/workspace.html draws the
         chapter sidebar `lg:w-72`) and the desktop arithmetic's —
         rail 288 + column + dock sum to the container's 1168 content
         with no gap of their own: 880 closed, 544 with the dock
         open, where the card fills its zone and the column's own
         16 px padding is the focus ring's clearance to the dock's
         seam. The list bounds its height and scrolls inside itself
         (Review Focus 2); below the breakpoint the whole drawer
         scrolls instead. The drawer paints one z-step above the
         dock's: opening it over a live dock covers the dock without
         unmounting it, so the dock's own draft survives behind it.
         At ≥1024 the column is also
         sticky: a long manuscript scrolls the page under the
         editor, and the rail — capped a viewport tall minus its
         own chrome — holds its place beside the writing instead of
         being carried out of sight with the page's top; `top-4`
         and the 17.5rem max-height budget keep the box inside the
         viewport at any height it takes. The budget is the chrome
         above the rail, the band included: the band holds the rail's
         own filter field, and the field's drafted height (36 px) is
         part of what the rail must leave room for. The arithmetic,
         measured at 1280×720 on the long rail — the budget's own
         case, the band wearing its field: the shell's 61 px bar, the
         page's 40 px top padding, the back link's 24 px line box,
         the h1's 8 px margin and 26 px line, the band's 24 px margin
         and 68 px (the field plus the band's own padding), and the
         workbench row's 24 px margin — 275 px ≈ 17.2rem, and the
         constant holds the half-rem step above it (280 px), 5 px of
         slack for line-box rounding. Nothing in that sum has a
         rail-width term — every line sits above the workbench row,
         which spans the container, not the rail — so the width's
         224 → 288 step re-derives the budget to the same 17.5rem.
         The drafted header, tab row and
         the two foot widgets are the rail's own chrome — they stand
         inside this cap and squeeze the list, not the budget. */
      className="flex w-72 shrink-0 flex-col lg:sticky lg:top-4 lg:max-h-[calc(100dvh-17.5rem)] lg:pr-6 max-lg:absolute max-lg:top-0 max-lg:bottom-0 max-lg:left-0 max-lg:z-30 max-lg:max-w-full max-lg:overflow-y-auto max-lg:rounded-[var(--radius-lg)] max-lg:border max-lg:border-rule max-lg:bg-panel max-lg:p-4 max-lg:shadow-overlay"
      aria-label={t("chapters.heading")}
    >
      <RailHeader bookTitle={bookTitle} chapterCount={chapterCount} words={railWords} />
      <RailTabs value={railTab} onChange={setRailTab} />
      {railTab === "chapters" ? (
        /* The chapters' panel: the list and its deeds, exactly as they
           stood — the tab row is the only thing new above them. The
           panel bounds the height the list scrolls in, the way the
           aside used to. `flex-1`/`min-h-0` are the desktop column's:
           at ≥1024 the rail is capped and the panel takes the
           remainder so the list scrolls inside itself. In the drawer
           (<1024) the panel must NOT grow or shrink — a growing panel
           under a too-small cap collapses to nothing and its content
           spills below the foot widgets, which paint over it (later
           DOM): the rows and the add button become unclickable. Below
           the breakpoint the drawer itself is the scroll container and
           the panel is plain flow. */
        <div
          role="tabpanel"
          id="rail-panel-chapters"
          aria-labelledby="rail-tab-chapters"
          className="flex flex-col px-3 lg:min-h-0 lg:flex-1"
        >
          {chapterCount === 0 ? (
            <p className="mt-2 text-body text-muted">{t("chapters.empty")}</p>
          ) : null}
          {/* The list scrolls itself in the desktop columns only (its
              bounded height is a column fact); below 1024 the drawer
              scrolls whole, so the list must neither clip nor shrink
              there. The desktop column is sticky (the rail holds its
              place beside the editor while a long manuscript scrolls
              the page), and the rows it shows are the filtered list —
              the walk below indexes into what rendered. The cards stand
              a drafted step apart, on the panel's own gutter. */}
          <ul
            ref={railListRef}
            className="mt-3 flex flex-col gap-1.5 lg:min-h-0 lg:flex-1 lg:overflow-y-auto"
          >
            {visibleChapters.map((chapter, index) => {
              const isCurrent = chapter.id === active;
              const title = chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 });
              // The count is spoken as the sentence the footer prints
              // ("… 2.107 Wörter") and shown as its number alone — the
              // localized grouping, so the row and the footer read alike.
              const words = chapterCounts.get(chapter.id) ?? 0;
              // The drafted eyebrow: "Kapitel 01" — the position, zero-padded
              // to two places. The rail stays digits; only the editor's
              // eyebrow is written out. The catalog sentence is the fallback
              // title's own, so the two wordings can never drift apart.
              const eyebrow = t("chapters.defaultTitle", {
                n: String(chapter.position + 1).padStart(2, "0"),
              });
              // interim: no chapter status field — shares shelf follow-up #784
              // (every chapter wears the draft's default line until one exists).
              const status = t("chapters.statusFirstDraft");
              // One tab stop in the list, whatever the filter did to it:
              // the open chapter's row — or, when the filter hides that
              // row (or the book has no open chapter yet), the first
              // visible one, so the keyboard always has a way in.
              const isTabStop =
                walkedIndex !== null
                  ? walkedIndex === index
                  : isCurrent || (activeVisibleIndex < 0 && index === 0);
              return (
                <li
                  key={chapter.id}
                  /* The slot is the drop target, and the marker is the
                     slot's own top edge — the row the drop would land
                     at — so the row card's classes stay untouched (spec
                     §7: no markup or role change). `onDragOver` must
                     preventDefault for the drop to be allowed at all,
                     and only while a drag of ours is in flight. */
                  onDragOver={(event) => {
                    if (dragId.current === null) return;
                    event.preventDefault();
                    setDropIndex(index);
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    const source = dragId.current;
                    dragId.current = null;
                    setDropIndex(null);
                    if (source === null) return;
                    void moveTo(source, index);
                  }}
                  className={
                    dropIndex === index && dragId.current !== null ? DROP_HINT : undefined
                  }
                >
                  <button
                    type="button"
                    aria-current={isCurrent ? "true" : undefined}
                    /* The name spells the card in exactly its DOM order —
                       title, eyebrow, figure, status — because the visible
                       words must reach the reader as one unbroken sequence
                       (axe's label-content rule reads the DOM order, hidden
                       chrome included), and it must open with the title
                       because the E2E locators anchor on it. The title
                       therefore leads the DOM too: the meta row sits above
                       it only by flex `order`, the draft's layout. */
                    aria-label={`${title} ${eyebrow} ${formatWordCount(words)} ${status}`}
                    tabIndex={isTabStop ? 0 : -1}
                    /* The desktop drag: the row is the grab, the slot
                       above is the landing. Wired only while no filter
                       is active — a filtered list has no unambiguous
                       drop index (Task 12's rule). */
                    draggable={railFilter === null}
                    onDragStart={
                      railFilter === null
                        ? () => {
                            dragId.current = chapter.id;
                          }
                        : undefined
                    }
                    onDragEnd={() => {
                      dragId.current = null;
                      setDropIndex(null);
                    }}
                    onKeyDown={(event) => {
                      // Alt+↑/↓ moves the focused row one step; the
                      // plain arrows keep the walk. The handler is the
                      // row's own, so the editor's Alt+arrows never
                      // reach it — there they keep the OS meaning.
                      if (
                        event.altKey &&
                        (event.key === "ArrowDown" || event.key === "ArrowUp")
                      ) {
                        event.preventDefault();
                        void move(chapter.id, event.key === "ArrowDown" ? 1 : -1);
                        return;
                      }
                      walkRail(event, index);
                    }}
                    onClick={() => {
                      // The chapter already open is no switch: a second
                      // history entry for the same address would only eat
                      // the back button. Either way the walk is over —
                      // the tab stop returns to the selection.
                      setWalkedIndex(null);
                      if (chapter.id === active) return;
                      select(chapter.id);
                    }}
                    className={`${ROW_FRAME} ${isCurrent ? ROW_CURRENT : ROW_REST}`}
                  >
                    <span aria-hidden="true" className={isCurrent ? GRIP_CURRENT : GRIP_REST}>
                      <Icon name="dragIndicator" size={16} />
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col">
                      {/* DOM order is the reading order — title first — and
                          flex `order` lays the card out as the draft draws
                          it: meta row on top, title under it, status at
                          the foot. The `{" "}` separators are the old row's
                          own rule: the spans' text must not fuse in the
                          DOM ("Kapitel 1Kapitel 01…"), or the name's words
                          and the content's words stop matching (a
                          whitespace-only flex child renders nothing, but
                          the text node still speaks). */}
                      <span className="order-2 mt-0.5 block truncate text-emph text-foreground">
                        {title}
                      </span>{" "}
                      <span className="order-1 flex items-center justify-between gap-1">
                        <span
                          className={`text-eyebrow uppercase ${isCurrent ? "text-area-writing" : "text-muted"}`}
                        >
                          {eyebrow}{" "}
                        </span>
                        <span
                          className={`text-meta tabular-nums ${isCurrent ? "font-semibold text-primary" : "text-muted"}`}
                        >
                          {formatWordCount(words)}{" "}
                        </span>
                      </span>
                      {/* The status line: dot then line, the drafted
                          first-draft mark — see the interim note above.
                          On the wash the line pairs with the wash's own
                          foreground; muted there is below AA. */}
                      <span className="order-3 mt-1 flex items-center gap-2">
                        <span
                          aria-hidden="true"
                          className="h-1.5 w-1.5 shrink-0 rounded-full bg-outline-variant"
                        />
                        <span
                          className={`min-w-0 truncate text-meta ${isCurrent ? "text-secondary-container-foreground" : "text-muted"}`}
                        >
                          {status}
                        </span>
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {/* The drafted add-chapter action: full width, dense, the
              plus glyph beside the label — the existing create path,
              restyled (the ladder's quiet voice; the draft's tonal
              chip paint is not one of the matrix's five paints). */}
          <Button
            variant="secondary"
            size="sm"
            icon={<Icon name="plus" size={16} />}
            onClick={() => void onCreateChapter()}
            className="mt-3 w-full justify-center"
          >
            {t("chapters.new")}
          </Button>
          {orderFailed ? (
            <Notice tone="danger" live="alert" className="mt-2">
              {t("chapters.orderFailed")}
            </Notice>
          ) : null}
          {createFailed ? (
            <Notice tone="danger" live="alert" className="mt-2">
              {t("chapters.errorCreate")}
            </Notice>
          ) : null}
        </div>
      ) : (
        /* The Szenen panel: the honest stand-in until the rail grows a
           scenes view of its own — one sentence and the planning door.
           Same wiring as the chapters' panel: the drawer's children are
           natural flow below 1024, the desktop column's remainder
           above. */
        <div
          role="tabpanel"
          id="rail-panel-scenes"
          aria-labelledby="rail-tab-scenes"
          className="flex flex-col lg:min-h-0 lg:flex-1"
        >
          <RailScenesEmpty novelId={novelId} />
        </div>
      )}
      {/* The rail's drafted foot (screens/writing/workspace.html, the
          drawer's two bottom cards): the tension arc with the open
          chapter's marker, and the session card, honestly neutral. They
          stand on the rail — both tabs — the way the draft draws them at
          the drawer's foot, and the list above squeezes so they never
          leave the viewport. */}
      <StoryArc position={arcPosition} total={chapterCount} />
      <SessionStats />
    </aside>
  );
}
