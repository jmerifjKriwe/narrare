import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Field, FileInput, Input } from "@shell/ui/field";
import { client, isModelChange, type Hit, type KnowledgeDocument } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";
import { Row } from "@shell/ui/Row";

/**
 * The seam the documents read goes through: the page renders only what
 * this returns, and the return names the one honest split — an answer
 * that is not "ok" is `failed`, never an empty list, because "no
 * documents" is a fact only a reachable service can claim (F14). An ok
 * answer with no data is honestly empty; with data, the rows pass
 * through untouched. Exported for the unit test.
 */
export function readDocuments(result: {
  data?: KnowledgeDocument[];
  response: { ok: boolean };
}): { kind: "ok"; documents: KnowledgeDocument[] } | { kind: "failed" } {
  if (!result.response.ok) return { kind: "failed" };
  return { kind: "ok", documents: result.data ?? [] };
}

/** The documents area's four states: the wait, the outage, the honest
 *  empty, the list. Everything the page claims about the library is one
 *  of these, and all four speak through `Notice`. */
type Load =
  | { kind: "loading" }
  | { kind: "ok"; documents: KnowledgeDocument[] }
  | { kind: "failed" };

/** Ask once for the documents, through the seam. A service that will not
 *  answer at all — fetch rejecting before any response exists — is the
 *  same outage a refusal is, and lands in the same state. */
async function askDocuments(): Promise<Load> {
  try {
    return readDocuments(await client.GET("/api/knowledge/documents"));
  } catch {
    return { kind: "failed" };
  }
}

/**
 * The upload form: the fields, the file and the failure live and die with
 * one mounting — the dialog mounts its content fresh on every open, so
 * nothing here outlives the dialog it belongs to. A refused upload keeps
 * the dialog open (the typed values are the user's work, and the retry is
 * the same button); the model-change refusal is the page's answer to give
 * — the dialog closes and the page's warning names the repair.
 */
function UploadForm({
  close,
  onUploaded,
  onModelChanged,
}: {
  close: () => void;
  onUploaded: () => Promise<void>;
  onModelChanged: () => void;
}) {
  const t = useTranslation();
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [failed, setFailed] = useState(false);

  /** Upload the file; close on success and on the model-change refusal, keep the dialog on the rest. */
  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (file === null) return;
    setFailed(false);
    const body = new FormData();
    body.append("file", file);
    if (title.trim() !== "") body.append("title", title);
    // openapi-typescript renders the binary part as `string`, which a real
    // FormData is not — one cast. The runtime contract (multipart/form-data,
    // browser sets the boundary) is exactly what the endpoint speaks.
    // The try wraps the POST alone: a throw after a successful upload must
    // not lie about failure — the success path sits after it.
    try {
      const { error, response } = await client.POST("/api/knowledge/documents", {
        body: body as unknown as { file: string; title?: string },
      });
      if (!response.ok) {
        if (isModelChange(error)) {
          // The corpus refused the width: the repair is the page's business
          // (its warning carries the re-embed), not the dialog's.
          onModelChanged();
          close();
          return;
        }
        setFailed(true);
        return;
      }
    } catch {
      // A service that does not answer is a refused upload, not silence:
      // the dialog keeps the typed work and names the refusal where the
      // retry — the same button — sits.
      setFailed(true);
      return;
    }
    await onUploaded();
    close();
  }

  return (
    <form onSubmit={(event) => void upload(event)} className="mt-4 flex flex-col gap-3">
      <Field label={t("knowledge.fileLabel")}>
        {/* The shared file input (`FileInput`): the control contract plus
            the native button's paint — the import dialog's treatment, one
            definition (R49's census round). */}
        <FileInput
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </Field>
      <Field label={t("knowledge.titleLabel")}>
        <Input value={title} onChange={(event) => setTitle(event.target.value)} />
      </Field>
      {failed ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.errorUpload")}
        </Notice>
      ) : null}
      <Button type="submit" variant="primary" className="self-start">
        {t("knowledge.upload")}
      </Button>
    </form>
  );
}

/** The knowledge page: search the corpus by meaning, and mind the library
 *  the passages come from — its upload lives behind one dialog, its read
 *  speaks through one seam, and nothing here mistakes a dead service for
 *  an empty shelf. */
export function KnowledgePage() {
  const t = useTranslation();
  // The tab's name: this page is "Wissen" until it goes.
  usePageTitle(t("knowledge.heading"));
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [searchError, setSearchError] = useState(false);
  const [modelChanged, setModelChanged] = useState(false);
  const [reembedFailed, setReembedFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const answer = await askDocuments();
      if (!cancelled) setLoad(answer);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function reload() {
    setLoad(await askDocuments());
  }

  async function search(event: React.FormEvent) {
    event.preventDefault();
    if (query.trim() === "") return;
    setSearchError(false);
    const limit = 5; // the server's own default, pinned here by the request type
    try {
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
    } catch {
      // A service that does not answer is a refused search, not silence.
      setSearchError(true);
    }
  }

  async function reembed() {
    setReembedFailed(false);
    try {
      const { response } = await client.POST("/api/knowledge/reembed");
      if (!response.ok) {
        // F15: the repair did not happen — said, where the retry sits.
        setReembedFailed(true);
        return;
      }
      setModelChanged(false);
      await reload();
    } catch {
      setReembedFailed(true);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("knowledge.heading")}</h1>
      <p className="mt-2 text-body text-muted">
        <Link
          to="/"
          className="underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("nav.back")}
        </Link>
      </p>

      {/* The ask: one field, one submit — the page's only search. */}
      <form onSubmit={search} className="mt-6 flex flex-col gap-2">
        <Field label={t("knowledge.queryLabel")}>
          <Input value={query} onChange={(event) => setQuery(event.target.value)} />
        </Field>
        <Button type="submit" variant="secondary" className="self-start">
          {t("knowledge.search")}
        </Button>
      </form>
      {searchError ? (
        <Notice tone="danger" live="alert" className="mt-2">
          {t("knowledge.errorSearch")}
        </Notice>
      ) : null}
      {modelChanged ? (
        // The corpus refuses to answer at the new width: the repair is the
        // one primary-named control beside it.
        <Notice
          tone="danger"
          live="alert"
          className="mt-2"
          action={
            <Button variant="secondary" onClick={() => void reembed()}>
              {t("knowledge.reembed")}
            </Button>
          }
        >
          {t("knowledge.modelChanged")}
        </Notice>
      ) : null}
      {reembedFailed ? (
        // The repair's own failure, named apart from the condition it
        // treats: a silent return would leave the warning standing as if
        // the re-embed had merely not been pressed yet.
        <Notice
          tone="danger"
          live="alert"
          className="mt-2"
          action={
            <Button variant="secondary" onClick={() => void reembed()}>
              {t("knowledge.retry")}
            </Button>
          }
        >
          {t("knowledge.errorReembed")}
        </Notice>
      ) : null}

      {hits === null ? null : (
        <Panel title={t("knowledge.hitsHeading")} dense className="mt-6">
          {hits.length === 0 ? (
            <Notice tone="quiet">{t("knowledge.noResults")}</Notice>
          ) : (
            <div>
              {hits.map((hit) => (
                // The hit is a row on the rule: the document's title, the
                // snippet under it. The row grows past the 28 px control
                // height because the snippet is the content — the rule
                // between rows is what keeps the column readable.
                <Row
                  as="div"
                  flush
                  key={hit.chunk_id}
                  className="h-auto flex-col items-stretch gap-1 py-2"
                >
                  <span className="text-label font-semibold">{hit.document_title}</span>
                  <span className="text-body leading-relaxed text-muted group-hover:text-foreground">
                    {hit.text}
                  </span>
                </Row>
              ))}
            </div>
          )}
        </Panel>
      )}

      <Panel
        title={t("knowledge.documentsHeading")}
        dense
        className="mt-6"
        actions={
          <Dialog title={t("knowledge.newDocument")} triggerLabel={t("knowledge.addDocument")}>
            {(close) => (
              <UploadForm
                close={close}
                onUploaded={reload}
                onModelChanged={() => setModelChanged(true)}
              />
            )}
          </Dialog>
        }
      >
        {load.kind === "loading" ? (
          // The answer has not arrived yet: the page asks rather than
          // claims — not the library, and not its empty state either. The
          // wait paints the list's own shape (rows at their loaded size,
          // the pulse under `motion-safe:`) beside the status line, so the
          // answer's arrival moves nothing.
          <>
            <div aria-hidden="true" className="flex flex-col">
              {[0, 1, 2].map((row) => (
                <div key={row} className="flex h-7 items-center px-3">
                  <div className="h-3 w-1/3 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
                </div>
              ))}
            </div>
            <Notice tone="quiet" live="status" className="mt-2">
              {t("knowledge.loading")}
            </Notice>
          </>
        ) : load.kind === "failed" ? (
          // F14: the outage is the state — named, with the way back in the
          // same notice. The empty claim stays silent here.
          <Notice
            tone="danger"
            live="alert"
            action={
              <Button variant="secondary" onClick={() => void reload()}>
                {t("knowledge.retry")}
              </Button>
            }
          >
            {t("knowledge.errorDocuments")}
          </Notice>
        ) : load.documents.length === 0 ? (
          <Notice tone="quiet">{t("knowledge.empty")}</Notice>
        ) : (
          <div>
            {load.documents.map((document) => (
              <Row as="div" key={document.id} flush>
                {document.title}
              </Row>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
