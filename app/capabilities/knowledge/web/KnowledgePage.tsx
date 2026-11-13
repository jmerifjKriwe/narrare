import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Field, FileInput, Input } from "@shell/ui/field";
import { client, isModelChange, type Hit, type KnowledgeDocument } from "@shell/lib/api/client";
import { formatDate } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useDeleteDocument } from "@shell/lib/query";
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
 * A byte count in human reading, on the decimal ladder the 1 MB upload
 * limit itself speaks, one decimal past the unit — the limit's own edge
 * reads "1.0 MB", not "1000 kB". The ladder steps AFTER rounding: 999 999
 * bytes are "1000.0 kB" before the step, and a unit the ladder itself
 * says does not exist is not an answer — the value crosses into the
 * megabyte it already rounds to. `null` is a size the row predates: the
 * size is unknown, and unknown is not a guessed "0 B", so the caller
 * renders no size slot at all. Exported for the unit test.
 */
export function formatBytes(bytes: number | null): string | null {
  if (bytes === null) return null;
  const units = ["B", "kB", "MB"] as const;
  let value = bytes;
  let unit = 0;
  while (unit < units.length - 1) {
    // The value as it would be written at this rung: only a value that
    // still reads under a thousand after rounding stays put.
    const shown = Math.round(value * 10) / 10;
    if (shown < 1000) break;
    value /= 1000;
    unit += 1;
  }
  return unit === 0 ? `${value} B` : `${value.toFixed(1)} ${units[unit]}`;
}

/**
 * An upload's calendar date in the reader's own words — "07.11.2026" in
 * German, "Nov 7, 2026" in English — through the shared helper, so the chosen
 * language keeps the browser's regional variant (de-AT). The platform's
 * wording, so no catalog carries it (`formatRelative`'s precedent).
 */
function formatUploadedDate(timestamp: string): string {
  // Guard the unparseable case: `formatDate` throws on an invalid date,
  // which would take the whole panel down. Render the raw string instead.
  if (Number.isNaN(Date.parse(timestamp))) return timestamp;
  return formatDate(timestamp, { dateStyle: "medium" });
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

/**
 * Delete a document: the warning says the two things a writer needs
 * before confirming — this is final, and final only here: the original
 * file on disk stays where it was uploaded from (WP3 D2). The confirm is
 * the book delete's shape: a refusal stays open and is named where the
 * retry — the same button — sits; the 204 closes the dialog and
 * refreshes the one read that shows the list.
 */
function DeleteForm({
  document,
  close,
  onDeleted,
}: {
  document: KnowledgeDocument;
  close: () => void;
  onDeleted: () => Promise<void>;
}) {
  const t = useTranslation();
  const deleteDocument = useDeleteDocument();
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState(false);

  /** Confirm the delete: the 204 closes after the list has re-read; a refusal stays and is named. */
  async function confirm() {
    setBusy(true);
    setRefusal(false);
    try {
      await deleteDocument.mutateAsync(document.id);
    } catch (error) {
      // A 404 means the document is already gone — the user's intent (delete
      // it) is satisfied, so close instead of blaming the service (#707).
      if (error instanceof Error && /404/.test(error.message)) {
        await onDeleted();
        close();
        return;
      }
      setRefusal(true);
      return;
    } finally {
      setBusy(false);
    }
    await onDeleted();
    close();
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      <p className="text-body text-muted">
        {t("knowledge.deleteBody", { title: document.title })}
      </p>
      {refusal ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.errorDelete")}
        </Notice>
      ) : null}
      <div className="mt-2 flex justify-end gap-3">
        <Button onClick={close}>{t("knowledge.cancel")}</Button>
        <Button variant="primary" disabled={busy} onClick={() => void confirm()}>
          {t("knowledge.delete")}
        </Button>
      </div>
    </div>
  );
}

/**
 * One document in the list: its name, and the three facts the row's own
 * read already holds — what was stored (the size; a row from before the
 * column knows no size, and the row says nothing rather than guess a
 * "0 B"), what it answers search with (its passages), and when it came
 * in. The delete rides at the row's end behind its confirm, named for
 * the document it deletes — a list of "Löschen" triggers must stay
 * tellable apart for a keyboard and a screen reader alike.
 */
function DocumentRow({
  document,
  onDeleted,
}: {
  document: KnowledgeDocument;
  onDeleted: () => Promise<void>;
}) {
  const t = useTranslation();
  // The size joins only when it exists: unknown is absent, never zero —
  // the same honesty the row's other two facts carry.
  const size = formatBytes(document.byte_size);
  const facts = [
    ...(size === null ? [] : [size]),
    t("knowledge.chunkCount", { count: document.chunk_count }),
    t("knowledge.uploadedOn", { date: formatUploadedDate(document.created_at) }),
  ].join(" · ");
  return (
    <Row
      as="div"
      flush
      // The row may grow past the 28 px control height when the window is
      // narrow: the facts and the trigger are content, not chrome, so
      // they wrap under the title (the hits rows' own shape) instead of
      // manufacturing a sideways scroll inside the shell's box. Where
      // the line fits — a one-line row on any desk — the row is exactly
      // the paint the panel shipped: title left, facts and trigger
      // right, 28 px tall, the size the loading skeleton already paints.
      className="h-auto flex-wrap gap-x-2 gap-y-1"
      trailing={
        <>
          <span className="ml-auto shrink-0 text-label text-muted group-hover:text-foreground">
            {facts}
          </span>
          <Dialog
            title={t("knowledge.deleteTitle")}
            triggerLabel={t("knowledge.delete")}
            triggerAriaLabel={t("knowledge.deleteFor", { title: document.title })}
          >
            {(close) => (
              <DeleteForm document={document} close={close} onDeleted={onDeleted} />
            )}
          </Dialog>
        </>
      }
    >
      <span className="min-w-0 truncate">{document.title}</span>
    </Row>
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
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("nav.back")}
        </Link>
      </p>
      {/* The canvas door: the novel's entities and relations as one
          selectable page — the dock lens it complements arrives in its
          own slice, this link is the hub's. */}
      <p className="mt-2 text-body text-muted">
        <Link
          to="/knowledge/graph"
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("knowledge.graphOpenLink")}
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
                <div key={row} className="flex h-7 items-center border-b border-rule">
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
              <DocumentRow key={document.id} document={document} onDeleted={reload} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
