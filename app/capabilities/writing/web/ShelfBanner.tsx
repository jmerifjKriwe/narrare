/**
 * The activity banner — the `shelf` draft's cadence panel, live on the
 * real aggregate (Task 4's `GET /api/writing/activity`, Task 10's port;
 * W4 Task 9 reads the daily goal, gap row 25). The geometry stands where
 * the draft draws it: the insights tile, the goal line and today's words
 * on the left, the weekly average, the sparkline and the statistics door
 * on the right.
 *
 * Honest readings of the draft (the gap doc records them):
 * - The draft's „Heutiges Schreibziel: 750 Wörter" is the USER's daily
 *   goal — `daily_goal_words`, atelier scope, carried by the aggregate
 *   with the day's progress (row 25's field, Task 8's settings PATCH
 *   stores it). Unset keeps the honest neutral („Noch kein Schreibziel");
 *   the remainder reads the aggregate's own `goal_remaining`, a reached
 *   day speaks the done-state copy. The W3 hero-book pin („Ziel für
 *   ‚…': … / … Wörter") ended here — the banner names no book.
 * - Today's words are the atelier's net across all novels (the aggregate
 *   is atelier-level), so the body names no single book; zero and negative
 *   days speak their own honest voice, unfloored — a negative day owes
 *   the goal plus the removal, the aggregate's own math.
 * - The sparkline is the draft's 120×32 line over the window's thirty
 *   points, zero-days dense; the marked point is TODAY (the draft's dot
 *   sat on its mock curve's peak). The label names the window, the net
 *   and the UTC day boundary — the server's clock, documented on the API.
 * - An all-zero window with no streak is the no-retroactivity neutral
 *   („Der erste Schreibtag beginnt mit dem ersten Kapitel"); the daily
 *   goal still stands, it is the user's truth, not the window's.
 * - The statistics door stays disabled with the drafted note: no
 *   statistics surface exists to open yet.
 *
 * Loading stands in the shelf's skeleton family (the shared Bone), error
 * in the honest retry family — the real failure message, a retry that
 * holds its notice while it asks again (the page's own discipline: a v5
 * refetch clears the error into pending, the flag holds the panel).
 */

import { useRef, useState } from "react";

import type { Activity, ActivityPoint } from "@shell/lib/api/client";
import { useLocalizedError } from "@shell/lib/api/errors";
import { formatNumber } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import { useActivityQuery } from "@shell/lib/query";
import { Icon } from "@shell/ui/icons";

import { activityIsEmpty, goalState, sparkline, todayState } from "./activity";
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

/** The live left block: the atelier's daily goal and the day's own words. */
function BannerLive({ data }: { data: Activity }) {
  const t = useTranslation();
  const empty = activityIsEmpty(data);
  // The goal is the user's stored answer — the aggregate carries it with
  // the day's progress; presence decides the voice, never the progress
  // alone (a null goal owes nothing, whatever the fields beside it say).
  const goal = data.daily_goal_words;
  const state = goalState(data);
  const todayLine = t("writing.shelf.banner.today", {
    state: todayState(data.today_words),
    count: data.today_words,
  });
  const body = empty
    ? t("writing.shelf.banner.body")
    : todayLine +
      (state === "open"
        ? ` ${t("writing.shelf.banner.dailyRemaining", { count: data.goal_remaining })}`
        : "") +
      (state === "met" ? ` ${t("writing.shelf.banner.dailyMet")}` : "");
  return (
    <div>
      <h3 className="text-emph text-foreground">
        {goal !== null ? (
          <>
            <span>{t("writing.shelf.banner.dailyGoal")}</span>
            <span className="tabular-nums">
              {`: ${t("writing.shelf.words.count", { count: goal })}`}
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
  error,
  retrying,
  onRetry,
}: {
  error: unknown;
  retrying: boolean;
  onRetry: () => void;
}) {
  const t = useTranslation();
  const localized = useLocalizedError();
  return (
    <div role="alert" className="flex w-full items-start gap-3">
      <span className="mt-0.5 shrink-0 text-danger">
        <Icon name="warning" size={22} />
      </span>
      <div className="space-y-1">
        <h3 className="text-emph text-foreground">{t("writing.shelf.banner.error.title")}</h3>
        {/* The failure, named in the reader's language. */}
        <p className="font-mono text-meta text-danger">{localized(error)}</p>
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

export function ShelfBanner({ noteId }: { noteId: string }) {
  const t = useTranslation();
  // The banner reads the aggregate on mount; the shelf's write family
  // invalidates the key, so a chapter write moves it without a remount.
  const activity = useActivityQuery();

  // The retry keeps the error notice on screen with a busy button — the
  // page's own discipline: a refetch clears the query's error while it
  // runs, so the banner's flag holds the panel until the answer lands.
  const [retrying, setRetrying] = useState(false);
  const lastError = useRef<unknown>(null);
  if (activity.error) {
    lastError.current = activity.error;
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
          <BannerError error={lastError.current} retrying={retrying} onRetry={retry} />
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
              <BannerLive data={activity.data} />
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
