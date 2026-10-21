"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { t } from "../lib/i18n";

type Novel = { id: string; title: string; created_at: string };

export default function NovelsPage() {
  const router = useRouter();
  const [novels, setNovels] = useState<Novel[]>([]);
  const [title, setTitle] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const statusResponse = await fetch("/api/setup/status");
      const status: { complete: boolean } = await statusResponse.json();
      if (cancelled) return;
      if (!status.complete) {
        // Nothing to list yet: an uninstalled instance starts at setup.
        router.replace("/setup");
        return;
      }
      const novelsResponse = await fetch("/api/writing/novels");
      if (cancelled) return;
      setNovels(await novelsResponse.json());
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function reload() {
    const response = await fetch("/api/writing/novels");
    setNovels(await response.json());
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (title.trim() === "") return;
    await fetch("/api/writing/novels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
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
