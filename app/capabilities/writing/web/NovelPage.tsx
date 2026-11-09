import { Link, Outlet, useNavigate, useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { client } from "@shell/lib/api/client";
import { docks } from "@shell/lib/generated/docks";
import { useTranslation } from "@shell/lib/i18n";
import { queryClient, useDeleteChapter } from "@shell/lib/query";
import { unsavedStatus } from "@shell/lib/save";
import { formatWordCount } from "@shell/lib/words";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Input } from "@shell/ui/field";
import { ActionMenu } from "@shell/ui/Menu";
import { Icon } from "@shell/ui/icons";
import { Notice } from "@shell/ui/Notice";
import { Row } from "@shell/ui/Row";

import { ChapterEditor } from "./ChapterEditor";
import { ChapterDeleteDialog, ChapterRenameDialog } from "./ChapterDialogs";
import { useChapterRail } from "./novel/useChapterRail";
import { useNovelDraft } from "./novel/useNovelDraft";
import { useNovelWorkspace } from "./novel/useNovelWorkspace";
import type { FocusStep } from "./routes";

// The step machine as data: no arithmetic on the union, and the ends are
// their own neighbours so a stray call cannot walk off the scale.
const DEEPEN: Record<FocusStep, FocusStep> = { 0: 1, 1: 2, 2: 2 };
const RELEASE: Record<FocusStep, FocusStep> = { 0: 0, 1: 0, 2: 1 };

// The drag's drop marker: a 2 px primary edge at the slot's top — the row
// a drop would land at. Its look is the spec's "left to the builder"; it
// lives on the slot so the Row's own classes stay untouched.
const DROP_HINT = "shadow-[inset_0_2px_0_var(--primary)]";

/** The novel workbench: the chapter rail beside the editor, panel state in the URL. */
export function NovelPage() {
  const t = useTranslation();
  // By route id, not the route object: the page stands apart from
  // routes.tsx, and the registered router still types `id` from the string.
  const { id: novelId } = useParams({ from: "/novels/$id" });
  const navigate = useNavigate();
  // The workbench's reads, selection and panel state live in the hooks —
  // the page composes them and renders the same DOM.
  const {
    novelQuery,
    chapters,
    chapterCounts,
    pending,
    failed,
    refreshFailed,
    retry,
    active,
    select,
    current,
    currentIndex,
    focus,
    collapsed,
    narrow,
    showRail,
    openDock,
    activeDock,
    step,
    toggleRail,
    toggleDock,
    offer,
    resolveOffer,
    hintShown,
  } = useNovelWorkspace(novelId);
  const { status, schedule, discard, draft, changeTitle, rename, guardOpen, answerGuard } =
    useNovelDraft(novelId, current);
  const {
    visibleChapters,
    activeVisibleIndex,
    railListRef,
    walkedIndex,
    setWalkedIndex,
    walkRail,
    railFilter,
    setRailFilter,
    orderFailed,
    move,
    moveTo,
    dragId,
    dropIndex,
    setDropIndex,
  } = useChapterRail(novelId, chapters, active);
  // The rail's own create failure: a chapter the user asked for that never
  // arrived must say so beside the button, not vanish into a silent click.
  const [createFailed, setCreateFailed] = useState(false);

  // The keyboard contract. Phase 5's ghost text layers ABOVE this: its Esc
  // discards a suggestion first and marks the event handled, and only an Esc
  // that arrives unhandled here steps the focus back. F9 has no such tenant.
  useEffect(() => {
    const onKeydown = (event: KeyboardEvent) => {
      // A held key repeats, and an IME composition emits keydown the page
      // must not act on: a repeated F9 would race the URL writes, and a
      // composition's Esc would tear the mode mid-word.
      if (event.repeat || event.isComposing) return;
      if (event.defaultPrevented) return;
      // The leave dialog owns the keyboard while it stands: stepping the
      // focus from under an unanswered ask would start a second navigation
      // behind the one that is waiting for this answer.
      if (guardOpen) return;
      if (event.key === "F9") {
        event.preventDefault();
        step(DEEPEN[focus]);
      } else if (event.key === "Escape") {
        event.preventDefault();
        step(RELEASE[focus]);
      }
    };
    window.addEventListener("keydown", onKeydown);
    return () => window.removeEventListener("keydown", onKeydown);
  }, [focus, step, guardOpen]);

  /** Create and select an untitled chapter, or show a retryable failure in the rail. */
  async function createChapter() {
    // An explicit empty title: the placeholder is a display concern, and
    // storing a title would freeze one locale's wording into the database.
    // The server treats an empty title exactly like an omitted one.
    // The filter clears with the ask — the new chapter must land in the
    // visible list, and the rail's own button is the one create path that
    // runs here (the palette's command arrives through the length effect).
    setRailFilter(null);
    setCreateFailed(false);
    try {
      const { data: chapter } = await client.POST(
        "/api/writing/novels/{novel_id}/chapters",
        { params: { path: { novel_id: novelId } }, body: { title: "" } },
      );
      if (!chapter) {
        // A refusal is the button's own story: the user asked for a chapter
        // and none arrived.
        setCreateFailed(true);
        return;
      }
      // The rail's list is the cache now: the new row arrives through the
      // refetch this invalidation triggers, not through a hand-patched
      // array — every view of the key (the rail, later the palette) reads
      // the same answer. Awaiting it also orders the selection: the param
      // is written only once the list that holds the row has landed, so
      // the dead-param cleanup above can never mistake the new address
      // for a dead one.
      await queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
      // The bookshelf hero names the last-touched book, and its truth is the
      // novel row's updated_at — a chapter write is the most common way that
      // changes, so the shelf's ["novels"] cache must not outlive this POST.
      // The prefix covers the row this page reads as well. The ask rides
      // alongside, not awaited: the selection waits only for the list it
      // names, never for the rest of the book.
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
      select(chapter.id);
    } catch {
      // The service is not answering at all and the proxy refuses: the same
      // refusal the rail must name as any other.
      setCreateFailed(true);
    }
  }

  // The runhead's menu (D3's narrowing): the open chapter's actions live
  // in its runhead, and the two that need more than a keystroke — rename,
  // delete — open the dialogs that own them. The rail keeps its plain
  // rows; the menu is the touch path's way to every chapter deed.
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const deleteChapter = useDeleteChapter(novelId);

  /** Delete one chapter: the one orchestrated sequence the delete dialog's
   *  confirm runs. Retire comes first and provably — when the chapter is
   *  the open one, its pending document is dropped before the request
   *  flies, so no PUT can arrive at a chapter the delete is about to kill
   *  and no `save.failed` names a deletion the user asked for. The retire
   *  is also what makes the navigation honest: the blocker below would
   *  flush on any navigation, and a flush after this `discard()` finds an
   *  empty slot (the generation bump retires any answer still in flight)
   *  — the neighbour opens without a phantom write either way. A chapter
   *  that is not the open one dies without a navigation: the editor and
   *  the address keep what they hold (D7). */
  async function confirmDeleteChapter(chapterId: string): Promise<boolean> {
    const isOpen = chapterId === current?.id;
    // What the guards would protect, asked before the retire can empty
    // it: a clean chapter — idle or saved, nothing typed, nothing failed
    // — has no words to hand back, and inventing them would be a phantom
    // save ("Gespeichert" for text nobody edited) or a phantom failure.
    const hadUnsaved = unsavedStatus(status);
    // The neighbour is named from the list the book has now, before
    // anything flies: the chapter that takes this one's place — the next,
    // else the previous (D7). Only the open chapter's death opens one.
    const index = chapters.findIndex((row) => row.id === chapterId);
    const neighbour = chapters[index + 1] ?? chapters[index - 1] ?? null;
    if (isOpen) discard();
    try {
      await deleteChapter.mutateAsync(chapterId);
    } catch {
      // A refused delete hands the retired words back — only the words
      // that were pending: both fields dirty again, the status pending,
      // so the leave guards protect them and the next debounce carries
      // them to a chapter that still lives. A clean chapter stays clean.
      if (isOpen && hadUnsaved) {
        schedule(draft, "title");
        schedule(draft, "body");
      }
      // The refusal is the dialog's to name; nothing moved, and the
      // neighbour this run computed is still only a computation.
      return false;
    }
    // The 204 is the server's word, and the mutation's own invalidation is
    // already carrying it: the refetch's answer — not a hand-patched list —
    // is what removes the row, exactly the create path's contract with the
    // cache. The selection below runs in this same tick, ahead of that
    // answer (a navigation commits in a microtask; the refetch lands on a
    // macrotask), which is what keeps the dead-param cleanup honest: by the
    // time the rows no longer hold this chapter, the address no longer
    // names it. A synchronous removal here would open exactly the window
    // the cleanup exists to close.
    if (!isOpen || neighbour === null) {
      if (!isOpen) return true;
      // The book's last chapter: the empty state, and the address loses
      // its dead value by replace — a cleanup, not a selection, so the
      // back button keeps no step for it.
      void navigate({
        to: ".",
        search: (prev) => ({ ...prev, chapter: undefined }),
        replace: true,
      });
      return true;
    }
    // A push, the rail's own selection semantics: the back button walks
    // back to the address the deleted chapter wore, and history keeps
    // the delete as the step it was.
    select(neighbour.id);
    return true;
  }

  // F22's choice: below the workbench breakpoint the rail and the dock stay
  // overlays — the viewport floor pins covering, never squeezing — so they
  // get what an overlay owes the page behind it: a scrim that takes the
  // pointer's dismissal, and `inert` on the work they cover, which is the
  // focus containment. React Aria's modal machinery would remount the
  // dock's Outlet to trap focus; `inert` contains it without the remount,
  // and the toolbar band above the row stays live — it is the workbench's
  // own controls, and the way either drawer closes. The rail half is gated
  // on the rail's own render condition: an overlay with no drawer would
  // scrim the loading and outage states and inert their retry.
  const railOverlay = narrow && showRail && !pending && !failed;
  const dockOverlay = narrow && openDock !== null;

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10">
      {focus < 2 ? (
        <>
          <Link
            to="/"
            className="text-body text-muted underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("nav.back")}
          </Link>
          {/* The heading names the book only when the book's row is here: an
              empty h1 on the outage page would be a heading about nothing. */}
          {novelQuery.data ? (
            <h1 className="mt-2 text-title font-semibold tracking-tight">
              {novelQuery.data.title}
            </h1>
          ) : null}
        </>
      ) : null}

      {focus === 2 && hintShown ? (
        <p role="status" className="mt-4 text-center text-meta text-muted">
          {t("workspace.focusHint")}
        </p>
      ) : null}

      {/* The toolbar band (F26): one gap group of icon buttons — focus, rail,
          the dock tabs the registry names. The rail's collapse control lives
          here now, not above the chapter list; at depth 1 the rail is hidden,
          so its toggle is hidden with it. The dock tabs keep their pressed
          state (they toggle); the group's name is the one dock control the
          toolbar carries — no separate dock toggle beside the tabs. */}
      {focus < 2 ? (
        <div className="mt-6 flex flex-wrap items-center gap-2">
          {/* The band wraps before it overflows: a phone's 328 px content
              box cannot hold four icon buttons and an input's automatic
              minimum on one line, and the field is `min-w-0` so it shrinks
              into the space the buttons leave (or takes a line of its own)
              instead of pushing the page's gutter aside. */}
          <Button
            variant="icon"
            icon={<Icon name="focus" />}
            label={t("workspace.focusToggle")}
            aria-pressed={focus > 0}
            onClick={() => step(focus === 0 ? 1 : 0)}
          />
          {focus === 0 ? (
            <Button
              variant="icon"
              icon={<Icon name={collapsed ? "railShow" : "railHide"} />}
              label={t("workspace.railToggle")}
              aria-pressed={collapsed}
              onClick={toggleRail}
            />
          ) : null}
          <div role="group" aria-label={t("workspace.dockToggle")} className="flex items-center gap-2">
            {docks.map((dock) => (
              <Button
                key={dock.id}
                variant="icon"
                icon={<Icon name={dock.id} />}
                label={t(dock.titleKey)}
                aria-pressed={activeDock?.path === dock.path}
                onClick={() => toggleDock(dock)}
              />
            ))}
          </div>
          {/* The rail's filter (Task 12): the long rail's own field, in the
              band that already holds the rail's collapse control. It stands
              only above twenty chapters and only while the rail itself is
              on screen — a field for a hidden list would be a promise with
              no subject. The input's accessible name is the fuller phrase
              that carries the visible label inside it, so the name a reader
              hears says what the field matches. */}
          {focus === 0 && showRail && !pending && !failed && chapters.length > 20 ? (
            <Field label={t("chapters.railFilter")} className="ml-auto w-40 min-w-0">
              <Input
                type="search"
                value={railFilter ?? ""}
                onChange={(event) => {
                  const value = event.target.value;
                  // The walk ends with the question: its row may no longer
                  // be in the list the next answer renders, and a stale
                  // index would leave that list without a tab stop.
                  setWalkedIndex(null);
                  setRailFilter(value.trim() === "" ? null : value);
                }}
                aria-label={t("chapters.railFilterAria")}
                className="min-w-0"
              />
            </Field>
          ) : null}
        </div>
      ) : null}

      {/* The workbench: the rail beside the editor, so writing never scrolls
          past the chapter list. The container is one width in both states
          (F25) — 1200, the shelf's own, so the bar, the shelf and this page
          share one left edge: rail 224, column 592, dock 352, so the card's
          576 and the 16 px gap it leaves the ring fit with no slack to
          spare. The frame stays while the book
          loads or fails — the toolbar and the docks are independent of the
          book's row, and a dock's own outage story must stay reachable.
          Below the desktop breakpoint the row is the overlays' containing
          block: the panels float above the editor instead of standing
          beside it. */}
      <div className="mt-6 flex items-start max-lg:relative">
        {railOverlay ? (
          <div
            aria-hidden="true"
            onClick={toggleRail}
            className="hidden max-lg:absolute max-lg:inset-0 max-lg:z-10 max-lg:block max-lg:bg-scrim"
          />
        ) : null}
        {/* The rail needs the chapter list. While it loads, or after the
            load failed, there is no list to be empty — the empty copy would
            mask exactly the state this page just named in the editor column. */}
        {showRail && !pending && !failed ? (
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
               and the 16rem max-height budget keep the box inside the
               viewport at any height it takes. */
            className="flex w-56 shrink-0 flex-col lg:sticky lg:top-4 lg:max-h-[calc(100dvh-16rem)] lg:pr-6 max-lg:absolute max-lg:top-0 max-lg:bottom-0 max-lg:left-0 max-lg:z-30 max-lg:w-72 max-lg:max-w-full max-lg:overflow-y-auto max-lg:rounded-[var(--radius-lg)] max-lg:border max-lg:border-rule max-lg:bg-panel max-lg:p-4 max-lg:shadow-overlay"
            aria-label={t("chapters.heading")}
          >
            <h2 className="text-emph font-semibold tracking-tight">{t("chapters.heading")}</h2>
            {chapters.length === 0 ? (
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
                    >
                      {/* The separator is visible text, not only label:
                          axe requires the visible words to be part of the
                          accessible name, and without a space in the
                          content the reader would still stitch "Kapitel"
                          and the count into one number. The count stays
                          foreground — muted on the selected row's wash is
                          below AA, the exact case the Row's own docs name. */}
                      <span className="min-w-0 flex-1 truncate">
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
            <Button onClick={() => void createChapter()} className="mt-3 w-full">
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
          </aside>
        ) : null}

        <section
          className="flex min-w-0 flex-1 flex-col items-center lg:pr-4"
          inert={railOverlay || dockOverlay || undefined}
        >
          {/* The writing surface is the card (F18): ChapterEditor paints it,
              the page only leaves it the column. The arithmetic is the
              workspace's: rail 224 + column 592 + dock 352 = the container's
              1168; the column is the card's 576 plus the 16 px gap the focus
              ring needs, so the ring never lands on the dock's seam. The
              measure stays 544 inside the card, wherever the dock is. */}
          <div className="w-full py-6">
            <div className="mx-auto w-full max-w-[576px]">
              {pending ? (
              // The page has asked and is waiting — a named state, not a blank
              // or empty-looking book. Quiet and polite: nothing is wrong.
              <Notice tone="quiet" live="status" className="mt-6">
                {t("chapters.loading")}
              </Notice>
            ) : failed ? (
              // The book could not be loaded — refused or unreachable, with
              // nothing on screen to keep. The failure is named where the
              // retry is one press away (the shelf's outage shape).
              <Notice
                tone="danger"
                live="alert"
                className="mt-6"
                action={
                  <Button variant="secondary" onClick={retry}>
                    {t("chapters.retry")}
                  </Button>
                }
              >
                {t("chapters.errorLoad")}
              </Notice>
            ) : (
              <>
                {refreshFailed ? (
                  // The refresh failed, but the chapters on screen are the
                  // last loaded ones: a quiet note beside the work, not the
                  // outage's louder clothes — the editor and the rail stay,
                  // and the retry asks again. The shelf's derived-boolean
                  // pattern: one Notice, `live="status"` keeps it from being
                  // silent to a screen reader — background speech about work
                  // that stays, not an alert about work that is gone.
                  <Notice
                    tone="quiet"
                    live="status"
                    className="mt-6"
                    action={
                      <Button variant="secondary" onClick={retry}>
                        {t("chapters.retry")}
                      </Button>
                    }
                  >
                    {t("chapters.refreshFailed")}
                  </Notice>
                ) : null}
                {orderFailed && !showRail ? (
                  // The same refusal the rail's aside names, for the
                  // states that have no rail to name it: the runhead's
                  // move items render at a focus depth that hides the
                  // rail and with the column collapsed, and a 409 there
                  // would revert silently. One of the two notices is
                  // mounted at any time — `showRail` partitions them —
                  // so the alert is announced once, from the surface
                  // that is on screen.
                  <Notice tone="danger" live="alert" className="mt-6">
                    {t("chapters.orderFailed")}
                  </Notice>
                ) : null}
                {current ? (
                  <ChapterEditor
                    key={current.id}
                    chapterId={current.id}
                    body={current.body}
                    title={draft.title}
                    onTitleChange={changeTitle}
                    status={status}
                    schedule={schedule}
                    proposal={offer ?? undefined}
                    onProposalResolve={resolveOffer}
                    bookTitle={novelQuery.data?.title}
                    chapterNumber={current.position + 1}
                    chapterTotal={chapters.length}
                    focusDepth={focus}
                    actions={
                      <ActionMenu
                        label={t("chapters.actions")}
                        // The trigger names the chapter as the page holds
                        // it — the draft, not the cache row — so a typed
                        // title reaches the button's name before the save
                        // lands (the row catches up on the refetch).
                        triggerAriaLabel={t("chapters.actionsFor", {
                          title:
                            draft.title ||
                            t("chapters.defaultTitle", { n: current.position + 1 }),
                        })}
                        items={[
                          {
                            id: "rename",
                            label: t("chapters.rename"),
                            onSelect: () => setRenameOpen(true),
                          },
                          {
                            id: "moveUp",
                            // The ends are their own no-ops, offered but
                            // disabled: the shortcut the hint names is the
                            // rail's own Alt+↑ (D6), discoverable exactly
                            // where the action lives. A filter disables
                            // the move wherever the row sits — a filtered
                            // list has no unambiguous neighbour — and the
                            // label itself says why, so the reason travels
                            // with the item to readers and screens alike.
                            label:
                              railFilter === null
                                ? t("chapters.moveUp")
                                : t("chapters.moveUpFiltered"),
                            shortcut: "Alt+↑",
                            disabled: railFilter !== null || currentIndex <= 0,
                            onSelect: () => void move(current.id, -1),
                          },
                          {
                            id: "moveDown",
                            label:
                              railFilter === null
                                ? t("chapters.moveDown")
                                : t("chapters.moveDownFiltered"),
                            shortcut: "Alt+↓",
                            disabled:
                              railFilter !== null || currentIndex >= chapters.length - 1,
                            onSelect: () => void move(current.id, 1),
                          },
                          {
                            id: "delete",
                            label: t("chapters.delete"),
                            onSelect: () => setDeleteOpen(true),
                          },
                        ]}
                      />
                    }
                  />
                ) : null}
              </>
            )}
            </div>
          </div>
        </section>

        {dockOverlay && !railOverlay ? (
          <div
            aria-hidden="true"
            onClick={() => {
              if (openDock) toggleDock(openDock);
            }}
            className="hidden max-lg:absolute max-lg:inset-0 max-lg:z-10 max-lg:block max-lg:bg-scrim"
          />
        ) : null}

        {/* The right dock: the open registry row's child route renders here —
            the tab's navigation decided which one, and the matched child is
            the dock's open state. The tab is the dock's one control: it
            toggles, the back button closes, and no second close control
            squats in the header (one control per panel). The column scrolls
            alone so a long answer never scrolls the editor out of view. */}
        {openDock ? (
          <aside
            /* Same contract as the rail, mirrored: a drawer from the
               right below 1024, the desktop's dock column at ≥1024. The
               352 the dock takes are the arithmetic's own; the column's
               16 px padding is the gap the card's ring needs. The column is
               a flex
               stack so the title holds its place while the body under it
               takes the remaining height and scrolls alone. The rail's
               drawer sits a z-step above this one: a rail opened over a
               live dock covers it without unmounting it, so the dock's
               in-progress ask survives behind the drawer — and while it is
               covered the dock goes `inert`, so the keyboard cannot land on
               controls the drawer hides. */
            className="flex w-88 shrink-0 flex-col rounded-[var(--radius-lg)] border border-rule bg-panel p-4 max-lg:absolute max-lg:top-0 max-lg:bottom-0 max-lg:right-0 max-lg:z-20 max-lg:max-w-full max-lg:shadow-overlay lg:max-h-[calc(100dvh-16rem)] lg:pl-6"
            aria-label={t(openDock.titleKey)}
            inert={railOverlay || undefined}
          >
            <h2 className="text-emph font-semibold tracking-tight">{t(openDock.titleKey)}</h2>
            {/* The dock owns its scroll: it takes the height it needs up to
                the viewport's own cap (the rail's arithmetic), and the body
                under the title scrolls inside it. A fixed 50 vh window used
                to cut a row in half while 200 px of the page stood unused. */}
            <div className="mt-3 min-h-0 flex-1 overflow-y-auto">
              <Outlet />
            </div>
          </aside>
        ) : null}
      </div>

      {/* The chapter's two deeds that need more than a keystroke (D3's
          runhead menu): the rename dialog and the delete dialog, both
          controlled — the menu was the press, the dialogs are the asks.
          They stand only while a chapter is open: the runhead's menu is
          their one trigger. */}
      {current ? (
        <>
          <ChapterRenameDialog
            chapter={current}
            open={renameOpen}
            onOpenChange={setRenameOpen}
            onRenamed={rename}
          />
          <ChapterDeleteDialog
            novelId={novelId}
            chapter={current}
            open={deleteOpen}
            onOpenChange={setDeleteOpen}
            onDelete={confirmDeleteChapter}
          />
        </>
      ) : null}

      {/* The leave guard's ask (F21): the shell's dialog, not window.confirm
          — the question the gate owes, in the page's own clothes. Escape and
          an outside click are dismissals: the work stays. */}
      <Dialog
        title={t("save.leaveTitle")}
        isOpen={guardOpen}
        onOpenChange={(open) => {
          if (!open) answerGuard(false);
        }}
      >
        {() => (
          <>
            <p className="mt-2 text-body text-muted">{t("save.confirmLeave")}</p>
            <div className="mt-6 flex justify-end gap-3">
              <Button onClick={() => answerGuard(false)}>{t("save.leaveStay")}</Button>
              <Button variant="primary" onClick={() => answerGuard(true)}>
                {t("save.leaveGo")}
              </Button>
            </div>
          </>
        )}
      </Dialog>
    </div>
  );
}
