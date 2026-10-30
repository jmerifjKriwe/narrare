import { Link, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";

import { client, type Novel, type NovelCreate } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { useCreateNovel, useNovelsQuery } from "@shell/lib/query";
import { formatRelative } from "@shell/lib/time";
import { Dialog } from "@shell/ui/Dialog";
import { TextField } from "@shell/ui/TextField";

import { ExportNovelDialog, ImportArchiveDialog } from "./InterchangeDialogs";

/** The start page: a continue-hero over the shelf, and the new-book dialog. */
export function NovelsPage() {
  const t = useTranslation();
  const navigate = useNavigate();
  const novels = useNovelsQuery();
  const createNovel = useCreateNovel();
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [blurb, setBlurb] = useState("");
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const [createFailed, setCreateFailed] = useState(false);
  // The empty Titel is refused by name, not by silence: the failed submit
  // marks the field, and the mark lifts as soon as the field answers it.
  // Derived, not stored, so typing a title can never leave a stale refusal.
  const [triedEmptyTitle, setTriedEmptyTitle] = useState(false);
  const titleInvalid = triedEmptyTitle && title.trim() === "";

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

  // The failure's way back: the gate asks again and the list refetches —
  // one press, not a reload.
  const retryLoad = useCallback(() => {
    void checkGate();
    void novels.refetch();
  }, [checkGate, novels]);

  // The hero's book is the last-touched one — compared as parsed instants,
  // because two ISO strings with different timezone offsets do not order as
  // their moments do. The comparison is strict, so on equal instants the
  // first row of the list wins — and the list arrives newest-created first —
  // which makes the choice deterministic even when two books were touched in
  // the same instant.
  const hero = (novels.data ?? []).reduce<Novel | null>(
    (best, novel) =>
      best === null || Date.parse(novel.updated_at) > Date.parse(best.updated_at) ? novel : best,
    null,
  );

  /** Create a book from trimmed fields; close on success and retain the form on failure. */
  async function create(event: React.FormEvent, close: () => void) {
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
    setTitle("");
    setGenre("");
    setBlurb("");
    setTriedEmptyTitle(false);
    close();
  }

  // The page asks before it shows: a named loading state, never a blank
  // page, and never an empty library that has not heard yet. The wait paints
  // the shelf's own shape — a hero card and rows at the heights the loaded
  // page will claim — so the answer's arrival moves content, not layout.
  // The shapes are decoration (hidden from the accessibility tree); the
  // status line says what the wait is, and stays the screen reader's answer.
  if (!ready || novels.isPending) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-2xl font-semibold tracking-tight">{t("novels.heading")}</h1>
        <div aria-hidden="true" className="mt-6 flex flex-col gap-2">
          <div className="rounded-lg border border-border bg-card px-5 py-4">
            <div className="h-4 w-20 animate-pulse rounded bg-panel" />
            <div className="mt-3 h-6 w-48 animate-pulse rounded bg-panel" />
            <div className="mt-3 h-4 w-32 animate-pulse rounded bg-panel" />
          </div>
          {[0, 1, 2].map((row) => (
            <div
              key={row}
              className="rounded-lg border border-border bg-card px-4 py-3"
            >
              <div className="h-5 w-40 animate-pulse rounded bg-panel" />
              <div className="mt-2 h-3 w-24 animate-pulse rounded bg-panel" />
            </div>
          ))}
        </div>
        <p role="status" className="mt-6 text-sm text-muted">
          {t("novels.loading")}
        </p>
      </div>
    );
  }

  const failedNow = failed || novels.isError;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t("novels.heading")}</h1>
        {!failedNow && (
          <div className="flex items-center gap-2">
            <ImportArchiveDialog novels={novels.data ?? []} />
            <Dialog title={t("novels.new")} triggerLabel={t("novels.createBook")}>
              {(close) => (
                <form
                  onSubmit={(event) => void create(event, close)}
                  className="mt-4 flex flex-col gap-3"
                >
                  <TextField
                    label={t("novels.titleLabel")}
                    value={title}
                    onChange={setTitle}
                    isInvalid={titleInvalid}
                    validationMessage={titleInvalid ? t("novels.titleRequired") : undefined}
                  />
                  <TextField label={t("novels.genre")} value={genre} onChange={setGenre} />
                  <TextField label={t("novels.blurb")} value={blurb} onChange={setBlurb} multiline />
                  {createFailed ? (
                    <p role="alert" className="text-sm text-danger">
                      {t("novels.errorCreate")}
                    </p>
                  ) : null}
                  <button
                    type="submit"
                    className="self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    {t("novels.create")}
                  </button>
                </form>
              )}
            </Dialog>
          </div>
        )}
      </div>
      {failedNow ? (
        <div className="mt-6">
          <p role="alert" className="text-sm text-danger">
            {t("novels.errorLoad")}
          </p>
          {/* The way back is one press: the gate asks again and the list
              refetches, no reload demanded. */}
          <button
            type="button"
            onClick={retryLoad}
            className="mt-3 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel"
          >
            {t("novels.retry")}
          </button>
        </div>
      ) : (
        <>
          {hero && (
            <section
              aria-labelledby="novels-continue"
              className="mt-6 rounded-lg border border-border bg-card px-5 py-4"
            >
              <h2 id="novels-continue" className="text-sm font-medium text-muted">
                {t("novels.continue")}
              </h2>
              {/* The title stays text: the shelf card is this book's link, and
                  a second identically-named link would make "open the book"
                  ambiguous for a keyboard and a screen reader alike. */}
              <p className="mt-1 text-lg font-semibold">{hero.title}</p>
              <p className="mt-1 text-sm text-muted">
                {t("novels.lastTouched", { time: formatRelative(hero.updated_at) })}
              </p>
              <Link
                to="/novels/$id"
                params={{ id: hero.id }}
                className="mt-2 inline-block rounded-md text-sm underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                {t("chapters.continue")}
              </Link>
            </section>
          )}
          <ul className="mt-6 flex flex-col gap-2">
            {(novels.data ?? []).map((novel) => (
              <li key={novel.id} className="flex items-stretch justify-between gap-2 rounded-lg border border-border bg-card">
                <Link
                  to="/novels/$id"
                  params={{ id: novel.id }}
                  className="block flex-1 rounded-md px-4 py-3 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  <span className="font-medium">{novel.title}</span>
                  {novel.genre && (
                    <span className="mt-1 block text-sm text-muted">{novel.genre}</span>
                  )}
                  <span className="mt-1 block text-xs text-muted">
                    {t("novels.lastTouched", { time: formatRelative(novel.updated_at) })}
                  </span>
                </Link>
                <div className="flex items-center pr-4">
                  <ExportNovelDialog novel={novel} />
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
