"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ChapterEditor } from "../../../components/ChapterEditor";
import { t } from "../../../lib/i18n";

type Novel = { id: string; title: string };
type Chapter = { id: string; title: string; position: number; body: string };

export default function NovelPage() {
  const params = useParams();
  const novelId = String(params.id);
  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [active, setActive] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [novelResponse, chaptersResponse] = await Promise.all([
      fetch(`/api/writing/novels/${novelId}`),
      fetch(`/api/writing/novels/${novelId}/chapters`),
    ]);
    const loadedNovel: Novel = await novelResponse.json();
    const loadedChapters: Chapter[] = await chaptersResponse.json();
    setNovel(loadedNovel);
    setChapters(loadedChapters);
    setActive((previous) => previous ?? loadedChapters[0]?.id ?? null);
  }, [novelId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createChapter() {
    const number = chapters.length + 1;
    const response = await fetch(`/api/writing/novels/${novelId}/chapters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: t("chapters.defaultTitle").replace("{n}", String(number)),
      }),
    });
    const chapter: Chapter = await response.json();
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
    <main>
      <Link href="/">{t("nav.back")}</Link>
      <h1>{novel?.title}</h1>

      <section>
        <h2>{t("chapters.heading")}</h2>
        {chapters.length === 0 ? <p>{t("chapters.empty")}</p> : null}
        <ul>
          {chapters.map((chapter) => (
            <li key={chapter.id}>
              <button
                type="button"
                aria-pressed={chapter.id === active}
                onClick={() => setActive(chapter.id)}
              >
                {chapter.title}
              </button>
            </li>
          ))}
        </ul>
        <button type="button" onClick={createChapter}>
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
    </main>
  );
}
