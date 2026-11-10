import { Link, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useId } from "react";

import { Button } from "@shell/ui/Button";
import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useNovelsQuery } from "@shell/lib/query";
import { Notice } from "@shell/ui/Notice";
import { stageName } from "./stageNames";

type StoryboardChapter = components["schemas"]["StoryboardChapterRead"];
type StoryboardStage = components["schemas"]["StoryboardStageRead"];
type Storyboard = components["schemas"]["StoryboardRead"];

/**
 * The seam the canvas reads through: the page renders only what this
 * returns, and the return names the one honest split — an answer that is
 * not "ok" is `failed`, never an empty bar, because "no chapters" is a
 * fact only a reachable service can claim (the timeline read's F14
 * precedent, mirrored from the storyboard's own seam so the two canvases
 * degrade alike). An ok answer with data passes through untouched.
 * Exported for the unit test.
 */
export function readStructure(result: {
  data?: Storyboard;
  response: { ok: boolean };
}): { kind: "ok"; board: Storyboard } | { kind: "failed" } {
  if (!result.response.ok || result.data === undefined) return { kind: "failed" };
  return { kind: "ok", board: result.data };
}

/**
 * Each band's width in percent: its span's share of the tiled span. A
 * structure tiles the unit interval contiguously from zero (the backend
 * registry's shape), so the shares add to one hundred. A span that sums to
 * nothing — every stage empty of width — splits evenly instead of dividing
 * by zero; the bar still renders, every band the same size.
 * Exported for the unit test.
 */
export function bandPercents(stages: ReadonlyArray<{ from: number; to: number }>): number[] {
  if (stages.length === 0) return [];
  const spans = stages.map((stage) => Math.max(0, stage.to - stage.from));
  const total = spans.reduce((sum, span) => sum + span, 0);
  if (total <= 0) return stages.map(() => 100 / stages.length);
  return spans.map((span) => (span / total) * 100);
}

/**
 * The summary line's three numbers: the chapters standing on the bar, all
 * their words, and how many drifted off the plan. Exported for the unit test.
 */
export function summarizeBoard(board: Storyboard): {
  chapters: number;
  words: number;
  deviations: number;
} {
  const entries = board.stages.flatMap((stage) => stage.chapters ?? []);
  return {
    chapters: entries.length,
    words: entries.reduce((sum, entry) => sum + entry.word_count, 0),
    deviations: entries.filter((entry) => entry.sync_status === "deviated").length,
  };
}

/**
 * The structure canvas as a full page: the novel's story as one proportion
 * bar — a band per stage, each band as wide as its share of the story, the
 * chapters standing inside their band. Read-only: moves stay on the
 * storyboard, this page only shows the shape. The novel arrives as the
 * `?novel=` search param (the siblings' convention: tolerant in, absent
 * means the picker); a param naming nothing the read returns degrades to
 * the missing-novel state, never an error.
 */
export function StructurePage() {
  const t = useTranslation();
  // The tab's name: this page is "Structure" until it goes.
  usePageTitle(t("structure.heading"));
  const { novel: novelId } = useSearch({ from: "/planning/structure" });
  // A param naming no novel is no novel: the empty string is the absent
  // state, not a novel called "".
  const current = novelId === "" ? undefined : novelId;

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("structure.heading")}</h1>
      {current === undefined ? <NovelPicker /> : <NovelStructure novelId={current} />}
    </div>
  );
}

/** No novel named: the novels to proportion, one link each. */
function NovelPicker() {
  const t = useTranslation();
  const novels = useNovelsQuery();

  if (novels.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-6">
        {t("structure.loading")}
      </Notice>
    );
  }
  if (novels.isError) {
    return (
      <Notice
        tone="danger"
        live="alert"
        className="mt-6"
        action={
          <Button variant="secondary" onClick={() => void novels.refetch()}>
            {t("planning.retry")}
          </Button>
        }
      >
        {t("structure.loadFailed")}
      </Notice>
    );
  }
  const rows = novels.data ?? [];
  if (rows.length === 0) {
    return (
      <Notice
        tone="quiet"
        className="mt-6"
        action={
          <Link
            to="/"
            className="shrink-0 underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("nav.back")}
          </Link>
        }
      >
        {t("planning.noNovels")}
      </Notice>
    );
  }
  return (
    <nav aria-label={t("structure.pickNovel")} className="mt-6 flex flex-col gap-2">
      {rows.map((novel) => (
        <Link
          key={novel.id}
          to="/planning/structure"
          search={{ novel: novel.id }}
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {novel.title}
        </Link>
      ))}
    </nav>
  );
}

/** A refused or unreachable read carries its status beside the error, so
 *  the canvas can tell a missing novel (degrade) from an outage (retry). */
type BoardError = Error & { status?: number };

/** The named novel's shape: its stages as proportional bands. */
function NovelStructure({ novelId }: { novelId: string }) {
  const t = useTranslation();
  const boardQuery = useQuery({
    queryKey: ["planning", "storyboard", novelId],
    queryFn: async () => {
      // The structure canvas reads the storyboard aggregate: no new
      // endpoint, the same answer the storyboard columns stand in.
      const answer = await client.GET("/api/planning/novels/{novel_id}/storyboard", {
        params: { path: { novel_id: novelId } },
      });
      const read = readStructure(answer);
      if (read.kind === "failed") {
        const error = new Error(`structure unavailable: ${answer.response.status}`) as BoardError;
        error.status = answer.response.status;
        throw error;
      }
      return read.board;
    },
  });

  if (boardQuery.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-6">
        {t("structure.loading")}
      </Notice>
    );
  }
  if (boardQuery.isError) {
    // A param naming nothing the read returns degrades, never errors: the
    // missing novel reads as a quiet state with the way back beside it.
    const status = (boardQuery.error as BoardError | null)?.status;
    if (status === 404) {
      return (
        <>
          <p className="mt-2 text-body text-muted">
            <Link
              to="/planning/structure"
              className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
            >
              {t("planning.changeNovel")}
            </Link>
          </p>
          <Notice tone="quiet" className="mt-6">
            {t("structure.novelMissing")}
          </Notice>
        </>
      );
    }
    return (
      <Notice
        tone="danger"
        live="alert"
        className="mt-6"
        action={
          <Button variant="secondary" onClick={() => void boardQuery.refetch()}>
            {t("planning.retry")}
          </Button>
        }
      >
        {t("structure.loadFailed")}
      </Notice>
    );
  }
  const board = boardQuery.data;
  const summary = summarizeBoard(board);
  if (summary.chapters === 0) {
    return (
      <>
        <p className="mt-2 flex flex-wrap gap-x-4 text-body text-muted">
          <Link
            to="/planning/structure"
            className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("planning.changeNovel")}
          </Link>
          <Link
            to="/planning/storyboard"
            search={{ novel: novelId }}
            className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("planning.openStoryboard")}
          </Link>
        </p>
        {/* The honest empty: no chapters is a fact the service confirmed,
            and the next step stands beside it. */}
        <Notice tone="quiet" className="mt-6">
          {t("structure.noChapters")}
        </Notice>
      </>
    );
  }
  const shares = bandPercents(board.stages);
  return (
    <>
      <p className="mt-2 flex flex-wrap gap-x-4 text-body text-muted">
        <Link
          to="/planning/structure"
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("planning.changeNovel")}
        </Link>
        <Link
          to="/planning/storyboard"
          search={{ novel: novelId }}
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("planning.openStoryboard")}
        </Link>
      </p>
      <p className="mt-2 text-body text-muted">
        {t("structure.summary", {
          chapters: summary.chapters,
          words: summary.words,
          deviations: summary.deviations,
        })}
      </p>
      <div className="mt-4 flex w-full items-stretch gap-1">
        {board.stages.map((stage, index) => (
          <StageBand
            key={stage.key}
            stage={stage}
            novelId={novelId}
            share={shares[index] ?? 0}
          />
        ))}
      </div>
    </>
  );
}

/** One stage's band: as wide as its share of the story, the chapters
 *  standing inside it in position order. */
function StageBand({
  stage,
  novelId,
  share,
}: {
  stage: StoryboardStage;
  novelId: string;
  share: number;
}) {
  const t = useTranslation();
  const headingId = useId();
  // Position order, not aggregate order: the band reads left to right.
  const entries = [...(stage.chapters ?? [])].sort((a, b) => a.position - b.position);

  return (
    <section
      aria-labelledby={`${headingId}-band`}
      style={{ width: `${share}%` }}
      className="min-w-0 overflow-hidden border-t border-rule bg-soft px-3 py-2"
    >
      <h2 id={`${headingId}-band`} className="truncate text-label font-semibold text-muted">
        {stageName(t, stage.title_key, stage.key)}
      </h2>
      {entries.length === 0 ? null : (
        <ul className="mt-1 flex flex-col gap-1">
          {entries.map((entry) => (
            <li key={entry.chapter_id} className="min-w-0">
              <ChapterMark entry={entry} novelId={novelId} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** One chapter's mark on the bar: its title walks to the workspace, its
 *  size stands beside it, and a drift off the plan wears its name — a
 *  badge with the word, never colour alone. */
function ChapterMark({ entry, novelId }: { entry: StoryboardChapter; novelId: string }) {
  const t = useTranslation();
  const name = entry.title.trim() === "" ? t("planning.untitledChapter") : entry.title;

  return (
    <div className="min-w-0">
      <Link
        to="/novels/$id"
        params={{ id: novelId }}
        search={{ chapter: entry.chapter_id }}
        title={name}
        className="block truncate text-body font-semibold underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
      >
        {name}
      </Link>
      <p className="flex flex-wrap items-center gap-x-2 text-label text-muted">
        <span>{t("storyboard.words", { count: entry.word_count })}</span>
        {entry.sync_status === "deviated" ? (
          <span className="inline-block border border-current px-1">
            {t("storyboard.sync.deviated")}
          </span>
        ) : null}
      </p>
    </div>
  );
}
