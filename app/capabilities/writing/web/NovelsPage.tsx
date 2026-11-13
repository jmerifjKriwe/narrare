import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { client, type Novel } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import {
  useNovelsQuery,
  takeNovelDeletedElsewhere,
} from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Notice } from "@shell/ui/Notice";

import { ImportArchiveDialog } from "./InterchangeDialogs";
import { ActivityBanner } from "./shelf/ActivityBanner";
import { BookCard } from "./shelf/BookCard";
import { BookList } from "./shelf/BookList";
import { EmptyShelf } from "./shelf/EmptyShelf";
import { HeroCard } from "./shelf/HeroCard";
import { NewBookForm } from "./shelf/NovelDialogs";
import { ShelfHeader } from "./shelf/ShelfHeader";
import { ShelfLoadingNotice, ShelfSkeleton } from "./shelf/ShelfSkeleton";
import { ShelfToolbar, type ShelfView } from "./shelf/ShelfToolbar";

/**
 * The start page, recomposed 1:1 against `screens/library/shelf.html`
 * (spec §6.6): the header with its metrics, the hero over the last-touched
 * book, the search/filter/view row, the grid or the dense rows, and the
 * activity banner — every drafted element standing, every field the app
 * does not carry rendering its interim neutral beside its follow-up.
 *
 * The page's own state is the drafted row's (§6.6 "pure client state"):
 * the search text, the genre filter and the view. The setup gate, the
 * outage voices and the deleted-elsewhere note keep the contracts they
 * already had — the gate decides whether there is a library at all, and
 * the failures speak beside the books that stand.
 */

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
  // The drafted row's three client states (§6.6).
  const [search, setSearch] = useState("");
  const [genre, setGenre] = useState<string | null>(null);
  const [view, setView] = useState<ShelfView>("grid");
  // The one-shot note from the workspace's 404 degrade: the book this
  // shelf's card opened was deleted elsewhere, and the shelf says so once,
  // on the mount the degrade lands on — the note dies with the showing, so
  // it can never outlive the event it names.
  const [deletedElsewhere] = useState(takeNovelDeletedElsewhere);

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

  // The view is the drafted row's own state (§6.6: pure client state): the
  // grid is the drafted default, the dense rows are the toggle's second
  // view. The shelf never switches for itself — no draft shows it choosing.
  const chooseView = useCallback((next: ShelfView) => {
    setView(next);
  }, []);

  // The filter row's own derivations: the genres the shelf carries, and
  // the titles the search matches. Titles only — figures and tags join
  // when their search index does (the row's own follow-up).
  const genres = [...new Set(list.map((novel) => novel.genre).filter((g): g is string => g !== null))];
  const needle = search.trim().toLowerCase();
  const filtered = list.filter(
    (novel) =>
      (genre === null || novel.genre === genre) &&
      (needle === "" || novel.title.toLowerCase().includes(needle)),
  );
  const visible = filtered.filter((novel) => novel.id !== hero?.id);

  // The page asks before it shows: a named loading state, never a blank
  // page, and never an empty library that has not heard yet. The wait
  // paints the shelf's own shape (the states screen's panel 1), so the
  // answer's arrival moves content, not layout.
  if (!ready || novels.isPending) {
    return (
      <div className="mx-auto w-full max-w-7xl px-4 py-6 lg:px-8">
        <h1 className="text-title font-semibold tracking-tight">{t("shelf.title")}</h1>
        <div className="mt-6">
          <ShelfSkeleton />
        </div>
        <ShelfLoadingNotice />
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

  // The way back: the gate asks again and the list refetches — one press,
  // not a reload.
  const retryButton = (
    <Button variant="secondary" onClick={retry}>
      {t("novels.retry")}
    </Button>
  );

  return (
    <div className="mx-auto w-full max-w-7xl space-y-8 px-4 py-6 lg:px-8">
      {deletedElsewhere ? (
        // The quiet voice, the degrade's own words: nothing here asks the
        // user to fix anything, so the note is status speech — the shelf
        // stands, the book that left is named, and the next press is
        // wherever the user was going.
        <Notice tone="quiet" live="status">
          {t("novels.deleteElsewhere")}
        </Notice>
      ) : null}
      {outage ? (
        // The outage is the page (the drafted error card, states screen
        // panel 2): named where the way back is, one alert, one press.
        // No header stands over it — a first load that failed has no
        // count to show, and "0 Romane" would claim an empty library the
        // shelf has not heard about.
        <Notice tone="danger" live="alert" action={retryButton}>
          {t("novels.errorLoad")}
        </Notice>
      ) : (
        <>
          <ShelfHeader
            count={list.length}
            totalWords={list.reduce((sum, novel) => sum + novel.word_count, 0)}
            empty={empty}
            onCreate={() => setCreateOpen(true)}
            onImport={() => setImportOpen(true)}
          />
          {empty ? (
            <EmptyShelf
              onCreate={() => setCreateOpen(true)}
              onImport={() => setImportOpen(true)}
            />
          ) : (
            <>
              {refreshFailed ? (
                // The books stand; the refresh that failed says so politely
                // above them — the shelf is the last good answer, never torn
                // down for it. The retry re-asks the gate beside the list:
                // the gate's failure holds this note as much as the list's,
                // so one press must be able to retire both.
                <Notice tone="quiet" live="status" action={retryButton}>
                  {t("novels.refreshFailed")}
                </Notice>
              ) : null}
              {hero ? <HeroCard key={hero.id} novel={hero} /> : null}
              <div className="space-y-4">
                <ShelfToolbar
                  search={search}
                  onSearch={setSearch}
                  genres={genres}
                  genre={genre}
                  onGenre={setGenre}
                  view={view}
                  onView={chooseView}
                />
                {view === "grid" ? (
                  <ul className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                    {visible.map((novel) => (
                      <BookCard key={novel.id} novel={novel} />
                    ))}
                  </ul>
                ) : (
                  <BookList novels={filtered} />
                )}
              </div>
            </>
          )}
          <ActivityBanner empty={empty} />
        </>
      )}
      <Dialog title={t("novels.new")} isOpen={createOpen} onOpenChange={setCreateOpen}>
        {(close) => <NewBookForm close={close} />}
      </Dialog>
      <ImportArchiveDialog novels={list} isOpen={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}
