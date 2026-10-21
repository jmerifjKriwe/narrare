"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { t } from "../../lib/i18n";

type Document = { id: string; title: string; created_at: string };
type Hit = {
  chunk_id: string;
  document_id: string;
  document_title: string;
  text: string;
  score: number;
};

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const response = await fetch("/api/knowledge/documents");
      if (cancelled) return;
      setDocuments(await response.json());
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function reload() {
    const response = await fetch("/api/knowledge/documents");
    setDocuments(await response.json());
  }

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (file === null) return;
    const body = new FormData();
    body.append("file", file);
    if (title.trim() !== "") body.append("title", title);
    const response = await fetch("/api/knowledge/documents", { method: "POST", body });
    if (!response.ok) return;
    setTitle("");
    await reload();
  }

  async function search(event: React.FormEvent) {
    event.preventDefault();
    if (query.trim() === "") return;
    const response = await fetch("/api/knowledge/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    setHits(await response.json());
  }

  if (!ready) return null;

  return (
    <main>
      <h1>{t("knowledge.heading")}</h1>
      <p>
        <Link href="/">{t("nav.back")}</Link>
      </p>
      <form onSubmit={upload}>
        <label>
          {t("knowledge.fileLabel")}
          <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
        <label>
          {t("knowledge.titleLabel")}
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <button type="submit">{t("knowledge.upload")}</button>
      </form>
      {documents.length === 0 ? (
        <p>{t("knowledge.empty")}</p>
      ) : (
        <ul>
          {documents.map((document) => (
            <li key={document.id}>{document.title}</li>
          ))}
        </ul>
      )}
      <form onSubmit={search}>
        <label>
          {t("knowledge.queryLabel")}
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <button type="submit">{t("knowledge.search")}</button>
      </form>
      {hits === null ? null : hits.length === 0 ? (
        <p>{t("knowledge.noResults")}</p>
      ) : (
        <ul>
          {hits.map((hit) => (
            <li key={hit.chunk_id}>
              <strong>{hit.document_title}</strong>
              <p>{hit.text}</p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
