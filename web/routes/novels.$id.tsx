import { createRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";

import { ChapterEditor } from "../components/ChapterEditor";
import { client, type Chapter, type Novel } from "../lib/api/client";
import { useTranslation } from "../lib/i18n";
import { rootRoute } from "./__root";

function NovelPage() {
  const t = useTranslation();
  const { id: novelId } = novelRoute.useParams();
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
    setActive((previous) => previous ?? loadedChapters[0]?.id ?? null);
  }, [novelId]);

  useEffect(() => {
    void load();
  }, [load]);

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
    <div className="mx-auto max-w-2xl px-4 py-10">
      <Link to="/" className="text-sm text-muted underline-offset-4 hover:underline">
        {t("nav.back")}
      </Link>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">{novel?.title}</h1>

      <section className="mt-6">
        <h2 className="text-lg font-semibold">{t("chapters.heading")}</h2>
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
          className="mt-3 rounded-md border border-border px-3 py-2 text-sm font-medium"
        >
          {t("chapters.new")}
        </button>
      </section>

      {current ? (
        <ChapterEditor
          key={current.id}
          chapterId={current.id}
          body={current.body}
          onSaved={remember}
        />
      ) : null}
    </div>
  );
}

export const novelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$id",
  component: NovelPage,
});
