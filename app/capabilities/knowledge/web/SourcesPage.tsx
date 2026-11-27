/**
 * The sources archive (W5 Task 6) — the knowledge capability's document
 * archive, ported from the owner-approved harmonized `sources-archive-2`
 * draft onto the shell's tokens. The library's real documents and the real
 * semantic search:
 *
 * - The document list carries one row per DocumentRead: the title, the
 *   byte size (NULL for rows ingested before the column existed — those
 *   show no size, nothing invented), the upload date and the real chunk
 *   count. The meta line's extension summary is DERIVED from the real
 *   titles, never the draft's mock list. The upload fires the real
 *   multipart endpoint (the `file` field); the picker mirrors the
 *   service's own bounds first — plain text only, 1 MB — so a refused
 *   file is never sent, and the server's 413/422/409 still answer through
 *   the mutation's error face, each named in its own words. The delete
 *   rides the destructive confirm family (crudDialogs' one home): the
 *   chunk consequence named before it happens, the settled list refetched
 *   from the server.
 * - The semantic search round-trips the real query (POST /search, the
 *   server's own limit) into the draft's result-card geometry: the rank
 *   badge (the server's ordering — honest, no invented percentage score),
 *   the document title and the chunk excerpt. SearchHit carries no chunk
 *   index or page, so the draft's „Chunk 14 · Seite 14" meta is not drawn.
 *   The no-hit face names the query; the outage and the embedding
 *   mismatch each name themselves apart. An explicit submit is an
 *   explicit re-ask: resubmitting the same words retires their cached
 *   answer first, so the POST goes out again within the staleTime.
 * - The footnote and fact-check areas stand as the draft's honest disabled
 *   gaps (a status-only "Not available yet." note) — no endpoint serves them,
 *   no fake content rides them. The view doors (Ansehen / Im Originaldokument
 *   anzeigen) are disabled with the same gap note: no endpoint serves the
 *   original document's bytes.
 * - The subbar's sibling doors connect the three surfaces (graph, dossiers,
 *   sources) — one consistent mechanism, the Tasks 3/5 door extended.
 *   Documents are the library's, never an entity's (D8), so no selection
 *   travels these doors.
 *
 * The page reads the real API through the shell's query seam and imports
 * no other capability (rule 1). Loading, outage and the empty archive each
 * answer with their own honest face; the empty archive IS the upload
 * invitation.
 */
import { useNavigate, useParams } from "@tanstack/react-router";
import { useMemo, useRef, useState } from "react";

import { codeOf } from "@shell/lib/api/errors";
import { isModelChange, type KnowledgeDocument } from "@shell/lib/api/client";
import { formatDate } from "@shell/lib/format";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useDocumentsQuery, useNovelQuery, useSourceSearch, invalidateSourceSearch, useUploadDocument } from "@shell/lib/query";
import { CARD_EYEBROW, FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { DeleteDocumentDialog } from "./crudDialogs";
import { formatBytes, isTextFile, MAX_UPLOAD_BYTES, titleExtensions } from "./sources";

const SOURCES_PATH = "/novels/$novelId/knowledge/sources";
const GRAPH_PATH = "/novels/$novelId/knowledge/graph";
const DOSSIERS_PATH = "/novels/$novelId/knowledge/dossiers";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The upload's refusals, each named in its own words — the client-side
 *  bounds and the server's answers share the vocabulary (a 413 IS the
 *  size bound the picker mirrors). Only the generic failure offers a
 *  retry: the same file re-sent is the loss-free ask; a bound crossed or
 *  a model changed is not re-asked into a different answer. */
type UploadRefusal = "tooLarge" | "wrongType" | "empty" | "mismatch" | "failed";

const UPLOAD_MESSAGES: Record<UploadRefusal, MessageKey> = {
  tooLarge: "knowledge.sources.uploadTooLarge",
  wrongType: "knowledge.sources.uploadWrongType",
  empty: "knowledge.sources.uploadEmpty",
  mismatch: "knowledge.sources.mismatch",
  failed: "knowledge.sources.uploadFailed",
};

function classifyUpload(error: unknown): UploadRefusal {
  const status = (error as { status?: number } | null)?.status;
  if (status === 413) return "tooLarge";
  if (codeOf(error) === "document-empty") return "empty";
  if (isModelChange(error)) return "mismatch";
  return "failed";
}

/** The shell's busy face (the crud dialogs' spinner): a ring with one
 *  transparent quarter, turning. No glyph — the motion is the mark. */
function Spinner() {
  return (
    <span aria-hidden="true" className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border border-primary-foreground border-t-transparent" />
  );
}

export function SourcesPage() {
  const t = useTranslation();
  const { novelId } = useParams({ from: SOURCES_PATH });
  const navigate = useNavigate();
  usePageTitle(t("knowledge.sources.title"));

  const documents = useDocumentsQuery();
  // The eyebrow's project name is the real book's own (the chrome's
  // breadcrumb names it too; the row is the one cached truth). A pending
  // or absent row leaves the apparatus label standing alone — the header
  // never invents a project.
  const novel = useNovelQuery(novelId);

  // --- The upload ----------------------------------------------------------
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const lastFileRef = useRef<File | null>(null);
  const upload = useUploadDocument();
  const [uploadRefusal, setUploadRefusal] = useState<UploadRefusal | null>(null);

  function send(file: File) {
    lastFileRef.current = file;
    upload.mutate(file, { onError: (error) => setUploadRefusal(classifyUpload(error)) });
  }

  /** The picker's answer: the client-side bounds first (a refused file is
   *  never sent), then the real multipart ask. */
  function pick(file: File | undefined) {
    if (file === undefined) return;
    setUploadRefusal(null);
    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadRefusal("tooLarge");
      return;
    }
    if (!isTextFile(file)) {
      setUploadRefusal("wrongType");
      return;
    }
    send(file);
  }

  function retryUpload() {
    const file = lastFileRef.current;
    if (file === null) return;
    setUploadRefusal(null);
    send(file);
  }

  // --- The semantic search ---------------------------------------------------
  const [draft, setDraft] = useState("");
  const [submitted, setSubmitted] = useState("");
  const search = useSourceSearch(submitted);
  const hits = search.data ?? [];

  // --- The delete ------------------------------------------------------------
  const [deleting, setDeleting] = useState<KnowledgeDocument | null>(null);

  const documentList = useMemo(() => documents.data ?? [], [documents.data]);
  const extensions = useMemo(() => titleExtensions(documentList.map((row) => row.title)), [documentList]);

  const uploadBusy = upload.isPending;
  const searchBusy = search.isPending && submitted !== "";

  return (
    <div id="sources-page" data-testid="sources-page" tabIndex={-1} className="flex h-full flex-col overflow-hidden focus:outline-none">
      {/* The subbar — the view label and the two sibling doors (the Tasks
          3/5 mechanism, extended to the third surface). Documents are the
          library's, so no selection travels. */}
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-border bg-surface-container-low px-4 py-2">
        <span className="flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta font-semibold text-foreground shadow-card">
          <span className="text-primary">
            <Icon name="autoStories" size={15} />
          </span>
          {t("knowledge.sources.title")}
        </span>
        <button
          type="button"
          data-testid="sources-graph-door"
          onClick={() => void navigate({ to: GRAPH_PATH, params: { novelId }, search: {} })}
          className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
        >
          <Icon name="hub" size={14} /> {t("knowledge.graph.title")}
        </button>
        <button
          type="button"
          data-testid="sources-dossiers-door"
          onClick={() => void navigate({ to: DOSSIERS_PATH, params: { novelId }, search: {} })}
          className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
        >
          <Icon name="viewList" size={14} /> {t("knowledge.dossiers.title")}
        </button>
      </div>

      {/* The draft's centered column: the header, the search, the archive,
          the two honest gap areas. The body scrolls; the subbar stays. */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6 lg:px-6">
          {/* The header — the apparatus eyebrow (the real project beside
              it when the row stands), the title, the description and the
              upload door. */}
          <header className="flex flex-col gap-3 border-b border-rule pb-5 md:flex-row md:items-end md:justify-between">
            <div>
              <div className={`${CARD_EYEBROW} mb-1 flex items-center gap-1.5`}>
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-primary" />
                <span>{t("knowledge.sources.eyebrow")}</span>
                {novel.data !== undefined && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span>{t("knowledge.sources.project", { title: novel.data.title })}</span>
                  </>
                )}
              </div>
              <h1 className={`${SERIF} text-2xl font-semibold text-foreground lg:text-3xl`}>{t("knowledge.sources.title")}</h1>
              <p className="mt-1 max-w-2xl text-body text-muted">{t("knowledge.sources.description")}</p>
            </div>
            <button
              type="button"
              data-testid="sources-upload"
              disabled={uploadBusy}
              aria-busy={uploadBusy}
              onClick={() => fileInputRef.current?.click()}
              className={`flex shrink-0 items-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-4 py-2 text-label font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
            >
              {uploadBusy ? <Spinner /> : <Icon name="uploadFile" size={16} />}
              {uploadBusy ? t("knowledge.sources.uploadBusy") : t("knowledge.sources.upload")}
            </button>
            {/* The picker itself: hidden, named, the text kinds the
                ingestion accepts. The value resets after every pick so the
                same file can be chosen again after a refusal. */}
            <input
              ref={fileInputRef}
              data-testid="sources-file-input"
              type="file"
              accept=".txt,.md,.markdown,text/plain,text/markdown"
              aria-label={t("knowledge.sources.upload")}
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                pick(file);
              }}
            />
          </header>

          {/* The upload's refusal face — the bound named, the file never
              silently dropped. Only the generic failure offers the retry
              that re-sends the very file. */}
          {uploadRefusal !== null && (
            <div
              role="alert"
              data-testid="sources-upload-error"
              className="flex items-start gap-1.5 rounded-[var(--radius-surface)] border border-rule border-l-2 border-l-danger bg-surface-container-lowest p-3"
            >
              <span className="mt-0.5 shrink-0 text-danger">
                <Icon name="warning" size={14} />
              </span>
              <div className="flex-1">
                <p className="text-meta leading-tight text-foreground">{t(UPLOAD_MESSAGES[uploadRefusal])}</p>
                {uploadRefusal === "failed" && (
                  <button
                    type="button"
                    onClick={retryUpload}
                    className={`mt-1 inline-flex items-center gap-1 text-meta font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
                  >
                    {t("knowledge.graph.retry")}
                    <Icon name="refresh" size={12} />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* The semantic search — the draft's card: the box and the
              button, the privacy note, the results beneath. */}
          <section aria-label={t("knowledge.sources.searchTitle")} className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1.5">
                <span className="text-primary">
                  <Icon name="search" size={18} />
                </span>
                <h2 className="text-lg font-semibold text-foreground">{t("knowledge.sources.searchTitle")}</h2>
              </div>
              <span className="text-meta text-muted">{t("knowledge.sources.searchEngine")}</span>
            </div>
            <div className="flex flex-col gap-3 rounded-[var(--radius-surface)] border border-rule bg-card p-4 shadow-card">
              <form
                data-testid="sources-search-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  const query = draft.trim();
                  if (query !== "") {
                    // The explicit re-ask (PR #923): the same words retire
                    // their cached answer first, so a resubmit re-POSTs
                    // instead of replaying the staleTime's first answer.
                    invalidateSourceSearch(query);
                    setSubmitted(query);
                  }
                }}
                className="flex flex-col gap-2 sm:flex-row"
              >
                <label className="relative block flex-1">
                  <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted">
                    <Icon name="search" size={14} />
                  </span>
                  <span className="sr-only">{t("knowledge.sources.searchTitle")}</span>
                  <input
                    data-testid="sources-search"
                    type="search"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder={t("knowledge.sources.searchPlaceholder")}
                    className={`w-full rounded-[var(--radius-control)] border border-rule bg-surface-container-low py-2 pl-8 pr-3 text-body text-foreground placeholder:text-muted focus:outline-none ${FOCUS}`}
                  />
                </label>
                <button
                  type="submit"
                  data-testid="sources-search-button"
                  disabled={draft.trim() === "" || searchBusy}
                  aria-busy={searchBusy}
                  className={`flex items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-secondary/15 px-5 py-2 text-label font-semibold text-foreground transition-colors hover:bg-secondary/25 disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
                >
                  <Icon name="search" size={14} /> {t("knowledge.sources.searchButton")}
                </button>
              </form>
              <p className="text-meta italic text-muted">{t("knowledge.sources.searchPrivacy")}</p>

              {/* The results — only once a query stands submitted. The
                  count is the server's own number; the rank is its
                  ordering, never an invented score. */}
              {submitted !== "" && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between border-b border-rule pb-1">
                    <span className={CARD_EYEBROW}>{t("knowledge.sources.results")}</span>
                    {search.isSuccess && (
                      <span role="status" data-testid="sources-hit-count" className="text-meta text-muted">
                        {t("knowledge.sources.hitCount", { count: hits.length })}
                      </span>
                    )}
                  </div>
                  {searchBusy ? (
                    <p role="status" data-testid="sources-search-busy" className="py-2 text-center text-meta text-muted">
                      {t("knowledge.sources.searchBusy")}
                    </p>
                  ) : search.isError ? (
                    <div
                      role="alert"
                      data-testid="sources-search-error"
                      className="space-y-1.5 rounded-[var(--radius-surface)] border border-danger/40 bg-panel p-3 text-center"
                    >
                      <p className="text-meta text-danger">
                        {isModelChange(search.error) ? t("knowledge.sources.mismatch") : t("knowledge.sources.searchFailed")}
                      </p>
                      <button
                        type="button"
                        onClick={() => void search.refetch()}
                        className={`rounded border border-border bg-surface-container-low px-2.5 py-1 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
                      >
                        {t("knowledge.graph.retry")}
                      </button>
                    </div>
                  ) : hits.length === 0 ? (
                    <div data-testid="sources-no-hits" className="space-y-1 rounded-[var(--radius-surface)] border border-rule bg-surface-container-low/50 p-4 text-center">
                      <p className="text-meta font-medium text-foreground">{t("knowledge.sources.noHits", { query: submitted })}</p>
                      <p className="text-meta text-muted">{t("knowledge.sources.noHitsNote")}</p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {hits.map((hit, index) => (
                        <article
                          key={hit.chunk_id}
                          data-testid="sources-hit"
                          className="flex flex-col gap-1.5 rounded-[var(--radius-surface)] border border-rule bg-surface-container-low p-3"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded bg-surface-container px-2 py-0.5 text-[11px] font-semibold text-foreground">
                              {t("knowledge.sources.rank", { rank: index + 1 })}
                            </span>
                            <span className="text-label font-semibold text-primary">{hit.document_title}</span>
                          </div>
                          {/* The draft's excerpt geometry: the chunk's own
                              words in quotation marks, on the inset surface. */}
                          <p className="rounded-[var(--radius-control)] border border-rule bg-surface-container-lowest p-2.5 text-body italic leading-relaxed text-foreground">
                            »{hit.text}«
                          </p>
                          <div className="flex justify-end">
                            <button
                              type="button"
                              data-testid="sources-open-original"
                              disabled
                              title={t("knowledge.sources.viewNote")}
                              className="flex cursor-not-allowed items-center gap-1 text-meta text-primary opacity-60"
                            >
                              <Icon name="openInNew" size={13} /> {t("knowledge.sources.openOriginal")}
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* The archive — the real rows, the honest states apart. */}
          <section aria-label={t("knowledge.sources.documentsTitle")} className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1.5">
                <span className="text-primary">
                  <Icon name="archive" size={18} />
                </span>
                <h2 className="text-lg font-semibold text-foreground">{t("knowledge.sources.documentsTitle")}</h2>
              </div>
              {documents.isSuccess && (
                <span data-testid="sources-file-meta" className="text-meta text-muted">
                  {t("knowledge.sources.fileCount", { count: documentList.length })}
                  {extensions.length > 0 && ` (${extensions.map((extension) => `.${extension}`).join(", ")})`}
                </span>
              )}
            </div>
            {documents.isPending ? (
              <p role="status" data-testid="sources-loading" className="py-4 text-center text-meta text-muted">
                {t("knowledge.sources.loading")}
              </p>
            ) : documents.isError ? (
              <div
                role="alert"
                data-testid="sources-load-error"
                className="space-y-1.5 rounded-[var(--radius-surface)] border border-danger/40 bg-panel p-4 text-center"
              >
                <p className="text-meta text-danger">{t("knowledge.sources.loadFailed")}</p>
                <button
                  type="button"
                  onClick={() => void documents.refetch()}
                  className={`rounded border border-border bg-surface-container-low px-2.5 py-1 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
                >
                  {t("knowledge.graph.retry")}
                </button>
              </div>
            ) : documentList.length === 0 ? (
              <div data-testid="sources-empty" className="flex flex-col items-center gap-2 rounded-[var(--radius-surface)] border border-rule bg-card p-8 text-center shadow-card">
                <span className="text-muted">
                  <Icon name="uploadFile" size={28} />
                </span>
                <p className="text-body font-semibold text-foreground">{t("knowledge.sources.empty")}</p>
                <p className="max-w-sm text-meta text-muted">{t("knowledge.sources.emptyNote")}</p>
                <button
                  type="button"
                  data-testid="sources-empty-upload"
                  disabled={uploadBusy}
                  aria-busy={uploadBusy}
                  onClick={() => fileInputRef.current?.click()}
                  className={`mt-1 flex items-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-4 py-2 text-label font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
                >
                  {uploadBusy ? <Spinner /> : <Icon name="uploadFile" size={16} />}
                  {uploadBusy ? t("knowledge.sources.uploadBusy") : t("knowledge.sources.upload")}
                </button>
              </div>
            ) : (
              <div className="overflow-hidden rounded-[var(--radius-surface)] border border-rule bg-card shadow-card">
                <ul className="divide-y divide-rule">
                  {documentList.map((document) => (
                    <li
                      key={document.id}
                      data-testid="sources-document"
                      className="flex flex-col gap-2 p-3 transition-colors hover:bg-surface-container-low/50 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="flex items-start gap-2.5">
                        <span className="mt-0.5 shrink-0 text-primary">
                          <Icon name="document" size={20} />
                        </span>
                        <div className="flex min-w-0 flex-col">
                          <span className="text-label font-semibold text-foreground">{document.title}</span>
                          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-meta text-muted">
                            {document.byte_size !== null && (
                              <>
                                <span>{formatBytes(document.byte_size)}</span>
                                <span aria-hidden="true">·</span>
                              </>
                            )}
                            <span>
                              {t("knowledge.sources.uploadedAt", {
                                date: formatDate(document.created_at, { day: "2-digit", month: "short", year: "numeric" }),
                              })}
                            </span>
                            <span aria-hidden="true">·</span>
                            <span>{t("knowledge.sources.chunkCount", { count: document.chunk_count })}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5 self-end sm:self-center">
                        {/* No endpoint serves the original's bytes — the
                            view door stands an honest disabled gap. */}
                        <button
                          type="button"
                          data-testid="sources-view"
                          disabled
                          title={t("knowledge.sources.viewNote")}
                          className="cursor-not-allowed rounded px-2 py-1 text-meta text-muted opacity-60"
                        >
                          {t("knowledge.sources.view")}
                        </button>
                        <button
                          type="button"
                          id={`source-delete-${document.id}`}
                          data-testid="sources-delete"
                          onClick={() => setDeleting(document)}
                          className={`flex items-center gap-1 rounded px-2 py-1 text-meta font-medium text-danger transition-colors hover:bg-danger/10 ${FOCUS}`}
                        >
                          <Icon name="trash" size={13} /> {t("knowledge.crud.deleteConfirm")}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {/* The draft's two honest gap areas — no endpoint serves either,
              so they stand disabled with the draft's own note, never fake
              content. */}
          <section className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div
              data-testid="sources-footnote-gap"
              aria-disabled="true"
              className="flex flex-col items-center gap-1.5 rounded-[var(--radius-surface)] border border-dashed border-border bg-surface-container-low/50 p-5 text-center opacity-75"
            >
              <span className="text-muted">
                <Icon name="openInNew" size={22} />
              </span>
              <span className="text-label font-semibold text-foreground">{t("knowledge.sources.footnote")}</span>
              <p className="text-meta text-muted">{t("knowledge.sources.laterNote")}</p>
            </div>
            <div
              data-testid="sources-factcheck-gap"
              aria-disabled="true"
              className="flex flex-col items-center gap-1.5 rounded-[var(--radius-surface)] border border-dashed border-border bg-surface-container-low/50 p-5 text-center opacity-75"
            >
              <span className="text-muted">
                <Icon name="balance" size={22} />
              </span>
              <span className="text-label font-semibold text-foreground">{t("knowledge.sources.factCheck")}</span>
              <p className="text-meta text-muted">{t("knowledge.sources.laterNote")}</p>
            </div>
          </section>
        </div>
      </div>

      {/* The destructive confirm — the family's one home, the document's
          own consequence. The deleted row retires its opener; focus lands
          on the page root that survives. */}
      {deleting !== null && (
        <DeleteDocumentDialog
          document={deleting}
          openerId={`source-delete-${deleting.id}`}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
