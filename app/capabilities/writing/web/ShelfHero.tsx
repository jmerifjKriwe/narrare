/**
 * The hero card — the `shelf` draft's „Aktuell in Arbeit" panel: the
 * latest-edited novel's cover at `hero` size, its title and series line
 * (or genre when it stands alone), the blurb when the row carries one,
 * the word pair in tabular figures with the drafted progress, the chapter
 * count and the localized last-edited stamp, and the two doors.
 *
 * The quick menu (#863, the `shelf-hero-menu` draft) is the grid cards'
 * own surface, mounted in the header row beside the status badge: the same
 * 28px trigger, the same w-64 popover with the three actions and the meta
 * line, the same confirm/busy/error discipline. The hero never shows an
 * archived book (pickHero), so no Wiederherstellen variant stands here;
 * archiving the hero re-picks the next active book through the shelf's own
 * refetch — honest, no special case. The section carries NO overflow clip
 * (the grid article's rule): the popover overhangs the hero's edge freely
 * and the menu's clamp keeps it inside the viewport; the cover rounds and
 * clips itself.
 *
 * Honest deviations from the draft, kept (the gap doc records them): the
 * draft's „Vor 6 Sekunden synchronisiert" line is a sync claim no engine
 * backs — the last-edited stamp in the metrics row is the row's own truth;
 * the blockquote is the row's blurb when it has one, never the demo's
 * invented prose; the workspace door is live (W4 Task 11, row 3 — it
 * resumes the last-edited scene, the label names chapter + scene), the
 * lore door stays disabled with the drafted note until the knowledge
 * wave opens it. A missing target keeps the landing's honest neutral: the
 * count alone, an empty track, no percentage.
 */

import { Link } from "@tanstack/react-router";

import type { Novel } from "@shell/lib/api/client";
import { BookCover } from "@shell/lib/cover/BookCover";
import { useTranslation } from "@shell/lib/i18n";
import { useChaptersQuery } from "@shell/lib/query";
import { formatRelative } from "@shell/lib/time";
import { formatWordCount } from "@shell/lib/words";
import { Icon } from "@shell/ui/icons";

import { progress } from "./shelf";
import { ProgressTrack, StatusPill } from "./ShelfBookCard";
import { ShelfQuickMenu } from "./ShelfQuickMenu";
import { lastEditedEntry, orderedSceneEntries, scenesByChapterFrom, useChapterScenes } from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

export function ShelfHero({ novel, noteId }: { novel: Novel; noteId: string }) {
  const t = useTranslation();
  const result = progress(novel.word_count, novel.target_words);
  // The hero door's resume target (W4 Task 11, gap row 3): the book's
  // last-edited scene, by the server's updated_at — the same rule the
  // workspace's active marker reads, so the door and the marker agree.
  // While the reads stand (or fail) the door keeps the plain verb: it
  // opens the workspace either way, and names no chapter it cannot prove.
  const chapters = useChaptersQuery(novel.id);
  const sceneResults = useChapterScenes(chapters.data ?? []);
  const entries = orderedSceneEntries(
    chapters.data ?? [],
    scenesByChapterFrom(chapters.data ?? [], sceneResults),
  );
  const lastEdited = lastEditedEntry(entries);
  const writeLabel =
    lastEdited !== null
      ? t("writing.shelf.hero.writeScene", {
          chapter: lastEdited.chapter.position + 1,
          scene: lastEdited.scene.position,
        })
      : t("writing.shelf.hero.write");
  return (
    <section className="relative rounded-xl border border-border bg-surface-container-low shadow-sm">
      <div className="relative z-10 flex flex-col items-center gap-8 p-6 md:flex-row lg:p-8">
        {/* The book object — the shared cover system at hero size. */}
        <div className="shrink-0 transition-transform duration-300 hover:-translate-y-1">
          <BookCover title={novel.title} genre={novel.genre} author={novel.author} size="hero" />
        </div>
        <div className="flex-1 space-y-4">
          <div>
            {/* The header row — the eyebrow and the status badge on the left,
                the quick menu's 28px trigger on the right (the draft's
                „oben rechts in der Hero-Kopfzeile"). The wrapper is relative
                so the popover docks under the trigger and overhangs the
                hero's edge freely — the section carries no clip. */}
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-secondary-container px-2.5 py-0.5 text-eyebrow uppercase tracking-wide text-secondary-container-foreground">
                  {t("writing.shelf.hero.eyebrow")}
                </span>
                <StatusPill status={novel.status} />
              </div>
              <ShelfQuickMenu novel={novel} className="relative z-50 shrink-0" />
            </div>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className={`${SERIF} text-2xl font-semibold tracking-tight text-foreground lg:text-3xl`}>
                {novel.title}
              </h2>
              {/* The series line when the book belongs to one; the genre
                  when it stands alone; nothing when neither is answered. */}
              {novel.series_title != null ? (
                <span className="text-label text-muted">
                  {novel.series_volume != null
                    ? t("writing.shelf.hero.series", {
                        series: novel.series_title,
                        volume: novel.series_volume,
                      })
                    : novel.series_title}
                </span>
              ) : novel.genre != null ? (
                <span className="text-label text-muted">{novel.genre}</span>
              ) : null}
            </div>
            {novel.blurb != null && (
              <p
                className={`${SERIF} mt-3 line-clamp-3 max-w-2xl text-body italic leading-relaxed text-muted`}
              >
                {novel.blurb}
              </p>
            )}
          </div>
          {/* The metrics row — the row's own figures, tabular. */}
          <div className="space-y-3 pt-2">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              <div className="flex items-center gap-1.5">
                <span className="text-area-writing">
                  <Icon name="inkHighlighter" size={18} />
                </span>
                <span className="text-emph tabular-nums text-foreground">
                  {formatWordCount(novel.word_count)}
                </span>
                <span className="text-meta text-muted">
                  {novel.target_words != null
                    ? t("writing.shelf.hero.wordsTarget", { target: novel.target_words })
                    : t("writing.shelf.hero.wordsUnit")}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-outline">
                  <Icon name="menuBook" size={18} />
                </span>
                <span className="text-emph tabular-nums text-foreground">{novel.chapter_count}</span>
                <span className="text-meta text-muted">
                  {t("writing.shelf.chapters.unit", { count: novel.chapter_count })}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-outline">
                  <Icon name="clock" size={18} />
                </span>
                <span className="text-meta text-muted">
                  {t("writing.shelf.lastEdited", { when: formatRelative(novel.updated_at) })}
                </span>
              </div>
            </div>
            {/* The drafted progress — or the landing's honest neutral. */}
            <div className="max-w-xl space-y-1.5">
              <div className="flex items-center gap-3">
                <ProgressTrack
                  wordCount={novel.word_count}
                  targetWords={novel.target_words}
                  trackClass="h-1.5 bg-surface-container-highest"
                />
                {result !== null && (
                  <span className="shrink-0 text-label font-semibold tabular-nums text-foreground">
                    {t("writing.shelf.card.percent", { percent: result.percent })}
                  </span>
                )}
              </div>
              {result === null && (
                <p className="text-meta text-muted">{t("writing.shelf.noTarget")}</p>
              )}
            </div>
            {/* The two doors — the workspace door is LIVE (W4 Task 11,
                row 3): it opens the book at its last-edited scene, the
                label naming chapter + scene honestly. The lore door stays
                disabled; its future-facing note is shared with the adjacent
                live workspace CTA. */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                to="/novels/$novelId"
                params={{ novelId: novel.id }}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-6 text-label font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-95 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
              >
                <Icon name="editNote" size={18} />
                <span>{writeLabel}</span>
              </Link>
              <button
                type="button"
                disabled
                aria-describedby={noteId}
                className="inline-flex h-10 cursor-not-allowed items-center gap-1.5 rounded-lg border border-border bg-surface px-4 text-label text-foreground opacity-50 shadow-sm"
              >
                <span className="text-area-knowledge">
                  <Icon name="hub" size={18} />
                </span>
                <span>{t("writing.shelf.hero.lore")}</span>
              </button>
            </div>
            <p id={noteId} className="text-meta text-muted">
              {t("writing.shelf.comingSoon")}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
