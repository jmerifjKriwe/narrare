"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { client, type Novel } from "../lib/api/client";
import { t } from "../lib/i18n";
import { nav } from "../lib/generated/capabilities";

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
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("novels.heading")}</h1>
      <p className="mt-2 text-sm text-muted">
        {nav.map((entry, index) => (
          <span key={entry.id}>
            {index > 0 && <span aria-hidden="true"> · </span>}
            <Link href={entry.path} className="underline-offset-4 hover:underline">
              {t(entry.titleKey)}
            </Link>
          </span>
        ))}
      </p>
      <form onSubmit={create} className="mt-6 flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t("novels.titleLabel")}
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="rounded-md border border-border bg-card px-3 py-2 text-base font-normal focus:border-primary focus:outline-none"
          />
        </label>
        <button
          type="submit"
          className="self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
        >
          {t("novels.create")}
        </button>
      </form>
      <ul className="mt-8 flex flex-col gap-2">
        {novels.map((novel) => (
          <li key={novel.id} className="rounded-lg border border-border bg-card">
            <Link
              href={`/novels/${novel.id}`}
              className="block px-4 py-3 underline-offset-4 hover:underline"
            >
              {novel.title}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
