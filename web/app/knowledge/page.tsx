"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { client, isModelChange, type Hit, type KnowledgeDocument } from "../../lib/api/client";
import { t } from "../../lib/i18n";

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [ready, setReady] = useState(false);
  const [uploadError, setUploadError] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const [modelChanged, setModelChanged] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const { data } = await client.GET("/api/knowledge/documents");
      if (cancelled) return;
      setDocuments(data ?? []);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function reload() {
    const { data } = await client.GET("/api/knowledge/documents");
    setDocuments(data ?? []);
  }

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (file === null) return;
    const body = new FormData();
    body.append("file", file);
    if (title.trim() !== "") body.append("title", title);
    // openapi-typescript renders the binary part as `string`, which a real
    // FormData is not — one cast. The runtime contract (multipart/form-data,
    // browser sets the boundary) is exactly what the endpoint speaks.
    const { error, response } = await client.POST("/api/knowledge/documents", {
      body: body as unknown as { file: string; title?: string },
    });
    if (!response.ok) {
      const changed = isModelChange(error);
      setUploadError(!changed);
      setModelChanged(changed);
      return;
    }
    setUploadError(false);
    setModelChanged(false);
    setTitle("");
    await reload();
  }

  async function search(event: React.FormEvent) {
    event.preventDefault();
    if (query.trim() === "") return;
    const limit = 5; // the server's own default, pinned here by the request type
    const { data, error, response } = await client.POST("/api/knowledge/search", {
      body: { query, limit },
    });
    if (!response.ok) {
      const changed = isModelChange(error);
      setSearchError(!changed);
      setModelChanged(changed);
      return;
    }
    setSearchError(false);
    setModelChanged(false);
    setHits(data ?? []);
  }

  async function reembed() {
    const { response } = await client.POST("/api/knowledge/reembed");
    if (!response.ok) return;
    setModelChanged(false);
    await reload();
  }

  if (!ready) return null;

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("knowledge.heading")}</h1>
      <p className="mt-2 text-sm text-muted">
        <Link href="/" className="underline-offset-4 hover:underline">
          {t("nav.back")}
        </Link>
      </p>
      <form onSubmit={upload} className="mt-6 flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t("knowledge.fileLabel")}
          <input
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="rounded-md border border-border bg-card px-3 py-2 text-sm font-normal file:mr-3 file:rounded file:border-0 file:bg-transparent file:text-sm file:font-medium"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t("knowledge.titleLabel")}
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
          {t("knowledge.upload")}
        </button>
      </form>
      {modelChanged ? (
        <p role="alert" className="mt-4 flex flex-wrap items-center gap-2 text-sm text-danger">
          {t("knowledge.modelChanged")}{" "}
          <button
            type="button"
            onClick={() => void reembed()}
            className="rounded-md border border-danger px-2 py-1 font-medium"
          >
            {t("knowledge.reembed")}
          </button>
        </p>
      ) : null}
      {uploadError ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {t("knowledge.errorUpload")}
        </p>
      ) : null}
      {documents.length === 0 ? (
        <p className="mt-6 text-sm text-muted">{t("knowledge.empty")}</p>
      ) : (
        <ul className="mt-6 flex flex-col gap-2">
          {documents.map((document) => (
            <li
              key={document.id}
              className="rounded-lg border border-border bg-card px-4 py-3 text-sm"
            >
              {document.title}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={search} className="mt-8 flex flex-col gap-2">
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t("knowledge.queryLabel")}
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="rounded-md border border-border bg-card px-3 py-2 text-base font-normal focus:border-primary focus:outline-none"
          />
        </label>
        <button
          type="submit"
          className="self-start rounded-md border border-border px-3 py-2 text-sm font-medium"
        >
          {t("knowledge.search")}
        </button>
      </form>
      {searchError ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {t("knowledge.errorSearch")}
        </p>
      ) : null}
      {hits === null ? null : hits.length === 0 ? (
        <p className="mt-6 text-sm text-muted">{t("knowledge.noResults")}</p>
      ) : (
        <ul className="mt-6 flex flex-col gap-3">
          {hits.map((hit) => (
            <li key={hit.chunk_id} className="rounded-lg border border-border bg-card p-4">
              <strong className="text-sm font-semibold">{hit.document_title}</strong>
              <p className="mt-1 text-sm leading-relaxed text-muted">{hit.text}</p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
