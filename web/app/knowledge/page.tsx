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
      {modelChanged ? (
        <p role="alert">
          {t("knowledge.modelChanged")}{" "}
          <button type="button" onClick={() => void reembed()}>
            {t("knowledge.reembed")}
          </button>
        </p>
      ) : null}
      {uploadError ? (
        <p role="alert">{t("knowledge.errorUpload")}</p>
      ) : null}
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
      {searchError ? <p role="alert">{t("knowledge.errorSearch")}</p> : null}
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
