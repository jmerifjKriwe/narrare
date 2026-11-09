import { useChildMatches, useNavigate, useSearch } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";

import { docks } from "@shell/lib/generated/docks";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { subscribeProposal } from "@shell/lib/proposal";
import {
  activeChapterFallback,
  noteNovelDeletedElsewhere,
  useChaptersQuery,
  useNovelQuery,
} from "@shell/lib/query";
import { countWords } from "@shell/lib/words";

import type { FocusStep } from "../routes";

// One row of the generated dock registry. The workspace knows no dock by
// name — its tabs, matching and labels all come from this table, and a new
// dock (the Wissen dock) renders by appearing in it.
type DockRow = (typeof docks)[number];

/**
 * The workbench breakpoint as JS. Below it the rail and the dock are
 * overlays — the same width the `max-lg:` classes answer — and an overlay
 * owes the page it covers a scrim and its focus; the hook exists so `inert`
 * can answer the same media query the classes do. jsdom has no matchMedia:
 * it gets the desktop answer, which keeps the unit tests in the columns.
 */
function useBelowWorkbenchBreakpoint(): boolean {
  const query = "(max-width: 1023.98px)";
  const [narrow, setNarrow] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia(query).matches
      : false,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const onChange = () => setNarrow(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  return narrow;
}

/**
 * The novel workbench's data, selection and panel state: the route reads,
 * queries, the selection latch, the proposal, the focus/rail/dock URL state
 * and the hints around them. The JSX stays in `NovelPage.tsx`.
 */
export function useNovelWorkspace(novelId: string) {
  const t = useTranslation();
  const { rail, focus: focusParam, chapter: chapterParam } = useSearch({ from: "/novels/$id" });
  // Below the workbench breakpoint the rail is a drawer over the text, so
  // there "absent" has to mean closed: opening it needs the explicit
  // `?rail=true` the toggle writes. On the desktop columns absent still
  // means expanded, and only a `?rail=false` closes the column.
  const narrow = useBelowWorkbenchBreakpoint();
  const collapsed = rail === false || (rail === undefined && narrow);
  // Absent means the workbench: the URL names a depth only once it deepens.
  const focus: FocusStep = focusParam ?? 0;
  const navigate = useNavigate();
  // The workspace's reads go through Query, the one server-state path: the
  // novel's row under `["novels", id]`, its chapters under
  // `["chapters", id]`. Both queryFns throw on a non-ok answer, so the cache
  // holds either the answer or the failure — a 404 is never an empty book.
  const novelQuery = useNovelQuery(novelId);
  const chaptersQuery = useChaptersQuery(novelId);
  const chapters = chaptersQuery.data ?? [];
  // One split per body per list, not per render: the rail's counts are
  // derived where the list arrives, and a keystroke re-renders for free.
  const chapterCounts = useMemo(
    () => new Map(chapters.map((chapter) => [chapter.id, countWords(chapter.body)])),
    [chapters],
  );
  // The page's name (§8.7): the book's title once its row is here — a
  // catalog fallback while it waits, never an empty string.
  usePageTitle(novelQuery.data?.title ?? t("chapters.loading"));
  // The four states of the contract, derived per read, none stored: a read's
  // error is judged against its own cache. An error with nothing from that
  // read on screen is the named outage — the retry asks again, and the page
  // has nothing to lose; an error that still holds its previous answer is a
  // true refresh failure — the quiet note, and the work stays. The page never
  // claims the book could not be loaded while its text is on screen. The
  // chapters read is the workbench's spine (it decides whether there is
  // something to show); the novel row rides along (the heading's title).
  const novelLoaded = novelQuery.data !== undefined;
  const chaptersLoaded = chaptersQuery.data !== undefined;
  // The book deleted elsewhere (Task 13): a 404 from the novel's row is
  // not an outage — the service answered, and the answer is that the book
  // is gone. The degrade is a navigation to the shelf with the note that
  // names what happened, and it outranks both failure voices below: an
  // outage page would claim the book could not be loaded, when the truth
  // is that there is no book to load. It fires whatever the screen holds —
  // a first load that never arrived, or a refresh that found the row gone
  // under open work; the leave guard still asks about unsaved words, and
  // only the navigation that survives it lands here.
  useEffect(() => {
    if (!novelQuery.isError) return;
    if ((novelQuery.error as { status?: number }).status !== 404) return;
    noteNovelDeletedElsewhere();
    void navigate({ to: "/" });
  }, [novelQuery.isError, novelQuery.error, navigate]);
  const pending = novelQuery.isPending || chaptersQuery.isPending;
  const failed =
    (novelQuery.isError && !novelLoaded) || (chaptersQuery.isError && !chaptersLoaded);
  const refreshFailed =
    !failed &&
    ((novelQuery.isError && novelLoaded) || (chaptersQuery.isError && chaptersLoaded));

  // One retry asks both reads again: the workspace shows a book only when
  // both have answered, so the recovery is whole or it is not recovery.
  const retry = useCallback(() => {
    void novelQuery.refetch();
    void chaptersQuery.refetch();
  }, [novelQuery, chaptersQuery]);

  // The selection's address is the URL: a `chapter` param that names one of
  // the book's own rows is the open chapter, full stop. Without it — or with
  // one the book does not have — the page falls back to the chapter last
  // written in, and that fallback is latched, not re-derived: the first list
  // that yields a chapter fills it, and a refetch may never move the
  // selection, because only a gated navigation may. (A create's refetch
  // brings a newer updated_at; a re-derived fallback would flip the editor
  // to the new row outside the gate and drop the unsaved body with it. An
  // empty list is no answer of this kind: the latch waits, and the first
  // chapter's refetch fills it.) The one thing that does invalidate the
  // latch is its own row dying — a delete is the gated navigation that
  // opened the neighbour, and the latched id must not outlive its row, or
  // the bare address would resolve to a chapter that renders no editor.
  // A live row, whatever the refetch brought, keeps the latch where it
  // is. The latch is the
  // book's, not the page's: a palette jump to another novel keeps this route
  // mounted and changes only the param, and the old book's row must not
  // survive as the new book's answer — the latch resets, and the new book's
  // own last-touched chapter fills it once its list lands. Nothing about the
  // fallback is written back: an arrival without a param leaves the address
  // bare, so a reload still proves the server's choice.
  const [fallback, setFallback] = useState<{
    novel: string;
    chapter: string | null;
  } | null>(null);
  useEffect(() => {
    const rows = chaptersQuery.data;
    if (rows === undefined) return;
    setFallback((previous) =>
      previous?.novel === novelId &&
      previous.chapter !== null &&
      rows.some((chapter) => chapter.id === previous.chapter)
        ? previous
        : { novel: novelId, chapter: activeChapterFallback(rows) },
    );
  }, [chaptersQuery.data, novelId]);
  const active =
    chapterParam !== undefined && chapters.some((chapter) => chapter.id === chapterParam)
      ? chapterParam
      : fallback?.novel === novelId
        ? fallback.chapter
        : null;

  // The selection writes itself into the address — a push, so the back
  // button walks the chapters. The navigation is the whole switch: the
  // flush gate below stands in front of it, and the param's landing is
  // what moves the editor.
  const select = useCallback(
    (chapterId: string) => {
      void navigate({
        to: ".",
        search: (prev) => ({ ...prev, chapter: chapterId }),
      });
    },
    [navigate],
  );

  // A param naming a chapter the book does not have is a dead link: the
  // selection fell back above, and the dead value leaves the address — a
  // replace, so the cleanup is not a history step the back button owns.
  // Waiting for the rows before judging keeps a just-created chapter's
  // address alive: the create selects only once the list that holds the
  // row has landed, so this cleanup can never eat it.
  useEffect(() => {
    const rows = chaptersQuery.data;
    if (chapterParam === undefined || rows === undefined) return;
    if (rows.some((chapter) => chapter.id === chapterParam)) return;
    void navigate({
      to: ".",
      search: (prev) => ({ ...prev, chapter: undefined }),
      replace: true,
    });
  }, [chapterParam, chaptersQuery.data, navigate]);

  // The proposal bus: the dock's panels (other capabilities) offer text
  // through the shell; the workbench subscribes and feeds the editor's
  // proposal props. One pending offer, last-wins, spent on resolve — and
  // dead with this page: unmount drops the subscription, so an offer made
  // to this workspace never haunts the next visit. `null` frees the
  // editor's own continuation stream; only a live offer speaks here.
  const [offer, setOffer] = useState<string | null>(null);
  useEffect(() => subscribeProposal(setOffer), []);
  const resolveOffer = useCallback(() => setOffer(null), []);

  // The collapse is a navigation, not local state: the panel state becomes
  // part of the URL — a shareable workspace, and one the back button undoes.
  // `to: "."` keeps the navigation on whatever route is showing: collapsing
  // the rail while a dock child route is open must not throw the dock away
  // (a dock holds the ask in progress, so the drawer above it may cover the
  // dock, never unmount it).

  // Focus depth is URL state too, so it shares rail's properties: linkable,
  // back-button-true. The updater takes the function form on purpose — it
  // receives the current search and spreads it, so deepening or releasing
  // focus preserves ?rail instead of clobbering it. The same `to: "."` keeps
  // a dock child route mounted while the depth changes around it.
  const step = useCallback(
    (next: FocusStep) => {
      if (next === focus) return; // the ends are no-ops, not new history entries
      void navigate({
        to: ".",
        search: (prev) => ({ ...prev, focus: next }),
      });
    },
    [focus, navigate],
  );

  // A dock child route is showing when one of the registry's rows matches:
  // the matched child — not a local flag — is the dock's open state, so the
  // URL is the whole truth and the back button closes it. The tab for a row
  // is pressed exactly while that row's own route is the match, so switching
  // docks is a navigation too. The panel itself renders through the Outlet
  // in the dock column below.
  const childMatches = useChildMatches();
  const activeDock = docks.find((dock) =>
    childMatches.some((match) => match.routeId === dock.path),
  );

  // Opening and closing are navigations to and from the dock child route,
  // with the search written in the function form so ?rail and ?focus ride
  // along. There is no dock param to scrub: the open dock's URL truth is
  // the child route itself, and a closed dock leaves a clean URL.
  const toggleDock = useCallback(
    (dock: DockRow) => {
      void navigate(
        activeDock?.path === dock.path
          ? {
              to: "/novels/$id",
              params: { id: novelId },
              search: (prev) => ({ ...prev }),
            }
          : {
              to: dock.path,
              params: { id: novelId },
              // A dock opened over an open rail drawer closes it: the dock's
              // ask is the thing worth keeping, and the rail holds nothing
              // that can be lost — its own open, by contrast, covers the
              // dock without unmounting it.
              search: (prev) => ({
                ...prev,
                ...(narrow && !collapsed ? { rail: false } : {}),
              }),
            },
      );
    },
    [navigate, novelId, activeDock, narrow, collapsed],
  );

  // The rail's collapse (above, explained): at narrow the rail drawer paints
  // above the dock's (z-30 over z-20), so opening it never needs to close the
  // dock — the dock stays mounted with its in-progress question and answer,
  // and closing the rail brings it back.
  const toggleRail = useCallback(() => {
    void navigate({
      to: ".",
      search: (prev) => ({ ...prev, rail: collapsed }),
    });
  }, [navigate, collapsed]);

  const current = chapters.find((chapter) => chapter.id === active) ?? null;
  // The open chapter's slot, for the runhead menu's move items: the ends
  // of the rail are their own no-ops, and an offered deed that cannot run
  // says so by its disabled state, not by a silent click.
  const currentIndex = chapters.findIndex((chapter) => chapter.id === active);

  // Panels yield to focus before their own URL state: at depth 1 the rail is
  // hidden whatever ?rail says, and its toggles hide with it — they would be
  // no-ops while focus suppresses the panel. The page's own header goes at
  // depth 2: chrome-free means only the writing surface remains. The dock
  // panel yields the same way; its tab survives one step longer, because at
  // depth 1 closing the dock is still a real state change, and the tab is
  // the dock's way back.
  const showRail = focus === 0 && !collapsed;
  const openDock = activeDock !== undefined && focus === 0 ? activeDock : null;

  // The shell cannot be imported here (capabilities never reach across), so
  // the deepest step is published as a body attribute the shell subscribes
  // to. Cleanup on unmount: leaving the workbench restores chrome everywhere.
  useEffect(() => {
    if (focus !== 2) return;
    document.body.dataset.focus = "2";
    return () => {
      delete document.body.dataset.focus;
    };
  }, [focus]);

  // The depth-2 hint (F23): one line that offers Esc back, shown once at the
  // deepest step and retracted after a few seconds — it is a message, not
  // chrome. The retraction is a clean unmount, not an opacity fade: a hint
  // caught mid-fade is a contrast the a11y floor could sample and fail, and
  // a message that is simply gone cannot break any state it is read in.
  const [hintShown, setHintShown] = useState(false);
  useEffect(() => {
    if (focus !== 2) {
      setHintShown(false);
      return;
    }
    setHintShown(true);
    const timer = window.setTimeout(() => setHintShown(false), 4200);
    return () => window.clearTimeout(timer);
  }, [focus]);

  return {
    novelQuery,
    chaptersQuery,
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
  };
}
