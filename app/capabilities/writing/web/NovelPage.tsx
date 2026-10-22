import { Link, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";

import { client, type Chapter, type Novel } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";

import { ChapterEditor } from "./ChapterEditor";

/** The novel workbench: the chapter rail beside the editor, panel state in the URL. */
export function NovelPage() {
  const t = useTranslation();
  // By route id, not the route object: the page stands apart from
  // routes.tsx, and the registered router still types `id` from the string.
  const { id: novelId } = useParams({ from: "/novels/$id" });
  const { rail } = useSearch({ from: "/novels/$id" });
  // Absent means expanded: only an explicit collapsed encoding (validated to
  // false in routes.tsx) hides the rail.
  const collapsed = rail === false;
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
  const toggleRail = useCallback(() => {
    void navigate({
      to: "/novels/$id",
      params: { id: novelId },
      search: { rail: collapsed },
    });
  }, [navigate, novelId, collapsed]);

  async function createChapter() {
    // An explicit empty title: the placeholder is a display concern, and
    // storing a title would freeze one locale's wording into the database.
    // The server treats an empty title exactly like an omitted one.
    const { data: chapter } = await client.POST(
      "/api/writing/novels/{novel_id}/chapters",
      { params: { path: { novel_id: novelId } }, body: { title: "" } },
    );
    if (!chapter) return;
    setChapters((previous) => [...previous, chapter]);
    setActive(chapter.id);
  }

  const remember = useCallback((chapterId: string, body: string) => {
    setChapters((previous) =>
      previous.map((chapter) =>
        chapter.id === chapterId ? { ...chapter, body } : chapter,
      ),
    );
  }, []);

  const current = chapters.find((chapter) => chapter.id === active) ?? null;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <Link to="/" className="text-sm text-muted underline-offset-4 hover:underline">
        {t("nav.back")}
      </Link>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">{novel?.title}</h1>

      {/* The workbench: the rail beside the editor, so writing never scrolls
          past the chapter list. Collapsed, the rail unmounts and the editor
          takes the full width. */}
      <div className="mt-6 flex items-start gap-6">
        {!collapsed ? (
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
          {collapsed ? (
            <button
              type="button"
              onClick={toggleRail}
              className="rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel"
            >
              {t("workspace.expandRail")}
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
      </div>
    </div>
  );
}
