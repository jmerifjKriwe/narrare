import { Link, Outlet, useChildMatches, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";

import { client, type Chapter, type Novel } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";

import { ChapterEditor } from "./ChapterEditor";
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
  const { rail, focus: focusParam } = useSearch({ from: "/novels/$id" });
  // Absent means expanded: only an explicit collapsed encoding (validated to
  // false in routes.tsx) hides the rail.
  const collapsed = rail === false;
  // Absent means the workbench: the URL names a depth only once it deepens.
  const focus: FocusStep = focusParam ?? 0;
  const navigate = useNavigate();
  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [active, setActive] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [novelResult, chaptersResult] = await Promise.all([
      client.GET("/api/writing/novels/{novel_id}", {
        params: { path: { novel_id: novelId } },
      }),
      client.GET("/api/writing/novels/{novel_id}/chapters", {
        params: { path: { novel_id: novelId } },
      }),
    ]);
    setNovel(novelResult.data ?? null);
    const loadedChapters = chaptersResult.data ?? [];
    setChapters(loadedChapters);
    // The chapter to reopen on arrival is the last one written in, read from
    // the server's updated_at. Strict comparison: on equal timestamps the
    // first row keeps the lead, and the list is in position order, so the
    // choice stays deterministic even when two chapters tie.
    const latest = loadedChapters.reduce<Chapter | null>(
      (best, chapter) =>
        best === null || chapter.updated_at > best.updated_at ? chapter : best,
      null,
    );
    setActive((previous) => previous ?? latest?.id ?? null);
  }, [novelId]);

  useEffect(() => {
    void load();
  }, [load]);

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

  // A dock child route is showing (chat today, more later): the matched
  // child — not a local flag — is the dock's open state, so the URL is the
  // whole truth and the back button closes it. The panel itself renders
  // through the Outlet in the dock column below.
  const dockMatched = useChildMatches().length > 0;

  // Opening and closing are navigations to and from the dock child route,
  // with the search written in the function form so ?rail and ?focus ride
  // along. The dock param records which panel is open, beside rail and
  // focus in the URL.
  const toggleDock = useCallback(() => {
    void navigate(
      dockMatched
        ? {
            to: "/novels/$id",
            params: { id: novelId },
            search: (prev) => ({ ...prev, dock: "none" as const }),
          }
        : {
            to: "/novels/$id/chat",
            params: { id: novelId },
            search: (prev) => ({ ...prev, dock: "chat" as const }),
          },
    );
  }, [navigate, novelId, dockMatched]);

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

  async function createChapter() {
    // An explicit empty title: the placeholder is a display concern, and
    // storing a title would freeze one locale's wording into the database.
    // The server treats an empty title exactly like an omitted one.
    const { data: chapter } = await client.POST(
      "/api/writing/novels/{novel_id}/chapters",
      { params: { path: { novel_id: novelId } }, body: { title: "" } },
    );
    if (!chapter) return;
    // The bookshelf hero names the last-touched book, and its truth is the
    // novel row's updated_at — a chapter write is the most common way that
    // changes, so the shelf's ["novels"] cache must not outlive this POST.
    void queryClient.invalidateQueries({ queryKey: ["novels"] });
    setChapters((previous) => [...previous, chapter]);
    setActive(chapter.id);
  }

  const remember = useCallback((chapterId: string, body: string) => {
    setChapters((previous) =>
      previous.map((chapter) =>
        chapter.id === chapterId ? { ...chapter, body } : chapter,
      ),
    );
    // Same truth as the create path above: a settled save advanced the
    // novel's updated_at, and the hero reads it through ["novels"].
    void queryClient.invalidateQueries({ queryKey: ["novels"] });
  }, []);

  const current = chapters.find((chapter) => chapter.id === active) ?? null;

  // Panels yield to focus before their own URL state: at depth 1 the rail is
  // hidden whatever ?rail says, and its toggles hide with it — they would be
  // no-ops while focus suppresses the panel. The page's own header goes at
  // depth 2: chrome-free means only the writing surface remains. The dock
  // panel yields the same way; its tab survives one step longer, because at
  // depth 1 closing the dock is still a real state change, and the tab is
  // the dock's way back.
  const showRail = focus === 0 && !collapsed;
  const showDockPanel = dockMatched && focus === 0;

  return (
    <div
      className={
        showDockPanel ? "mx-auto max-w-6xl px-4 py-10" : "mx-auto max-w-4xl px-4 py-10"
      }
    >
      {focus < 2 ? (
        <>
          <Link to="/" className="text-sm text-muted underline-offset-4 hover:underline">
            {t("nav.back")}
          </Link>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{novel?.title}</h1>
        </>
      ) : null}

      {/* The workbench: the rail beside the editor, so writing never scrolls
          past the chapter list. Collapsed, the rail unmounts and the editor
          takes the full width. */}
      <div className="mt-6 flex items-start gap-6">
        {showRail ? (
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
                    onClick={() => setActive(chapter.id)}
                    className="w-full rounded-md border border-border bg-card px-4 py-2 text-left text-sm aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground"
                  >
                    {chapter.title || t("chapters.defaultTitle", { n: chapter.position + 1 })}
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={createChapter}
              className="mt-3 w-full rounded-md border border-border px-3 py-2 text-sm font-medium"
            >
              {t("chapters.new")}
            </button>
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
              which is what makes the mode distraction-free. The dock tab sits
              beside it: the one always-visible handle on the dock, pressed
              exactly when a dock child route is showing. */}
          {focus < 2 ? (
            <button
              type="button"
              onClick={() => step(focus === 0 ? 1 : 0)}
              className="ml-3 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel"
            >
              {focus === 0 ? t("workspace.focus") : t("workspace.unfocus")}
            </button>
          ) : null}
          {focus < 2 ? (
            <button
              type="button"
              onClick={toggleDock}
              aria-pressed={dockMatched}
              className="ml-3 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground"
            >
              {t("workspace.dockChat")}
            </button>
          ) : null}
          {current ? (
            <ChapterEditor
              key={current.id}
              chapterId={current.id}
              body={current.body}
              onSaved={remember}
            />
          ) : null}
        </section>

        {/* The right dock: a child route of this workspace renders here —
            the tab's navigation decides which one, and the matched child is
            the dock's open state. The column scrolls alone so a long answer
            never scrolls the editor out of view. */}
        {showDockPanel ? (
          <aside
            className="w-96 shrink-0 rounded-lg border border-border bg-panel p-4"
            aria-label={t("workspace.dockChat")}
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">{t("workspace.dockChat")}</h2>
              <button
                type="button"
                onClick={toggleDock}
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
