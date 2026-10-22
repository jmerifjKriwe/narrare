"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { client, type Novel } from "../lib/api/client";
import { t } from "../lib/i18n";

export default function NovelsPage() {
  const router = useRouter();
  const [novels, setNovels] = useState<Novel[]>([]);
  const [title, setTitle] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const { data: status } = await client.GET("/api/setup/status");
      if (cancelled) return;
      if (status && !status.complete) {
        // Nothing to list yet: an uninstalled instance starts at setup.
        router.replace("/setup");
        return;
      }
      const { data: loaded } = await client.GET("/api/writing/novels");
      if (cancelled) return;
      setNovels(loaded ?? []);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function reload() {
    const { data } = await client.GET("/api/writing/novels");
    setNovels(data ?? []);
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (title.trim() === "") return;
    await client.POST("/api/writing/novels", { body: { title } });
    setTitle("");
    await reload();
  }

  if (!ready) return null;

  return (
    <main>
      <h1>{t("novels.heading")}</h1>
      <p>
        <Link href="/knowledge">{t("nav.knowledge")}</Link>
        <span aria-hidden="true"> · </span>
        <Link href="/chat">{t("nav.chat")}</Link>
      </p>
      <form onSubmit={create}>
        <label>
          {t("novels.titleLabel")}
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <button type="submit">{t("novels.create")}</button>
      </form>
      <ul>
        {novels.map((novel) => (
          <li key={novel.id}>
            <Link href={`/novels/${novel.id}`}>{novel.title}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
