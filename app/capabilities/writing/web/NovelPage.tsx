import { Link, Outlet, useBlocker, useChildMatches, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { client, type Chapter } from "@shell/lib/api/client";
import { announce } from "@shell/lib/announce";
import { docks } from "@shell/lib/generated/docks";
import { useTranslation } from "@shell/lib/i18n";
import { activeLocale } from "@shell/lib/locale";
import { usePageTitle } from "@shell/lib/pageTitle";
import { subscribeProposal } from "@shell/lib/proposal";
import {
  activeChapterFallback,
  queryClient,
  useChaptersQuery,
  useDeleteChapter,
  useNovelQuery,
  useReorderChapters,
} from "@shell/lib/query";
import { useAutosave, unsavedStatus, type DocumentDraft } from "@shell/lib/save";
import { countWords, formatWordCount } from "@shell/lib/words";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { ActionMenu } from "@shell/ui/Menu";
import { Icon } from "@shell/ui/icons";
import { Notice } from "@shell/ui/Notice";
import { Row } from "@shell/ui/Row";

import { ChapterEditor } from "./ChapterEditor";
import { ChapterDeleteDialog, ChapterRenameDialog } from "./ChapterDialogs";
import type { FocusStep } from "./routes";

// The step machine as data: no arithmetic on the union, and the ends are
// their own neighbours so a stray call cannot walk off the scale.
const DEEPEN: Record<FocusStep, FocusStep> = { 0: 1, 1: 2, 2: 2 };
const RELEASE: Record<FocusStep, FocusStep> = { 0: 0, 1: 0, 2: 1 };

// The drag's drop marker: a 2 px primary edge at the slot's top — the row
// a drop would land at. Its look is the spec's "left to the builder"; it
// lives on the slot so the Row's own classes stay untouched.
const DROP_HINT = "shadow-[inset_0_2px_0_var(--primary)]";

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

/** The novel workbench: the chapter rail beside the editor, panel state in the URL. */
export function NovelPage() {
  const t = useTranslation();
  // By route id, not the route object: the page stands apart from
  // routes.tsx, and the registered router still types `id` from the string.
  const { id: novelId } = useParams({ from: "/novels/$id" });
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
  // The rail's own create failure: a chapter the user asked for that never
  // arrived must say so beside the button, not vanish into a silent click.
  const [createFailed, setCreateFailed] = useState(false);
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

  // The leave guard's state, ahead of the keyboard contract: while an ask
  // stands, F9/Esc are the dialog's keys, not the workbench's — a second
  // ask would overwrite the first answer's resolver and strand the
  // navigation that is still waiting on it.
  const [guardOpen, setGuardOpen] = useState(false);
  const guardAnswer = useRef<((leave: boolean) => void) | null>(null);
  const guardBusy = useRef(false);
  const answerGuard = useCallback((leave: boolean) => {
    setGuardOpen(false);
    guardBusy.current = false;
    const answer = guardAnswer.current;
    guardAnswer.current = null;
    answer?.(leave);
  }, []);

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

  /** Create and select an untitled chapter, or show a retryable failure in the rail. */
  async function createChapter() {
    // An explicit empty title: the placeholder is a display concern, and
    // storing a title would freeze one locale's wording into the database.
    // The server treats an empty title exactly like an omitted one.
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

  const remember = useCallback(
    (chapterId: string, draft: DocumentDraft) => {
      // The saved draft reaches the cache before the ask: the patch makes
      // the settled document — title and body both — the key's own answer,
      // so the words, the row's name and the freshness their updated_at
      // stands for cannot be remounted over by a refetch that never
      // answers (or answers refused) on a later switch. The refetch stays
      // the truth; the patch only holds the page's ground until it lands.
      queryClient.setQueryData<Array<Chapter>>(["chapters", novelId], (rows) =>
        rows?.map((row) =>
          row.id === chapterId
            ? { ...row, ...draft, updated_at: new Date().toISOString() }
            : row,
        ),
      );
      // This callback is `onSaved` — it fires only on success — so a failed
      // save never asks for anything.
      void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
      // Same truth as the create path above: a settled save advanced the
      // novel's updated_at, and the shelf's hero reads it through ["novels"].
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
    },
    [novelId],
  );

  const current = chapters.find((chapter) => chapter.id === active) ?? null;
  // The open chapter's slot, for the runhead menu's move items: the ends
  // of the rail are their own no-ops, and an offered deed that cannot run
  // says so by its disabled state, not by a silent click.
  const currentIndex = chapters.findIndex((chapter) => chapter.id === active);

  // The autosave is the page's, not the chapter's: the editor remounts on
  // every switch (its key is the chapter id), and a hook that lived inside
  // it would unmount with it — cleanup firing, a refused body dying with
  // its ref — on each switch. Here the body's lifetime spans switches: the
  // editor shows `status` beside the text and feeds `schedule` on update;
  // `flush` is the page's own handle on what has not reached the server.
  const { status, schedule, flush, discard } = useAutosave(current?.id ?? null, remember);

  // The document the writer holds: title beside body, one draft — the
  // autosave's unit of work. It belongs to the open chapter, and the
  // selection's change is its reset, done in render (the state-adjust
  // pattern) so the new chapter's first paint already carries its own
  // name: an effect would paint the old book's title over the new chapter
  // for a frame. Every schedule — the editor's body, the runhead's title —
  // passes through one wrapper, so the state and the pending save can
  // never disagree: `remember` patches the row from the whole draft, and a
  // stale half would patch a regression.
  const [held, setHeld] = useState<{ id: string | null; draft: DocumentDraft }>({
    id: null,
    draft: { title: "", body: "" },
  });
  const currentId = current?.id ?? null;
  if (held.id !== currentId) {
    setHeld({
      id: currentId,
      draft: { title: current?.title ?? "", body: current?.body ?? "" },
    });
  }
  const draft = held.draft;
  const draftRef = useRef(draft);
  draftRef.current = draft;
  const scheduleDraft = useCallback(
    (next: DocumentDraft, changed: keyof DocumentDraft) => {
      setHeld((previous) => ({ ...previous, draft: next }));
      schedule(next, changed);
    },
    [schedule],
  );
  /** The runhead's title keystrokes: the draft's body is whatever the page
   *  last held, so the rename rides beside — never over — the text. */
  const changeTitle = useCallback(
    (value: string) => scheduleDraft({ ...draftRef.current, title: value }, "title"),
    [scheduleDraft],
  );

  // The page's one opinion about unsaved text, shared by every guard: a body
  // waiting for its debounce, one on the wire, or one that did not land.
  // `saving` counts — a request that never answers loses the text just as
  // surely as one that was refused.
  const unsaved = unsavedStatus(status);
  // The guards ask at the moment they run, not at the render that registered
  // them: a navigation starts after the keystroke, not before it.
  const unsavedNow = useRef(unsaved);
  unsavedNow.current = unsaved;

  // Every way out of the chapter — the rail, the docks and their panel
  // state, history's back and forward, the shell's links, and whatever
  // jump lands here later — is a router navigation, and this is the one
  // place they all pass. While text is unsaved the gate flushes first;
  // only a flush that did not land asks, and a dismissed ask keeps the
  // work. The destination does not matter, because the body does: anything
  // the router would move away from the editor is worth the same question.
  // An accepted ask does not drop the body here, either: a panel toggle
  // would wipe a refused write while the editor stayed mounted — the
  // notice retracting, the next leave asking nothing — so the body is
  // cleared only where the chapter really changes (the effect below) or
  // the page really goes (the autosave's own teardown).
  // `enableBeforeUnload` is the same question for the tab close, which has
  // no navigation to intercept.
  //
  // The ask itself is the shell's dialog (F21), not window.confirm: the
  // page's own clothes, focus contained while it stands, and the two
  // answers as the two buttons the question names. The blocker awaits the
  // answer as a promise; Escape and an outside click are RAC dismissals,
  // which land in `onOpenChange` as a "stay". `guardBusy` stands only
  // once the ask stands — it is set after a flush has failed, not while
  // it runs — so two navigations inside the flush window are last-wins
  // by design: the second ask replaces the first.
  useBlocker({
    shouldBlockFn: async () => {
      if (!unsavedNow.current) return false;
      if (guardBusy.current) return true;
      const outcome = await flush();
      if (outcome !== "failed") return false;
      guardBusy.current = true;
      const leave = await new Promise<boolean>((resolve) => {
        guardAnswer.current = resolve;
        setGuardOpen(true);
      });
      return !leave;
    },
    enableBeforeUnload: () => unsavedNow.current,
  });

  // Reset the save story only after the chapter selection actually changes.
  // Creation can fail after a confirmed leave; until it succeeds, the old
  // chapter's failed body must still be protected by every leave guard.
  useEffect(() => {
    discard();
  }, [current?.id, discard]);

  // Panels yield to focus before their own URL state: at depth 1 the rail is
  // hidden whatever ?rail says, and its toggles hide with it — they would be
  // no-ops while focus suppresses the panel. The page's own header goes at
  // depth 2: chrome-free means only the writing surface remains. The dock
  // panel yields the same way; its tab survives one step longer, because at
  // depth 1 closing the dock is still a real state change, and the tab is
  // the dock's way back.
  const showRail = focus === 0 && !collapsed;
  const openDock = activeDock !== undefined && focus === 0 ? activeDock : null;

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

  // The rail's roving walk (F20): the current row is the one tab stop, and
  // Up/Down move the focus along the rows. The walk moves focus only — the
  // chapter changes when a row is activated, never when it is walked past —
  // but the tab stop follows the focus while the walk lasts (APG): walk
  // away and one Tab returns to the row the user was on, not the row they
  // had selected. Activating a row hands the tab stop back to the selection.
  const railListRef = useRef<HTMLUListElement | null>(null);
  const [walkedIndex, setWalkedIndex] = useState<number | null>(null);
  const walkRail = useCallback((event: ReactKeyboardEvent, index: number) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const rows = railListRef.current?.querySelectorAll<HTMLButtonElement>("button");
    if (!rows) return;
    const next = event.key === "ArrowDown" ? index + 1 : index - 1;
    if (next < 0 || next >= rows.length) return;
    setWalkedIndex(next);
    rows[next]?.focus();
  }, []);

  // The rail's reorder (WP6): Alt+↑/↓ on the focused row and a desktop
  // drag both end in one PUT of the whole rail. The arrangement is
  // written into the cache optimistically — the rail is the new order at
  // once, each row keeping its own updated_at (an arrangement is not a
  // write) — and any failure restores the list the ask replaced beside a
  // named notice. A 409 alone also refetches the key: the book's whole
  // changed in another tab, and the server's arrangement is the truth the
  // cache lacks. The shelf is asked for only on success, through the
  // mutation's own `onSuccess`.
  const reorder = useReorderChapters(novelId);
  const [orderFailed, setOrderFailed] = useState(false);
  // The tail of the reorder queue, the autosave's own pattern: never
  // rejects, so one failed ask cannot eat the moves queued behind it.
  // Serialization is the promise "survives a reload" keeps under key
  // repeat — two arrangements in flight at once can commit inverted, the
  // server holding the earlier permutation while the rail shows the last.
  const writes = useRef<Promise<unknown>>(Promise.resolve());
  // The rail's filter is Task 12's; until it exists no filter can be
  // active. The seam is here already — `null` is "no filter", the one
  // state in which a reorder is unambiguous — so Task 12 replaces the
  // state's source, not the guard.
  const [railFilter] = useState<string | null>(null);

  /** Move one chapter one step: the keyboard's Alt+↑/↓ path, and the
   *  address Task 10's menu items call. The ends are no-ops — nothing
   *  moves, nothing is asked. */
  async function move(chapterId: string, delta: -1 | 1): Promise<void> {
    if (railFilter !== null) return;
    const rows = queryClient.getQueryData<Array<Chapter>>(["chapters", novelId]);
    if (!rows) return;
    const from = rows.findIndex((chapter) => chapter.id === chapterId);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= rows.length) return;
    await moveTo(chapterId, to);
  }

  /** Move one chapter to an index: the drag path's landing, and move's
   *  engine. Both reads are the cache's, not the render's list — two
   *  moves before a re-render must not compute the second from the
   *  first's before — and the first read doubles as the snapshot a
   *  failure restores. */
  async function moveTo(chapterId: string, index: number): Promise<void> {
    if (railFilter !== null) return;
    const previous = queryClient.getQueryData<Array<Chapter>>(["chapters", novelId]);
    if (!previous) return;
    const from = previous.findIndex((chapter) => chapter.id === chapterId);
    if (from < 0 || from === index || index < 0 || index >= previous.length) return;
    const moved = previous[from];
    const without = previous.filter((chapter) => chapter.id !== chapterId);
    const next = [...without.slice(0, index), moved, ...without.slice(index)].map(
      (chapter, position) => ({ ...chapter, position }),
    );
    // A plain list tells AT nothing about a reordering: every move is
    // announced with the row's name — the one it wore as the move began,
    // the name the keystroke or the grab was aimed at — and the position
    // it holds now, out of the book's total.
    announce(
      t("chapters.moved", {
        title: moved.title || t("chapters.defaultTitle", { n: moved.position + 1 }),
        n: index + 1,
        m: next.length,
      }),
    );
    // The optimistic write: the rail and the cache agree at once, the
    // numbering rewritten to the arrangement the rows now stand in.
    // `setQueryData` runs the value through structural sharing and
    // answers with the object the cache actually stored — never the
    // `next` we passed — so the identity guard below compares against
    // the RETURN: the one reference a later read can still find there.
    const written = queryClient.setQueryData<Array<Chapter>>(
      ["chapters", novelId],
      next,
    );
    setOrderFailed(false);
    // The ask waits its turn: one arrangement on the wire at a time,
    // chained on the queue's tail. This move's promise (`ask`) can
    // reject into its own handler; the tail cannot, or a later keystroke
    // would queue behind a failure and never fly.
    const ask = writes.current.then(() =>
      reorder.mutateAsync(next.map((chapter) => chapter.id)),
    );
    writes.current = ask.catch(() => undefined);
    try {
      await ask;
    } catch (failure) {
      // Restore only what is still this move's to restore: the cache
      // must hold the very object this move's write stored, or a later
      // move's optimistic order — newer than this snapshot — would be
      // clobbered by an earlier failure. The notice still names the
      // refusal either way. A 409 asks the key to refetch, the server's
      // order arriving through the same door every list does; a
      // transport failure asks for nothing — the service is not
      // answering, and a second ask would only name a refresh failure
      // beside work that stays.
      if (queryClient.getQueryData<Array<Chapter>>(["chapters", novelId]) === written) {
        queryClient.setQueryData<Array<Chapter>>(["chapters", novelId], previous);
      }
      setOrderFailed(true);
      if ((failure as { status?: number }).status === 409) {
        void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
      }
    }
  }

  // The desktop drag's state. The dragged id rides component state, not
  // `dataTransfer`: the DOM test drives the events alone, and no drop
  // reads data some other surface would have to write. `dropIndex` is
  // the marker's truth — which slot the drop would land at — read by the
  // render, not by the drop itself (the slot's own handler knows its
  // index; the state would be one event behind it).
  const dragId = useRef<string | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

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
        schedule(held.draft, "title");
        schedule(held.draft, "body");
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

  /** The rename dialog's answer: the runhead's input (and the page's held
   *  draft) take the server's title at once, while the autosave's pending
   *  slot keeps whatever fields it was holding — the title was never
   *  dirtied by the dialog, so the pending flush carries the body only
   *  and the rename survives it (Task 9's contract). */
  const renamed = useCallback(
    (title: string) => {
      setHeld((previous) =>
        previous.id === current?.id
          ? { ...previous, draft: { ...previous.draft, title } }
          : previous,
      );
    },
    [current?.id],
  );

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
        <div className="mt-6 flex items-center gap-2">
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
        </div>
      ) : null}

      {/* The workbench: the rail beside the editor, so writing never scrolls
          past the chapter list. The container is one width in both states
          (F25) — 1200, the shelf's own, so the bar, the shelf and this page
          share one left edge: rail 224, dock 384, and the prose column that
          remains carries the 544 measure with air on both sides (592 with
          the dock open, 24 px each side). The frame stays while the book
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
               inside the column (lg:pr-6), so rail + prose + dock sum to
               the container with no gap to account for. The list bounds
               its height and scrolls inside itself (Review Focus 2); below
               the breakpoint the whole drawer scrolls instead. The drawer
               paints one z-step above the dock's: opening it over a live
               dock covers the dock without unmounting it, so the dock's
               own draft survives behind it. */
            className="flex w-56 shrink-0 flex-col lg:max-h-[calc(100dvh-16rem)] lg:pr-6 max-lg:absolute max-lg:top-0 max-lg:bottom-0 max-lg:left-0 max-lg:z-30 max-lg:w-72 max-lg:max-w-full max-lg:overflow-y-auto max-lg:rounded-[var(--radius-lg)] max-lg:border max-lg:border-rule max-lg:bg-panel max-lg:p-4 max-lg:shadow-overlay"
            aria-label={t("chapters.heading")}
          >
            <h2 className="text-emph font-semibold tracking-tight">{t("chapters.heading")}</h2>
            {chapters.length === 0 ? (
              <p className="mt-2 text-body text-muted">{t("chapters.empty")}</p>
            ) : null}
            {/* The list scrolls itself in the desktop columns only (its
                bounded height is a column fact); below 1024 the drawer
                scrolls whole, so the list must neither clip nor shrink
                there. */}
            <ul
              ref={railListRef}
              className="mt-3 flex flex-col lg:min-h-0 lg:flex-1 lg:overflow-y-auto"
            >
              {chapters.map((chapter, index) => {
                const isCurrent = chapter.id === active;
                const title = chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 });
                // The count is spoken as the sentence the footer prints
                // ("… 2.107 Wörter") and shown as its number alone — the
                // localized grouping, so the row and the footer read alike.
                const words = chapterCounts.get(chapter.id) ?? 0;
                const isTabStop =
                  walkedIndex !== null
                    ? walkedIndex === index
                    : isCurrent || (active === null && index === 0);
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
                         drop index (Task 12's rule, its seam already
                         here). */
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
                        {formatWordCount(words, activeLocale())}
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
          className="flex min-w-0 flex-1 flex-col items-center"
          inert={railOverlay || dockOverlay || undefined}
        >
          {/* The editor's tone step (R49): a band painted around the
              measured column — the 544 the prose reads at is never the
              chrome's victim. The prose column keeps 592 with the dock open
              (rail 224 + prose 592 + dock 384 = 1200), so the measure
              centres with 24 px of air on each side instead of touching the
              band's edge; the band takes its ground, its rules and its air
              vertically, and the measure lives on the inner column
              untouched. */}
          <div className="w-full border-y border-rule bg-card py-6">
            <div className="mx-auto w-full max-w-[544px]">
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
                {current ? (
                  <ChapterEditor
                    key={current.id}
                    chapterId={current.id}
                    body={current.body}
                    title={draft.title}
                    onTitleChange={changeTitle}
                    status={status}
                    schedule={scheduleDraft}
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
                            label: t("chapters.moveUp"),
                            // The ends are their own no-ops, offered but
                            // disabled: the shortcut the hint names is the
                            // rail's own Alt+↑ (D6), discoverable exactly
                            // where the action lives.
                            shortcut: "Alt+↑",
                            disabled: currentIndex <= 0,
                            onSelect: () => void move(current.id, -1),
                          },
                          {
                            id: "moveDown",
                            label: t("chapters.moveDown"),
                            shortcut: "Alt+↓",
                            disabled: currentIndex >= chapters.length - 1,
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
               384 the dock takes are the arithmetic's own; its gutter to
               the prose lives inside the column. The column is a flex
               stack so the title holds its place while the body under it
               takes the remaining height and scrolls alone. The rail's
               drawer sits a z-step above this one: a rail opened over a
               live dock covers it without unmounting it, so the dock's
               in-progress ask survives behind the drawer — and while it is
               covered the dock goes `inert`, so the keyboard cannot land on
               controls the drawer hides. */
            className="flex w-96 shrink-0 flex-col rounded-[var(--radius-lg)] border border-rule bg-panel p-4 max-lg:absolute max-lg:top-0 max-lg:bottom-0 max-lg:right-0 max-lg:z-20 max-lg:max-w-full max-lg:shadow-overlay lg:max-h-[calc(100dvh-16rem)] lg:pl-6"
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
            onRenamed={renamed}
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
