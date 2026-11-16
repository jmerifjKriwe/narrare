/**
 * The activity banner — the `shelf` draft's cadence panel, live on the
 * real aggregate (Task 4's `GET /api/writing/activity`, Task 10's port).
 * The geometry stands where the draft draws it: the insights tile, the
 * goal line and today's words on the left, the weekly average, the
 * sparkline and the statistics door on the right.
 *
 * Honest readings of the draft (the gap doc records them):
 * - The draft's „Heutiges Schreibziel: 750 Wörter" is a daily goal no row
 *   carries. The goal the banner tracks is the ACTIVE BOOK's — the hero
 *   novel's own `word_count / target_words` (the plan's pin), named by the
 *   book's title; a missing target keeps the shelf's dash, never an
 *   invented number. The draft's remainder sentence rides the book goal.
 * - Today's words are the atelier's net across all novels (the aggregate
 *   is atelier-level), so the body names no single book; zero and negative
 *   days speak their own honest voice, unfloored.
 * - The sparkline is the draft's 120×32 line over the window's thirty
 *   points, zero-days dense; the marked point is TODAY (the draft's dot
 *   sat on its mock curve's peak). The label names the window, the net
 *   and the UTC day boundary — the server's clock, documented on the API.
 * - An all-zero window with no streak is the no-retroactivity neutral
 *   („Der erste Schreibtag beginnt mit dem ersten Kapitel"); the book's
 *   goal still stands, it is the book's truth, not the window's.
 * - The statistics door stays disabled with the drafted note: no
 *   statistics surface exists to open yet.
 *
 * Loading stands in the shelf's skeleton family (the shared Bone), error
 * in the honest retry family — the real failure message, a retry that
 * holds its notice while it asks again (the page's own discipline: a v5
 * refetch clears the error into pending, the flag holds the panel).
 */

import { useRef, useState } from "react";

import type { Activity, ActivityPoint, Novel } from "@shell/lib/api/client";
import { formatNumber } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import { useActivityQuery } from "@shell/lib/query";
import { Icon } from "@shell/ui/icons";

import { activityIsEmpty, sparkline, todayState } from "./activity";
import { progress } from "./shelf";
import { Bone } from "./ShelfStates";

/** The shell's focus ring on the one control the error state offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The drafted line over the window's points — the pure helper's geometry,
 *  the tokens' ink: the area-writing stroke, the primary dot on today. */
function Sparkline({ points }: { points: readonly ActivityPoint[] }) {
  const t = useTranslation();
  const shape = sparkline(points);
  if (shape === null) return null;
  return (
    <svg
      role="img"
      aria-label={t("writing.shelf.banner.sparkline", { days: points.length })}
      className="overflow-visible text-area-writing"
      width={120}
      height={32}
      viewBox="0 0 120 32"
    >
      <path
        d={shape.d}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle className="fill-current text-primary" cx={shape.today.x} cy={shape.today.y} r={3} />
    </svg>
  );
}

/** The live left block: the hero's goal line and the day's own words. */
function BannerLive({ data, hero }: { data: Activity; hero: Novel | null }) {
  const t = useTranslation();
  const empty = activityIsEmpty(data);
  // The goal is the hero book's own pair — the progress rule's presence
  // check (a zero or negative target is no target), never the atelier sum.
  const hasGoal = hero !== null && progress(hero.word_count, hero.target_words) !== null;
  const remaining = hasGoal
    ? Math.max(0, (hero?.target_words ?? 0) - (hero?.word_count ?? 0))
    : 0;
  const todayLine = t("writing.shelf.banner.today", {
    state: todayState(data.today_words),
    count: data.today_words,
  });
  const body = empty
    ? t("writing.shelf.banner.body")
    : todayLine +
      (hasGoal && remaining > 0
        ? ` ${t("writing.shelf.banner.remaining", { count: remaining })}`
        : "") +
      (hero !== null && !hasGoal ? ` ${t("writing.shelf.noTarget")}` : "");
  return (
    <div>
      <h3 className="text-emph text-foreground">
        {hero !== null ? (
          <>
            <span>{t("writing.shelf.banner.goal", { title: hero.title })}</span>
            <span className="tabular-nums">
              {hasGoal
                ? `: ${t("writing.shelf.words.pair", { count: hero.word_count, target: hero.target_words ?? 0 })}`
                : ": —"}
            </span>
          </>
        ) : (
          <span>{t("writing.shelf.banner.noGoal")}</span>
        )}
      </h3>
      <p className="text-meta text-muted">{body}</p>
    </div>
  );
}

/** The error face — the retry family's compact form: the real failure,
 *  the loss-free line, and a retry that actually asks again. */
function BannerError({
  message,
  retrying,
  onRetry,
}: {
  message: string;
  retrying: boolean;
  onRetry: () => void;
}) {
  const t = useTranslation();
  return (
    <div role="alert" className="flex w-full items-start gap-3">
      <span className="mt-0.5 shrink-0 text-danger">
        <Icon name="warning" size={22} />
      </span>
      <div className="space-y-1">
        <h3 className="text-emph text-foreground">{t("writing.shelf.banner.error.title")}</h3>
        {/* The real failure — the query's own message, status included. */}
        <p className="font-mono text-meta text-danger">{message}</p>
        <p className="text-meta text-muted">{t("writing.shelf.banner.error.body")}</p>
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className={`mt-1 inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-surface-container-lowest px-3.5 py-2 text-label font-semibold text-foreground shadow-sm transition-all hover:border-primary active:scale-[0.98] ${FOCUS} ${retrying ? "cursor-not-allowed opacity-50" : ""}`}
        >
          <span className="text-primary">
            <Icon name="refresh" size={14} />
          </span>
          {retrying ? t("writing.shelf.error.retrying") : t("writing.shelf.error.retry")}
        </button>
      </div>
    </div>
  );
}

export function ShelfBanner({ hero, noteId }: { hero: Novel | null; noteId: string }) {
  const t = useTranslation();
  // The banner reads the aggregate on mount; the shelf's write family
  // invalidates the key, so a chapter write moves it without a remount.
  const activity = useActivityQuery();

  // The retry keeps the error notice on screen with a busy button — the
  // page's own discipline: a refetch clears the query's error while it
  // runs, so the banner's flag holds the panel until the answer lands.
  const [retrying, setRetrying] = useState(false);
  const lastError = useRef("");
  if (activity.error) {
    lastError.current =
      activity.error instanceof Error ? activity.error.message : String(activity.error);
  }
  function retry() {
    setRetrying(true);
    void activity.refetch().finally(() => setRetrying(false));
  }
  const showLoading = activity.isPending && !retrying;
  const showError = (activity.isError || retrying) && !activity.isSuccess;

  return (
    <section className="rounded-xl border border-border bg-surface p-4 shadow-sm lg:p-6">
      <div className="flex flex-col items-center justify-between gap-4 lg:flex-row">
        {showError ? (
          <BannerError message={lastError.current} retrying={retrying} onRetry={retry} />
        ) : (
          <div className="flex items-center gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-container-high text-primary">
              <Icon name="insights" size={22} />
            </div>
            {showLoading || activity.data === undefined ? (
              <div className="space-y-2">
                <Bone className="h-5 w-64 max-w-full" />
                <Bone className="h-4 w-80 max-w-full" />
              </div>
            ) : (
              <BannerLive data={activity.data} hero={hero} />
            )}
          </div>
        )}
        <div className="flex w-full items-center justify-end gap-4 lg:w-auto">
          <div className="hidden flex-col items-end sm:flex">
            <span className="text-eyebrow uppercase text-muted">{t("writing.shelf.banner.weekly")}</span>
            {showLoading ? (
              <Bone className="mt-0.5 h-4 w-16" />
            ) : showError || activity.data === undefined ? (
              <span className="text-emph tabular-nums text-muted">—</span>
            ) : (
              <span className="text-emph tabular-nums text-foreground">
                {t("writing.shelf.banner.average", {
                  value: formatNumber(activity.data.weekly_average, {
                    minimumFractionDigits: 1,
                    maximumFractionDigits: 1,
                  }),
                })}
              </span>
            )}
          </div>
          {showLoading ? (
            <Bone className="h-8 w-[120px]" />
          ) : !showError && activity.data !== undefined ? (
            <Sparkline points={activity.data.points} />
          ) : null}
          {/* No statistics surface exists to open yet — the door stays
              honestly disabled with the drafted note. */}
          <button
            type="button"
            disabled
            aria-describedby={noteId}
            className="h-8 shrink-0 cursor-not-allowed rounded-lg bg-surface-container px-3 text-label text-foreground opacity-50"
          >
            {t("writing.shelf.banner.stats")}
          </button>
        </div>
      </div>
      <p id={noteId} className="mt-2 text-meta text-muted">
        {t("writing.shelf.comingSoon")}
      </p>
    </section>
  );
}
