"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { t } from "../lib/i18n";

type Novel = { id: string; title: string; created_at: string };

export default function NovelsPage() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [title, setTitle] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/writing/novels");
    setNovels(await response.json());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (title.trim() === "") return;
    await fetch("/api/writing/novels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    setTitle("");
    await load();
  }

  return (
    <main>
      <h1>{t("novels.heading")}</h1>
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
