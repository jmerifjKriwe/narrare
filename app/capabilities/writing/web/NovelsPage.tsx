import { Link, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";

import { Button, buttonClass } from "@shell/ui/Button";
import { Cover } from "@shell/ui/Cover";
import { client, type Novel, type NovelCreate } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useCreateNovel, useNovelsQuery } from "@shell/lib/query";
import { formatRelative } from "@shell/lib/time";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Input, Textarea } from "@shell/ui/field";
import { Icon } from "@shell/ui/icons";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

import { ExportNovelDialog, ImportArchiveDialog } from "./InterchangeDialogs";

/**
 * The new-book dialog's form, with its own state: the fields, the empty
 * title's refusal and the create's failure all live and die with one
 * mounting — the dialog mounts its content fresh on every open, so nothing
 * here can outlive the dialog it belongs to. The empty Titel is refused by
 * name, not by silence: the failed submit marks the field, and the mark
 * lifts as soon as the field answers it. Derived, not stored, so typing a
 * title can never leave a stale refusal.
 */
function NewBookForm({ close }: { close: () => void }) {
  const t = useTranslation();
  const createNovel = useCreateNovel();
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [blurb, setBlurb] = useState("");
  const [createFailed, setCreateFailed] = useState(false);
  const [triedEmptyTitle, setTriedEmptyTitle] = useState(false);
  const titleInvalid = triedEmptyTitle && title.trim() === "";

  /** Create a book from trimmed fields; close on success and retain the form on failure. */
  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (title.trim() === "") {
      setTriedEmptyTitle(true);
      return;
    }
    setCreateFailed(false);
    // Only fields the user filled reach the row: an empty genre is no genre,
    // not a genre called "".
    const input: NovelCreate = { title: title.trim() };
    if (genre.trim() !== "") input.genre = genre.trim();
    if (blurb.trim() !== "") input.blurb = blurb.trim();
    try {
      // The list refreshes through the ["novels"] invalidation, not through
      // a reload here: the mutation owns that side of the contract.
      await createNovel.mutateAsync(input);
    } catch {
      // The dialog stays open: the typed values are the user's work, and
      // the failure is this create's own — named inside the dialog, where
      // the retry is one press away, not on a page behind it.
      setCreateFailed(true);
      return;
    }
    close();
  }

  return (
    <form onSubmit={(event) => void create(event)} className="mt-4 flex flex-col gap-3">
      <Field
        label={t("novels.titleLabel")}
        error={titleInvalid ? t("novels.titleRequired") : undefined}
      >
        <Input value={title} onChange={(event) => setTitle(event.target.value)} />
      </Field>
      <Field label={t("novels.genre")}>
        <Input value={genre} onChange={(event) => setGenre(event.target.value)} />
      </Field>
      <Field label={t("novels.blurb")}>
        <Textarea
          value={blurb}
          onChange={(event) => setBlurb(event.target.value)}
          rows={3}
        />
      </Field>
      {createFailed ? (
        <Notice tone="danger" live="alert">
          {t("novels.errorCreate")}
        </Notice>
      ) : null}
      <Button type="submit" variant="primary" className="self-start">
        {t("novels.create")}
      </Button>
    </form>
  );
}

/** The shelf card: the book's face and its facts in one press target. The
 *  whole card is the link — a second identically-named link inside it would
 *  make "open the book" ambiguous for a keyboard and a screen reader alike —
 *  so the cover is aria-hidden inside it and the title stays text. The
 *  title's box is three lines tall whether the title fills them or not,
 *  which is what keeps an 80-character Titel from blowing up the shelf: it
 *  clamps, it breaks the one word that cannot wrap, and the slot is three
 *  lines tall whether the title fills it or not — measured on the span,
 *  because the grid would stretch the cards to equality either way. The
 *  title row keeps a fixed gutter under the export button (`pr-7`), so a
 *  long first line runs under nothing. The hover wears the `--soft` wash,
 *  and the wash restores foreground to the muted facts (the parked AA
 *  rule: no text-muted on a `--soft` fill) — the same contract the ghost
 *  button carries. */
function ShelfCard({ novel }: { novel: Novel }) {
  const t = useTranslation();
  return (
    <li className="relative flex">
      <Link
        to="/novels/$id"
        params={{ id: novel.id }}
        className="group flex flex-1 flex-col rounded-[var(--radius-lg)] border border-border bg-card p-3 no-underline underline-offset-4 hover:bg-soft hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        <div className="flex items-start gap-3 pr-7">
          <Cover title={novel.title} />
          <span
            data-shelf-title
            className="line-clamp-3 min-h-[3.9em] min-w-0 flex-1 break-words text-title font-semibold leading-[1.3]"
          >
            {novel.title}
          </span>
        </div>
        {novel.genre ? (
          <span className="mt-2 text-label text-muted group-hover:text-foreground">
            {novel.genre}
          </span>
        ) : null}
        {novel.language ? (
          <span className="mt-0.5 text-label text-muted group-hover:text-foreground">
            {novel.language}
          </span>
        ) : null}
        <span className="mt-1 text-meta text-muted group-hover:text-foreground">
          {t("shelf.export.doneChapters", { count: novel.chapter_count })}
          {" · "}
          {t("shelf.card.words", { count: novel.word_count })}
        </span>
        <span className="mt-0.5 text-meta text-muted group-hover:text-foreground">
          {t("novels.lastTouched", { time: formatRelative(novel.updated_at) })}
        </span>
      </Link>
      <div className="absolute right-1.5 top-1.5">
        <ExportNovelDialog novel={novel} />
      </div>
    </li>
  );
}

/** The start page: a continue-hero over the shelf, and the new-book dialog. */
export function NovelsPage() {
  const t = useTranslation();
  const navigate = useNavigate();
  const novels = useNovelsQuery();
  // The tab's name and the bar's place: this page is "Romane" until it goes.
  usePageTitle(t("novels.heading"));
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  // The setup gate decides whether there is a library to list at all. Only
  // the novels themselves go through the query cache; this check cannot,
  // because its answer is "go somewhere else", not data. A callable, not
  // just an effect: the failure's retry button runs the same question
  // again instead of demanding a reload.
  const checkGate = useCallback(async () => {
    try {
      const status = await client.GET("/api/setup/status");
      if (!status.response.ok) {
        // An answer that is not "ok" means no usable state. Showing an empty
        // list here would claim the instance holds nothing; say what failed.
        setFailed(true);
      } else if (status.data && !status.data.complete) {
        // Nothing to list yet: an uninstalled instance starts at setup.
        void navigate({ to: "/setup", replace: true });
        return;
      } else {
        setFailed(false);
      }
    } catch {
      // The local service is not answering at all and the proxy refuses.
      setFailed(true);
    }
    setReady(true);
  }, [navigate]);

  useEffect(() => {
    void checkGate();
  }, [checkGate]);

  // The way back for both voices: the gate is the outage's question, and
  // the quiet note answers it beside the list — a dead gate holds the note
  // over standing books exactly as a refused refresh does, so the one
  // retry must retire both causes or the note outlives the failure the
  // service already recovered from. One press, not a reload.
  const retry = useCallback(() => {
    void checkGate();
    void novels.refetch();
  }, [checkGate, novels]);

  // The hero's book is the last-touched one — compared as parsed instants,
  // because two ISO strings with different timezone offsets do not order as
  // their moments do. The comparison is strict, so on equal instants the
  // first row of the list wins — and the list arrives newest-created first —
  // which makes the choice deterministic even when two books were touched in
  // the same instant.
  const list = novels.data ?? [];
  const hero = list.reduce<Novel | null>(
    (best, novel) =>
      best === null || Date.parse(novel.updated_at) > Date.parse(best.updated_at) ? novel : best,
    null,
  );
  const empty = list.length === 0;

  // The one way in, wherever the shelf is: in the header while books stand,
  // as the empty state's action while none do — never both at once, so
  // "Neues Buch" names exactly one button either way.
  const createTrigger = (
    <Button
      variant="primary"
      icon={<Icon name="plus" />}
      onClick={() => setCreateOpen(true)}
    >
      {t("novels.createBook")}
    </Button>
  );

  // The page asks before it shows: a named loading state, never a blank
  // page, and never an empty library that has not heard yet. The wait paints
  // the shelf's own shape — a hero card and three shelf cards at the sizes
  // the loaded page will claim — so the answer's arrival moves content, not
  // layout. The shapes are decoration (hidden from the accessibility tree)
  // and their fill is `--rule`; the pulse rides `motion-safe:`, so
  // prefers-reduced-motion: reduce stops it (F24). The status line says
  // what the wait is, and stays the screen reader's answer.
  if (!ready || novels.isPending) {
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-10">
        <h1 className="text-title font-semibold tracking-tight">{t("novels.heading")}</h1>
        <div aria-hidden="true" className="mt-6 flex flex-col gap-3">
          <div className="flex items-center gap-4 rounded-[var(--radius-lg)] border border-border bg-card p-4">
            <div className="aspect-[3/4] w-28 shrink-0 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
            <div className="flex flex-1 flex-col gap-2">
              <div className="h-5 w-48 motion-safe:animate-pulse rounded bg-rule" />
              <div className="h-3 w-32 motion-safe:animate-pulse rounded bg-rule" />
              <div className="h-3 w-24 motion-safe:animate-pulse rounded bg-rule" />
            </div>
          </div>
          {[0, 1, 2].map((row) => (
            <div
              key={row}
              className="flex gap-3 rounded-[var(--radius-lg)] border border-border bg-card p-3"
            >
              <div className="aspect-[3/4] w-20 shrink-0 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
              <div className="flex flex-1 flex-col gap-2 py-1">
                <div className="h-4 w-2/3 motion-safe:animate-pulse rounded bg-rule" />
                <div className="h-3 w-1/3 motion-safe:animate-pulse rounded bg-rule" />
                <div className="h-3 w-1/4 motion-safe:animate-pulse rounded bg-rule" />
              </div>
            </div>
          ))}
        </div>
        <Notice tone="quiet" live="status" className="mt-6">
          {t("novels.loading")}
        </Notice>
      </div>
    );
  }

  // The two failures wear different voices (§8.8), and the cache decides
  // which one speaks — a dead gate never outranks the books it sits above.
  // With nothing to show — the gate dead, or the first load failed — the
  // outage is the page and speaks in the danger voice. With books standing,
  // the same failures only mark the shown truth as stale: a quiet, polite
  // line above the shelf the books are still on.
  const outage = (failed || novels.isError) && empty;
  const refreshFailed = (failed || novels.isError) && !empty;

  // The failure's way back: the gate asks again and the list refetches —
  // one press, not a reload.
  const retryButton = (
    <Button variant="secondary" onClick={retry}>
      {t("novels.retry")}
    </Button>
  );

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-title font-semibold tracking-tight">{t("novels.heading")}</h1>
        {!outage && (
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              icon={<Icon name="import" />}
              onClick={() => setImportOpen(true)}
            >
              {t("shelf.import")}
            </Button>
            {!empty && createTrigger}
          </div>
        )}
      </div>
      {outage ? (
        // The outage is named where the way back is: one alert, one press.
        <Notice tone="danger" live="alert" className="mt-6" action={retryButton}>
          {t("novels.errorLoad")}
        </Notice>
      ) : empty ? (
        // The empty library is quiet, not dead: it names itself and carries
        // the one way in.
        <Notice tone="quiet" className="mt-6" action={createTrigger}>
          {t("novels.empty")}
        </Notice>
      ) : (
        <>
          {refreshFailed ? (
            // The books stand; the refresh that failed says so politely
            // above them — the shelf is the last good answer, never torn
            // down for it. The retry re-asks the gate beside the list:
            // the gate's failure holds this note as much as the list's,
            // so one press must be able to retire both.
            <Notice
              tone="quiet"
              live="status"
              className="mt-6"
              action={
                <Button variant="secondary" onClick={retry}>
                  {t("novels.retry")}
                </Button>
              }
            >
              {t("novels.refreshFailed")}
            </Notice>
          ) : null}
          {hero && (
            <section aria-labelledby="novels-continue" className="mt-6">
              <Panel>
                <h2 className="text-label uppercase tracking-[0.1em] text-muted" id="novels-continue">
                  {t("novels.continue")}
                </h2>
                <div className="mt-3 flex items-center gap-4">
                  <Cover title={hero.title} size="lg" />
                  <div className="min-w-0 flex-1">
                    <p className="text-emph font-semibold">{hero.title}</p>
                    {hero.genre ? (
                      <p className="mt-0.5 text-label text-muted">{hero.genre}</p>
                    ) : null}
                    {hero.language ? (
                      <p className="mt-0.5 text-label text-muted">{hero.language}</p>
                    ) : null}
                    <p className="mt-0.5 text-meta text-muted">
                      {t("novels.lastTouched", { time: formatRelative(hero.updated_at) })}
                    </p>
                  </div>
                  <Link
                    to="/novels/$id"
                    params={{ id: hero.id }}
                    className={`${buttonClass("secondary", "md")} inline-flex items-center justify-center no-underline`}
                  >
                    {t("chapters.continue")}
                  </Link>
                </div>
              </Panel>
            </section>
          )}
          <ul className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((novel) => (
              <ShelfCard key={novel.id} novel={novel} />
            ))}
          </ul>
        </>
      )}
      <Dialog title={t("novels.new")} isOpen={createOpen} onOpenChange={setCreateOpen}>
        {(close) => <NewBookForm close={close} />}
      </Dialog>
      <ImportArchiveDialog
        novels={list}
        isOpen={importOpen}
        onOpenChange={setImportOpen}
      />
    </div>
  );
}
