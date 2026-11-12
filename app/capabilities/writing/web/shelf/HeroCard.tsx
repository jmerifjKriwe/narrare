import { Link } from "@tanstack/react-router";

import { useTranslation } from "@shell/lib/i18n";
import { formatNumber } from "@shell/lib/format";
import { formatRelative } from "@shell/lib/time";
import { buttonClass } from "@shell/ui/Button";
import { Cover } from "@shell/ui/Cover";
import { Icon } from "@shell/ui/icons";
import type { Novel } from "@shell/lib/api/client";

/**
 * The hero card (`screens/library/shelf.html`, "Aktuell in Arbeit"): the
 * last-touched book as the shelf's one continue-target — its cover, the
 * sync pill row, the title with its series line, the blurb in the brand
 * serif, the metadata row in tabular figures, and the two doors: the
 * primary "Weiterschreiben in Kapitel n" and the secondary outline door.
 *
 * Every fact is the row's own (spec §6.6): the sync line is the real
 * last-touch time, the words and chapters are the row's counts. What the
 * draft shows that no field backs is hidden, not faked, and named for the
 * follow-up where it hides.
 */

export function HeroCard({ novel }: { novel: Novel }) {
  const t = useTranslation();
  return (
    <section
      aria-label={t("shelf.hero.active")}
      className="relative overflow-hidden rounded-[var(--radius-surface)] bg-surface-container-low shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-col items-center gap-8 p-6 md:flex-row lg:p-8">
        <div className="shrink-0 rounded-[var(--radius)] shadow-[var(--shadow-card)] transition-transform duration-300 hover:-translate-y-1">
          <Cover title={novel.title} size="hero" genre={novel.genre} language={novel.language} />
        </div>
        <div className="flex w-full min-w-0 flex-1 flex-col justify-between gap-4">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-secondary-container px-2 py-0.5 text-eyebrow uppercase text-secondary-container-foreground">
                {t("shelf.hero.active")}
              </span>
              {/* Real data: the row's own last-touch time is the honest
               * sync truth — the app is local, and this stamp is what the
               * autosave last wrote (§6.6, "derived"). */}
              <span className="flex items-center gap-1 text-meta text-success">
                <span
                  className="h-1.5 w-1.5 rounded-full bg-success motion-safe:animate-pulse"
                  aria-hidden="true"
                />
                {t("shelf.hero.synced", { time: formatRelative(novel.updated_at) })}
              </span>
            </div>
            <div className="flex flex-wrap items-baseline gap-3">
              <h2 className="text-[26px] leading-[34px] font-semibold text-foreground [font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif]">
                {novel.title}
              </h2>
              {/* Interim: no series or band field exists; the genre is the
               * one honest line the row carries, and no line at all when
               * the book carries none.
               * Missing data: series/band metadata.
               * Follow-up: render the series line (index issue at Task 11). */}
              {novel.genre ? (
                <span className="text-label text-muted">{novel.genre}</span>
              ) : null}
            </div>
            {novel.blurb ? (
              <p className="mt-3 line-clamp-3 max-w-2xl text-[18px] leading-[31.5px] text-muted [font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif]">
                {novel.blurb}
              </p>
            ) : null}
          </div>
          <div className="space-y-3 pt-2">
            <div className="flex flex-wrap items-center gap-6 text-foreground">
              <div className="flex items-center gap-1.5">
                <span className="text-area-writing" aria-hidden="true">
                  <Icon name="inkHighlighter" />
                </span>
                <span className="text-emph tabular-nums">{formatNumber(novel.word_count)}</span>
                <span className="text-meta text-muted">
                  {t("shelf.wordsUnit", { count: novel.word_count })}
                </span>
              </div>
              {/* Interim: no per-book target exists, so the drafted
               * "x / 60.000 Wörter" pair and the hero's tiny progress bar
               * are absent — a target the app never earned is never
               * implied. The word count above is the row's real one.
               * Missing data: per-book word target.
               * Follow-up: render the target pair and the bar (index issue
               * at Task 11). */}
              <div className="flex items-center gap-1.5">
                <span className="text-outline" aria-hidden="true">
                  <Icon name="menuBook" />
                </span>
                <span className="text-emph tabular-nums">{formatNumber(novel.chapter_count)}</span>
                <span className="text-meta text-muted">
                  {t("shelf.chaptersUnit", { count: novel.chapter_count })}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-outline" aria-hidden="true">
                  <Icon name="clock" />
                </span>
                <span className="text-meta text-muted">
                  {t("novels.lastTouched", { time: formatRelative(novel.updated_at) })}
                </span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                to="/novels/$id"
                params={{ id: novel.id }}
                className={`${buttonClass("primary", "lg")} inline-flex items-center gap-2 no-underline`}
              >
                <Icon name="editNote" />
                {/* Real derivation: the last chapter's number is the row's
                 * chapter count — the chapter a continue lands in. A book
                 * without chapters keeps the plain word. */}
                {novel.chapter_count > 0
                  ? t("shelf.hero.continueChapter", { n: novel.chapter_count })
                  : t("chapters.continue")}
              </Link>
              {/* Interim: no outline route exists — the workspace's
               * planning dock is where the outline lives, so the drafted
               * second door opens the book itself until a dedicated route
               * does.
               * Missing data: the outline & scenes route.
               * Follow-up: point this door at it (index issue at Task 11). */}
              <Link
                to="/novels/$id"
                params={{ id: novel.id }}
                className={`${buttonClass("secondary", "lg")} inline-flex items-center gap-2 no-underline`}
              >
                <Icon name="schema" />
                {t("shelf.hero.outline")}
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
