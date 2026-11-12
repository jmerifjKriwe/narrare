import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";
import { useState } from "react";

import type { Chapter } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { formatWordCount } from "@shell/lib/words";
import { Button } from "@shell/ui/Button";
import { Notice } from "@shell/ui/Notice";
import { Row } from "@shell/ui/Row";

import { RailHeader, RailScenesEmpty, RailTabs, type RailTabId } from "./RailHeader";

// The drag's drop marker: a 2 px primary edge at the slot's top — the row
// a drop would land at. Its look is the spec's "left to the builder"; it
// lives on the slot so the Row's own classes stay untouched.
const DROP_HINT = "shadow-[inset_0_2px_0_var(--primary)]";

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
  return (
    <aside
      /* Beside the editor at ≥1024 (the columns the desktop E2Es
         pin); below, a drawer over it. The 224 the rail takes are
         the desktop arithmetic's own — the gutter to the prose lives
         inside the column (lg:pr-6), so rail + column + dock sum to
         the container with no gap of their own; the column's 16 px
         padding is the gap the card's ring needs. The list bounds
         its height and scrolls inside itself (Review Focus 2); below
         the breakpoint the whole drawer scrolls instead. The drawer
         paints one z-step above the dock's: opening it over a live
         dock covers the dock without unmounting it, so the dock's
         own draft survives behind it. At ≥1024 the column is also
         sticky: a long manuscript scrolls the page under the
         editor, and the rail — capped a viewport tall minus its
         own chrome — holds its place beside the writing instead of
         being carried out of sight with the page's top; `top-4`
         and the 17rem max-height budget keep the box inside the
         viewport at any height it takes. The budget is the chrome
         above the rail, the band included: the band holds the rail's
         own filter field, and the field's drafted height (36 px) is
         part of what the rail must leave room for. The drafted
         header and tab row are the rail's own chrome — they stand
         inside this cap and squeeze the list, not the budget. */
      className="flex w-56 shrink-0 flex-col lg:sticky lg:top-4 lg:max-h-[calc(100dvh-17rem)] lg:pr-6 max-lg:absolute max-lg:top-0 max-lg:bottom-0 max-lg:left-0 max-lg:z-30 max-lg:w-72 max-lg:max-w-full max-lg:overflow-y-auto max-lg:rounded-[var(--radius-lg)] max-lg:border max-lg:border-rule max-lg:bg-panel max-lg:p-4 max-lg:shadow-overlay"
      aria-label={t("chapters.heading")}
    >
      <RailHeader bookTitle={bookTitle} chapterCount={chapterCount} words={railWords} />
      <RailTabs value={railTab} onChange={setRailTab} />
      {railTab === "chapters" ? (
        /* The chapters' panel: the list and its deeds, exactly as they
           stood — the tab row is the only thing new above them. The
           panel bounds the height the list scrolls in, the way the
           aside used to. */
        <div
          role="tabpanel"
          id="rail-panel-chapters"
          aria-labelledby="rail-tab-chapters"
          className="flex min-h-0 flex-1 flex-col"
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
              the walk below indexes into what rendered. */}
          <ul
            ref={railListRef}
            className="mt-3 flex flex-col lg:min-h-0 lg:flex-1 lg:overflow-y-auto"
          >
            {visibleChapters.map((chapter, index) => {
              const isCurrent = chapter.id === active;
              const title = chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 });
              // The count is spoken as the sentence the footer prints
              // ("… 2.107 Wörter") and shown as its number alone — the
              // localized grouping, so the row and the footer read alike.
              const words = chapterCounts.get(chapter.id) ?? 0;
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
                     at — so the Row's classes stay untouched (spec §7:
                     no markup or role change). `onDragOver` must
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
                  <Row
                    current={isCurrent}
                    selected={isCurrent}
                    /* The name is composed, not computed: title and count
                       sit in separate flex items, and every accname
                       implementation stitches those together by its own
                       whitespace rules — a title ending in a digit would
                       reach the reader as one number ("Kapitel 11"). The
                       label spells exactly the words on screen, with the
                       separator made explicit. */
                    aria-label={`${title} ${t("chapters.wordCount", { count: words })}`}
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
                    /* h-7 is the single-line control height: a wrapped title grows the row past it (the hits' `h-auto` precedent) instead of painting over the next row. */
                    className="h-auto min-h-7"
                  >
                    {/* The separator is visible text, not only label:
                        axe requires the visible words to be part of the
                        accessible name, and without a space in the
                        content the reader would still stitch "Kapitel"
                        and the count into one number. The count stays
                        foreground — muted on the selected row's wash is
                        below AA, the exact case the Row's own docs name. */}
                    {/* Wrap, never clamp: a 60-char title needs three lines in this rail, so a two-line clamp would still ellipsize exactly the titles this fixes. */}
                    <span className="min-w-0 flex-1 break-words">
                      {title}{" "}
                    </span>
                    <span className="shrink-0 text-meta tabular-nums">
                      {formatWordCount(words)}
                    </span>
                  </Row>
                </li>
              );
            })}
          </ul>
          <Button onClick={() => void onCreateChapter()} className="mt-3 w-full">
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
           scenes view of its own — one sentence and the planning door. */
        <div
          role="tabpanel"
          id="rail-panel-scenes"
          aria-labelledby="rail-tab-scenes"
          className="flex min-h-0 flex-1 flex-col"
        >
          <RailScenesEmpty novelId={novelId} />
        </div>
      )}
    </aside>
  );
}
