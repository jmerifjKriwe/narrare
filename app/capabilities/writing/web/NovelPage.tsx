import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useEffect, useState, useSyncExternalStore } from "react";

import { client } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { activeLocale, subscribeLocale } from "@shell/lib/locale";
import { queryClient, useDeleteChapter } from "@shell/lib/query";
import { unsavedStatus } from "@shell/lib/save";
import { shortcutKeycap } from "@shell/lib/shortcuts";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";

import { ChapterDeleteDialog, ChapterRenameDialog } from "./ChapterDialogs";
import { ExportNovelDialog } from "./InterchangeDialogs";
import { ChapterRail } from "./novel/ChapterRail";
import { DockColumn } from "./novel/DockColumn";
import { EditorColumn } from "./novel/EditorColumn";
import { useChapterRail } from "./novel/useChapterRail";
import { useNovelDraft } from "./novel/useNovelDraft";
import { useNovelWorkspace } from "./novel/useNovelWorkspace";
import { WorkspaceToolbar } from "./novel/WorkspaceToolbar";
import type { FocusStep } from "./routes";

// The step machine as data: no arithmetic on the union, and the ends are
// their own neighbours so a stray call cannot walk off the scale.
const DEEPEN: Record<FocusStep, FocusStep> = { 0: 1, 1: 2, 2: 2 };
const RELEASE: Record<FocusStep, FocusStep> = { 0: 0, 1: 0, 2: 1 };

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
    bookWords,
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
  // The band's language chip reads the shell's one locale store — the same
  // mechanism the switcher on the page it opens speaks through. The chip's
  // code is the active locale's, uppercased as the spec names it (EN/DE/FR);
  // subscribing is what makes a language change re-ink the chip.
  const locale = useSyncExternalStore(subscribeLocale, activeLocale, activeLocale);
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
  // The band's export press: the shelf's own dialog, controlled — the
  // ribbon's button is the opener, the dialog the ask (its own pattern for
  // an opener that is not its trigger).
  const [exportOpen, setExportOpen] = useState(false);
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
          {t("workspace.focusHint", { key: shortcutKeycap("workspace.stepBack") })}
        </p>
      ) : null}

      {/* The toolbar band (F26), dressed as the draft's editor ribbon
          (spec §5.1): the breadcrumb, the save chip reading the one
          autosave status, the book's live word count and the language
          chip; the workbench's own controls keep their names, pressed
          states and presses. The drafted values ride the reads the
          workspace already holds — `undefined` while a read waits, so no
          chip claims a book the page cannot see. */}
      {focus < 2 ? (
        <WorkspaceToolbar
          focus={focus}
          collapsed={collapsed}
          showRail={showRail}
          pending={pending}
          failed={failed}
          chapterCount={chapters.length}
          railFilter={railFilter}
          activeDockPath={activeDock?.path}
          bookTitle={novelQuery.data?.title}
          words={bookWords}
          status={status}
          localeChip={locale.toUpperCase()}
          onExport={novelQuery.data ? () => setExportOpen(true) : undefined}
          step={step}
          toggleRail={toggleRail}
          toggleDock={toggleDock}
          setWalkedIndex={setWalkedIndex}
          setRailFilter={setRailFilter}
        />
      ) : null}

      {/* The workbench: the rail beside the editor, so writing never scrolls
          past the chapter list. The container is one width in both states
          (F25) — 1200, the shelf's own, so the bar, the shelf and this page
          share one left edge: rail 224, column 608, dock 336. The column
          holds the card's 576 and leaves the ring its 24 px before the
          dock's seam — the centring's 8 and the column's own 16 of padding.
          The frame stays while the book
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
          <ChapterRail
            visibleChapters={visibleChapters}
            chapterCounts={chapterCounts}
            active={active}
            activeVisibleIndex={activeVisibleIndex}
            walkedIndex={walkedIndex}
            railListRef={railListRef}
            dragId={dragId}
            dropIndex={dropIndex}
            railFilter={railFilter}
            orderFailed={orderFailed}
            createFailed={createFailed}
            chapterCount={chapters.length}
            novelId={novelId}
            bookTitle={novelQuery.data?.title}
            move={move}
            moveTo={moveTo}
            setWalkedIndex={setWalkedIndex}
            setDropIndex={setDropIndex}
            select={select}
            walkRail={walkRail}
            onCreateChapter={createChapter}
          />
        ) : null}

        <EditorColumn
          railOverlay={railOverlay}
          dockOverlay={dockOverlay}
          pending={pending}
          failed={failed}
          refreshFailed={refreshFailed}
          orderFailed={orderFailed}
          showRail={showRail}
          current={current}
          chapterTotal={chapters.length}
          currentIndex={currentIndex}
          draftTitle={draft.title}
          status={status}
          offer={offer}
          bookTitle={novelQuery.data?.title}
          bookAuthor={novelQuery.data?.author ?? undefined}
          focus={focus}
          railFilter={railFilter}
          retry={retry}
          onTitleChange={changeTitle}
          schedule={schedule}
          onProposalResolve={resolveOffer}
          onRenameOpen={() => setRenameOpen(true)}
          onDeleteOpen={() => setDeleteOpen(true)}
          onMove={move}
        />

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
          <DockColumn openDock={openDock} railOverlay={railOverlay} />
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

      {/* The band's export: the shelf's own dialog for this book, one
          export surface, not two — mounted while the book's row is here,
          the only thing it can name. */}
      {novelQuery.data ? (
        <ExportNovelDialog
          novel={novelQuery.data}
          isOpen={exportOpen}
          onOpenChange={setExportOpen}
        />
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
