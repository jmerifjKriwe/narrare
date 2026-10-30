import { Link, Outlet, useBlocker, useChildMatches, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";

import { client, type Chapter } from "@shell/lib/api/client";
import { publishActiveChapter } from "@shell/lib/activeChapter";
import { docks } from "@shell/lib/generated/docks";
import { useTranslation } from "@shell/lib/i18n";
import { subscribeProposal } from "@shell/lib/proposal";
import { queryClient, useChaptersQuery, useNovelQuery } from "@shell/lib/query";
import { useAutosave, unsavedStatus } from "@shell/lib/save";

import { ChapterEditor } from "./ChapterEditor";
import type { FocusStep } from "./routes";

// The step machine as data: no arithmetic on the union, and the ends are
// their own neighbours so a stray call cannot walk off the scale.
const DEEPEN: Record<FocusStep, FocusStep> = { 0: 1, 1: 2, 2: 2 };
const RELEASE: Record<FocusStep, FocusStep> = { 0: 0, 1: 0, 2: 1 };

// One row of the generated dock registry. The workspace knows no dock by
// name — its tabs, matching and labels all come from this table, and a new
// dock (the Wissen dock) renders by appearing in it.
type DockRow = (typeof docks)[number];

/** The novel workbench: the chapter rail beside the editor, panel state in the URL. */
export function NovelPage() {
  const t = useTranslation();
  // By route id, not the route object: the page stands apart from
  // routes.tsx, and the registered router still types `id` from the string.
  const { id: novelId } = useParams({ from: "/novels/$id" });
  const { rail, focus: focusParam } = useSearch({ from: "/novels/$id" });
  // Absent means expanded: only an explicit collapsed encoding (validated to
  // false in routes.tsx) hides the rail.
  const collapsed = rail === false;
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
  const [active, setActive] = useState<string | null>(null);
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

  // The chapter to reopen on arrival is the last one written in, read from
  // the server's updated_at — compared as parsed instants, because two
  // ISO strings with different timezone offsets do not order as their
  // moments do. Strict comparison: on equal instants the first row keeps
  // the lead, and the list is in position order, so the choice stays
  // deterministic even when two chapters tie. The refill only fills an empty
  // selection — the user's own choice, once made, is never overwritten by a
  // refetch that brings the same list back.
  useEffect(() => {
    if (chaptersQuery.data === undefined) return;
    const latest = chaptersQuery.data.reduce<Chapter | null>(
      (best, chapter) =>
        best === null || Date.parse(chapter.updated_at) > Date.parse(best.updated_at)
          ? chapter
          : best,
      null,
    );
    setActive((previous) => previous ?? latest?.id ?? null);
  }, [chaptersQuery.data]);

  // The proposal bus: the dock's panels (other capabilities) offer text
  // through the shell; the workbench subscribes and feeds the editor's
  // proposal props. One pending offer, last-wins, spent on resolve — and
  // dead with this page: unmount drops the subscription, so an offer made
  // to this workspace never haunts the next visit. `null` frees the
  // editor's own continuation stream; only a live offer speaks here.
  const [offer, setOffer] = useState<string | null>(null);
  useEffect(() => subscribeProposal(setOffer), []);
  const resolveOffer = useCallback(() => setOffer(null), []);

  // The active chapter is workspace state the docks beside the editor need
  // — extraction reads the chapter the editor is showing. The shell seam
  // (not a capability import) carries it: published on every selection
  // change, null as the workspace goes, so a selection never outlives its
  // owner.
  useEffect(() => {
    publishActiveChapter(active);
    return () => {
      publishActiveChapter(null);
    };
  }, [active]);

  // The collapse is a navigation, not local state: the panel state becomes
  // part of the URL — a shareable workspace, and one the back button undoes.
  // `to: "."` keeps the navigation on whatever route is showing: collapsing
  // the rail while a dock child route is open must not throw the dock away.
  const toggleRail = useCallback(() => {
    void navigate({
      to: ".",
      search: (prev) => ({ ...prev, rail: collapsed }),
    });
  }, [navigate, collapsed]);

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
              search: (prev) => ({ ...prev }),
            },
      );
    },
    [navigate, novelId, activeDock],
  );

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
  }, [focus, step]);

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
      // the same answer. Awaiting it keeps the selection and the row it
      // names in step: the editor opens on a chapter the list already shows.
      await queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
      // The bookshelf hero names the last-touched book, and its truth is the
      // novel row's updated_at — a chapter write is the most common way that
      // changes, so the shelf's ["novels"] cache must not outlive this POST.
      // The prefix covers the row this page reads as well.
      await queryClient.invalidateQueries({ queryKey: ["novels"] });
      setActive(chapter.id);
    } catch {
      // The service is not answering at all and the proxy refuses: the same
      // refusal the rail must name as any other.
      setCreateFailed(true);
    }
  }

  const remember = useCallback(() => {
    // The cache holds the chapters now: the saved body reaches it through
    // the refetch this invalidation triggers. This callback is `onSaved` —
    // it fires only on success — so a failed save never asks for anything,
    // and no refetch can lay the server's old text over the body the
    // autosave holds for its retry.
    void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
    // Same truth as the create path above: a settled save advanced the
    // novel's updated_at, and the shelf's hero reads it through ["novels"].
    void queryClient.invalidateQueries({ queryKey: ["novels"] });
  }, [novelId]);

  const current = chapters.find((chapter) => chapter.id === active) ?? null;

  // The autosave is the page's, not the chapter's: the editor remounts on
  // every switch (its key is the chapter id), and a hook that lived inside
  // it would unmount with it — cleanup firing, a refused body dying with
  // its ref — on each switch. Here the body's lifetime spans switches: the
  // editor shows `status` beside the text and feeds `schedule` on update;
  // `flush` is the page's own handle on what has not reached the server.
  const { status, schedule, flush, discard } = useAutosave(current?.id ?? null, remember);

  // The page's one opinion about unsaved text, shared by every guard: a body
  // waiting for its debounce, one on the wire, or one that did not land.
  // `saving` counts — a request that never answers loses the text just as
  // surely as one that was refused.
  const unsaved = unsavedStatus(status);
  // The guards ask at the moment they run, not at the render that registered
  // them: a navigation starts after the keystroke, not before it.
  const unsavedNow = useRef(unsaved);
  unsavedNow.current = unsaved;

  /** Leave a chapter: save first, ask only when the save did not land. */
  async function leave(then: () => void) {
    const outcome = await flush();
    if (outcome === "failed" && !window.confirm(t("save.confirmLeave"))) return;
    then();
  }

  // Every way out of the book — the shell's top bar, the shelf link, the
  // browser's back and forward — is a router navigation, and this is the one
  // place they all pass. A destination inside the book's own subtree (the
  // dock's routes, a focus step, the rail) is no leave: the editor stays
  // mounted and the body stays here.
  // `enableBeforeUnload` is the same question for the tab close, which has no
  // navigation to intercept.
  useBlocker({
    shouldBlockFn: async ({ next: to }) => {
      const book = `/novels/${novelId}`;
      if (to.pathname === book || to.pathname.startsWith(`${book}/`)) return false;
      if (!unsavedNow.current) return false;
      const outcome = await flush();
      if (outcome !== "failed") return false;
      if (!window.confirm(t("save.confirmLeave"))) return true;
      discard();
      return false;
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

  return (
    <div
      className={openDock ? "mx-auto max-w-6xl px-4 py-10" : "mx-auto max-w-4xl px-4 py-10"}
    >
      {focus < 2 ? (
        <>
          <Link to="/" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("nav.back")}
          </Link>
          {/* The heading names the book only when the book's row is here: an
              empty h1 on the outage page would be a heading about nothing. */}
          {novelQuery.data ? (
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">
              {novelQuery.data.title}
            </h1>
          ) : null}
        </>
      ) : null}

      {/* The workbench: the rail beside the editor, so writing never scrolls
          past the chapter list. Collapsed, the rail unmounts and the editor
          takes the full width. The frame stays while the book loads or
          fails — the toolbar and the docks are independent of the book's
          row, and a dock's own outage story must stay reachable. */}
      <div className="mt-6 flex items-start gap-6">
        {/* The rail needs the chapter list. While it loads, or after the
            load failed, there is no list to be empty — the empty copy would
            mask exactly the state this page just named in the editor column. */}
        {showRail && !pending && !failed ? (
          <aside className="w-56 shrink-0" aria-label={t("chapters.heading")}>
            <h2 className="text-lg font-semibold">{t("chapters.heading")}</h2>
            <button
              type="button"
              onClick={toggleRail}
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel"
            >
              {t("workspace.collapseRail")}
            </button>
            {chapters.length === 0 ? (
              <p className="mt-2 text-sm text-muted">{t("chapters.empty")}</p>
            ) : null}
            <ul className="mt-3 flex flex-col gap-2">
              {chapters.map((chapter) => (
                <li key={chapter.id}>
                  <button
                    type="button"
                    aria-pressed={chapter.id === active}
                    onClick={() => {
                      // The chapter already open is no leave: asking there
                      // would discard a failure the user never left.
                      if (chapter.id === active) return;
                      void leave(() => setActive(chapter.id));
                    }}
                    className="w-full rounded-md border border-border bg-card px-4 py-2 text-left text-sm aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground"
                  >
                    {chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 })}
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => void leave(() => void createChapter())}
              className="mt-3 w-full rounded-md border border-border px-3 py-2 text-sm font-medium"
            >
              {t("chapters.new")}
            </button>
            {createFailed ? (
              <p role="alert" className="mt-2 text-sm text-danger">
                {t("chapters.errorCreate")}
              </p>
            ) : null}
          </aside>
        ) : null}

        <section className="min-w-0 flex-1">
          {/* The way back when the rail is gone: the toggle lives in the rail
              while it exists, so the collapsed page needs its own handle. */}
          {collapsed && focus === 0 ? (
            <button
              type="button"
              onClick={toggleRail}
              className="rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel"
            >
              {t("workspace.expandRail")}
            </button>
          ) : null}
          {/* The focus affordance, mouse's one step in and out. At depth 2 it
              is deliberately absent: the deepest step is left by keyboard,
              which is what makes the mode distraction-free. The dock tabs
              sit beside it, one per registry row: the label is the dock's
              own (its capability's catalog key), and a tab is pressed
              exactly while its route is the matched child. */}
          {focus < 2 ? (
            <button
              type="button"
              onClick={() => step(focus === 0 ? 1 : 0)}
              className="ml-3 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel"
            >
              {focus === 0 ? t("workspace.focus") : t("workspace.unfocus")}
            </button>
          ) : null}
          {focus < 2
            ? docks.map((dock) => (
                <button
                  key={dock.id}
                  type="button"
                  onClick={() => toggleDock(dock)}
                  aria-pressed={activeDock?.path === dock.path}
                  className="ml-3 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground"
                >
                  {t(dock.titleKey)}
                </button>
              ))
            : null}
          {pending ? (
            // The page has asked and is waiting — a named state, not a blank
            // or empty-looking book.
            <p className="mt-6 text-sm text-muted">{t("chapters.loading")}</p>
          ) : failed ? (
            // The book could not be loaded — refused or unreachable, with
            // nothing on screen to keep. The failure is named where the
            // retry is one press away.
            <div className="mt-6">
              <p role="alert" className="text-sm text-danger">
                {t("chapters.errorLoad")}
              </p>
              <button
                type="button"
                onClick={retry}
                className="mt-3 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel"
              >
                {t("chapters.retry")}
              </button>
            </div>
          ) : (
            <>
              {refreshFailed ? (
                // The refresh failed, but the chapters on screen are the
                // last loaded ones: a quiet note beside the work, not the
                // outage's louder clothes — the editor and the rail stay,
                // and the retry asks again.
                <div className="mt-6 flex items-baseline gap-3">
                  <p className="text-sm text-muted">{t("chapters.refreshFailed")}</p>
                  <button
                    type="button"
                    onClick={retry}
                    className="text-sm text-muted underline-offset-4 hover:underline"
                  >
                    {t("chapters.retry")}
                  </button>
                </div>
              ) : null}
              {current ? (
                <ChapterEditor
                  key={current.id}
                  chapterId={current.id}
                  body={current.body}
                  status={status}
                  schedule={schedule}
                  proposal={offer ?? undefined}
                  onProposalResolve={resolveOffer}
                />
              ) : null}
            </>
          )}
        </section>

        {/* The right dock: the open registry row's child route renders here —
            the tab's navigation decided which one, and the matched child is
            the dock's open state. The column scrolls alone so a long answer
            never scrolls the editor out of view. */}
        {openDock ? (
          <aside
            className="w-96 shrink-0 rounded-lg border border-border bg-panel p-4"
            aria-label={t(openDock.titleKey)}
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">{t(openDock.titleKey)}</h2>
              <button
                type="button"
                onClick={() => toggleDock(openDock)}
                className="rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-card"
              >
                {t("workspace.dockClose")}
              </button>
            </div>
            <div className="mt-3 max-h-[50vh] overflow-y-auto">
              <Outlet />
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}
