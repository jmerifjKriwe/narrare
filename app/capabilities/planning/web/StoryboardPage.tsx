/**
 * The storyboard page (W6 Task 4) — the planning capability's second web
 * surface, ported from the owner-approved harmonized
 * `three-act-storyboard-2` draft onto the shell's tokens. The novel's real
 * StoryboardRead stands the board:
 *
 * - The structure switcher offers the five real ids (three-act the default
 *   every unremapped novel reads); picking another stands the remap
 *   notice, whose apply opens the server's own two-step contract — the
 *   preview (`confirm: false`), then the confirm that writes exactly the
 *   previewed mapping. An unknown structure id surfaces the API's refusal
 *   face (Review Focus 2), never a bricked switcher.
 * - The stage columns carry only real facts: the stage's i18n title (the
 *   key the server's registry names), its share of the unit interval and
 *   the words summed in it; the chapter cards carry the word count, the
 *   sync status, the assignment source and the fan's scene count. The
 *   draft's invented per-act flavor titles, prose excerpts, the duplicated
 *   „#01" number and its „Gespeichert/Wird gesichert" states (no field
 *   carries them) are not ported; the five sync statuses and three scene
 *   lifecycle states get their own honest labels.
 * - The stage select on each card is the stage assignment PUT; a refusal
 *   names itself and the board's refetch returns the card to its column.
 * - The word-total chip reads the novel's real `word_count` and
 *   `target_words` — a novel without a target names no invented one.
 * - The scene drill-in (its own module) stands beside the board on wide
 *   viewports; the subbar with the sub-nav sibling doors stands in EVERY
 *   state — pending, outage, empty, populated (W5 #923's rule). An empty
 *   novel keeps the columns, the switcher and the doors, and its guidance
 *   card doors to the workspace, where chapter creation lives (rule 1:
 *   planning owns no chapter-create seam).
 *
 * The page reads the real API through the shell's query seam and imports
 * no other capability (rule 1).
 */
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useCallback, useMemo, useState } from "react";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { formatNumber } from "@shell/lib/format";
import {
  useChaptersQuery,
  useNovelQuery,
  useNovelScenes,
  useSetChapterStage,
  useStoryboard,
} from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import type { StoryboardChapter, StoryboardStage } from "@shell/lib/api/client";
import { SceneDrillIn } from "./sceneDrillIn";
import { DiscardDraftDialog, RemapDialog, stageLabel } from "./storyboardDialogs";

const TIMELINE_PATH = "/novels/$novelId/planning/timeline";
const CAUSALITY_PATH = "/novels/$novelId/planning/causality";

/** The five real structure ids, the switcher's own order — the client's
 *  mirror of the server registry for the labels alone; the stages, the
 *  default and the remap all stay the server's own answer. */
const STRUCTURE_IDS = ["three-act", "heros-journey", "save-the-cat", "five-act", "seven-point"] as const;

/** The sync dot's tone per real status — the mark, the label names it. */
const SYNC_DOT: Record<string, string> = {
  empty: "bg-outline",
  planned: "bg-primary",
  deviated: "bg-warning",
  completed: "bg-success",
  on_track: "bg-success",
};

/** The stage assignment PUT, owned per card: one hook instance per select,
 *  its refusal named beside it, the board's refetch the settle. */
function StageSelect({
  novelId,
  chapter,
  stages,
}: {
  novelId: string;
  chapter: StoryboardChapter;
  stages: readonly StoryboardStage[];
}) {
  const t = useTranslation();
  const assign = useSetChapterStage(novelId);
  const failed = assign.error !== null;
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <select
        aria-label={t("planning.storyboard.moveLabel")}
        value={chapter.stage_key}
        disabled={assign.isPending}
        onChange={(event) => assign.mutate({ chapterId: chapter.chapter_id, stageKey: event.target.value })}
        className={`w-full rounded border border-border bg-surface-container-low px-1.5 py-0.5 text-meta text-foreground transition-colors ${FOCUS} ${
          assign.isPending ? "cursor-wait opacity-60" : ""
        }`}
      >
        {stages.map((stage) => (
          <option key={stage.key} value={stage.key}>
            {stageLabel(t, stage.key)}
          </option>
        ))}
      </select>
      {failed && (
        <span role="alert" className="text-[11px] leading-tight text-danger">
          {t("planning.storyboard.stageError")}
        </span>
      )}
    </div>
  );
}

export function StoryboardPage() {
  const t = useTranslation();
  const { novelId } = useParams({ from: "/novels/$novelId/planning/storyboard" });
  const navigate = useNavigate();
  usePageTitle(t("planning.storyboard.title"));

  const board = useStoryboard(novelId);
  const chapters = useChaptersQuery(novelId);
  const novel = useNovelQuery(novelId);
  const chapterList = useMemo(() => chapters.data ?? [], [chapters.data]);
  const scenes = useNovelScenes(chapterList);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingStructure, setPendingStructure] = useState<string | null>(null);
  const [remapOpen, setRemapOpen] = useState(false);
  // The dock's unsaved working copy, reported upward: a chapter switch
  // while it stands asks first — the copy never folds behind a silent
  // card click (the review's Important fix).
  const [dockDirty, setDockDirty] = useState(false);
  const [switchGuardId, setSwitchGuardId] = useState<string | null>(null);
  const handleDirtyChange = useCallback((dirty: boolean) => setDockDirty(dirty), []);

  /** The drill-in's selection door: a clean switch walks straight, a
   *  dirty one hands the click to the discard confirm. */
  const selectChapter = useCallback(
    (chapterId: string) => {
      setSelectedId((current) => {
        if (chapterId === current) return current;
        if (dockDirty) {
          setSwitchGuardId(chapterId);
          return current;
        }
        return chapterId;
      });
    },
    [dockDirty],
  );

  const data = board.data;
  const stageList = useMemo(() => data?.stages ?? [], [data]);
  const boardChapters = useMemo(
    () => stageList.flatMap((stage) => stage.chapters ?? []),
    [stageList],
  );
  const structureId = data?.structure_id ?? "three-act";

  // The fan's per-chapter scene counts — only a complete, error-free fan
  // may count (the timeline counters' own rule).
  const sceneCounts = useMemo(() => {
    if (!scenes.isSuccess || scenes.data === undefined) return null;
    const counts = new Map<string, number>();
    for (const aggregate of scenes.data) {
      counts.set(aggregate.chapter_id, aggregate.scenes.length);
    }
    return counts;
  }, [scenes.isSuccess, scenes.data]);
  const scenesTotal = useMemo(
    () => (sceneCounts !== null ? [...sceneCounts.values()].reduce((sum, count) => sum + count, 0) : null),
    [sceneCounts],
  );

  const pending = board.isPending;
  const failed = board.isError;

  const novelWords = novel.data?.word_count ?? null;
  const novelTarget = novel.data?.target_words ?? null;

  /** One chapter card — the draft's geometry on real fields: the sync dot
   *  and chapter number over the serif title, the words beside them; the
   *  foot carries the scene count, the sync label, the assignment source
   *  and the stage select. The card's body is the drill-in affordance. */
  function card(chapter: StoryboardChapter) {
    const selected = chapter.chapter_id === selectedId;
    const count = sceneCounts?.get(chapter.chapter_id);
    return (
      <article
        key={chapter.chapter_id}
        data-testid="storyboard-card"
        className={`relative flex flex-col rounded-[var(--radius-surface)] bg-card p-3 text-left shadow-card transition-shadow ${
          selected ? "border-2 border-primary/40" : "border border-rule hover:bg-surface-container-low"
        }`}
      >
        {selected && (
          <span aria-hidden="true" className="absolute bottom-3 left-0 top-3 w-1.5 rounded-r-full bg-primary" />
        )}
        <button
          type="button"
          id={`storyboard-select-${chapter.chapter_id}`}
          onClick={() => selectChapter(chapter.chapter_id)}
          className={`flex flex-col text-left ${FOCUS}`}
        >
          <span className="mb-1 flex items-start justify-between gap-1">
            <span className="flex items-center gap-1.5">
              <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${SYNC_DOT[chapter.sync_status] ?? SYNC_DOT.empty}`} />
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                {t("planning.storyboard.chapterCard", { position: chapter.position + 1 })}
                {selected ? ` · ${t("planning.storyboard.focusActive")}` : ""}
              </span>
            </span>
            <span className="font-mono text-meta text-outline">
              {t("planning.storyboard.chapterWords", {
                words: chapter.word_count,
                display: formatNumber(chapter.word_count),
              })}
            </span>
          </span>
          <span className="[font-family:var(--font-serif)] text-label font-semibold leading-snug text-foreground">
            {chapter.title.trim() === "" ? t("planning.crud.untitledChapter") : chapter.title}
          </span>
        </button>
        <span className="mt-2.5 flex flex-wrap items-center justify-between gap-1.5 border-t border-rule pt-2 text-meta">
          <span className="flex items-center gap-1">
            <span aria-hidden="true" className="text-muted">
              <Icon name="viewList" size={13} />
            </span>
            {count !== undefined ? (
              t("planning.storyboard.scenesCount", { count })
            ) : (
              <span className="text-muted">{t("planning.storyboard.scenesUnavailable")}</span>
            )}
          </span>
          <span className={chapter.sync_status === "deviated" ? "font-medium text-warning" : "text-muted"}>
            {t(`planning.sync.${chapter.sync_status}` as MessageKey)}
            {chapter.assignment_source === "assigned"
              ? ` · ${t("planning.storyboard.assigned")}`
              : ` · ${t("planning.storyboard.suggested")}`}
          </span>
        </span>
        <span className="mt-1.5 flex items-end justify-end gap-2">
          <StageSelect novelId={novelId} chapter={chapter} stages={stageList} />
        </span>
      </article>
    );
  }

  /** One stage column — the real stage title, its interval share and the
   *  words summed in it; the bar shows the stage's share of the novel's
   *  own words (never an invented target). */
  function column(stage: StoryboardStage) {
    const standing = stage.chapters ?? [];
    const words = standing.reduce((sum, chapter) => sum + chapter.word_count, 0);
    const share = Math.round((stage.to - stage.from) * 100);
    const bar = novelWords !== null && novelWords > 0 ? Math.min(100, Math.round((words / novelWords) * 100)) : 0;
    return (
      <section
        key={stage.key}
        data-testid="storyboard-stage"
        aria-label={stageLabel(t, stage.key)}
        className="flex flex-col gap-2 rounded-[var(--radius-surface)] bg-surface-container-low p-2.5 shadow-card"
      >
        <div className="flex flex-col gap-1 rounded-[var(--radius-control)] bg-card p-2.5 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted">{stageLabel(t, stage.key)}</span>
            <span className="rounded bg-surface-container px-1.5 py-0.5 font-mono text-[11px] text-muted">
              {t("planning.storyboard.stageShare", { share, words: formatNumber(words) })}
            </span>
          </div>
          <div aria-hidden="true" className="h-1 overflow-hidden rounded-full bg-surface-container">
            <div className="h-full rounded-full bg-primary" style={{ width: `${bar}%` }} />
          </div>
        </div>
        <div className="flex flex-col gap-2">{standing.map(card)}</div>
      </section>
    );
  }

  return (
    <div
      id="storyboard-page"
      data-testid="storyboard-page"
      tabIndex={-1}
      className="flex h-full flex-col overflow-hidden focus:outline-none"
    >
      {/* The subbar — the page chip, the sub-nav sibling doors, the
          word-total chip, the structure switcher and the remap notice. It
          stands in EVERY state; only the body below varies. */}
      <div className="flex shrink-0 flex-col gap-2 border-b border-border bg-surface-container-low px-4 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta font-semibold text-foreground shadow-card">
              <span className="text-primary">
                <Icon name="planning" size={15} />
              </span>
              {t("planning.storyboard.title")}
            </span>
            <button
              type="button"
              data-testid="storyboard-timeline-door"
              onClick={() => {
                void navigate({ to: TIMELINE_PATH, params: { novelId }, search: {} });
              }}
              className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <Icon name="schema" size={14} /> {t("planning.timeline.title")}
            </button>
            <button
              type="button"
              data-testid="storyboard-causality-door"
              onClick={() => {
                void navigate({ to: CAUSALITY_PATH, params: { novelId }, search: {} });
              }}
              className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <Icon name="waves" size={14} /> {t("planning.sub.causality")}
            </button>
          </div>
          {/* The word-total chip — the novel's real field, no invented
              target where none stands. */}
          <div
            data-testid="storyboard-progress"
            className="flex flex-wrap items-center gap-2 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card"
          >
            <span aria-hidden="true" className="h-2 w-2 rounded-full bg-success" />
            {novelWords !== null &&
              (novelTarget !== null && novelTarget > 0 ? (
                <>
                  <span>
                    {t("planning.storyboard.progressWords", {
                      words: formatNumber(novelWords),
                      target: formatNumber(novelTarget),
                    })}
                  </span>
                  <span className="rounded bg-surface-container px-1.5 py-0.5 font-mono text-[11px] font-semibold text-primary">
                    {t("planning.storyboard.progressPercent", {
                      percent: Math.min(100, Math.round((novelWords / novelTarget) * 100)),
                    })}
                  </span>
                </>
              ) : (
                <span>{t("planning.storyboard.progressNoTarget", { words: formatNumber(novelWords) })}</span>
              ))}
            {!chapters.isError && (
              <span className="font-medium">{t("planning.storyboard.chaptersCount", { count: chapterList.length })}</span>
            )}
            {scenesTotal !== null ? (
              <span className="font-medium text-muted">
                {t("planning.storyboard.scenesTotal", { count: scenesTotal })}
              </span>
            ) : (
              scenes.isError && (
                <span className="font-medium text-muted">{t("planning.storyboard.scenesUnavailable")}</span>
              )
            )}
          </div>
        </div>
        {/* The structure switcher — the five real ids, the standing one
            lifted; picking another prepares the remap without writing. */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-rule/70 pt-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-outline">
              <Icon name="schema" size={14} /> {t("planning.storyboard.structureLabel")}
            </span>
            <div data-testid="storyboard-structure-switcher" className="flex flex-wrap gap-1">
              {STRUCTURE_IDS.map((id) => {
                const active = id === structureId;
                return (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => {
                      if (!active) setPendingStructure(id);
                    }}
                    className={`flex items-center gap-1 rounded-[var(--radius-control)] px-2.5 py-0.5 text-label shadow-sm transition-colors ${FOCUS} ${
                      active
                        ? "bg-primary font-medium text-primary-foreground"
                        : "bg-card text-foreground hover:bg-surface-container"
                    }`}
                  >
                    {active && <Icon name="check" size={13} />}
                    {t(`storyboard.structure.${id}` as MessageKey)}
                  </button>
                );
              })}
            </div>
          </div>
          <span className="text-[11px] italic text-muted">{t("planning.storyboard.structureNote")}</span>
        </div>
        {/* The remap notice — the draft's explanatory helper, standing
            exactly while a structure change is prepared. */}
        {pendingStructure !== null && pendingStructure !== structureId && (
          <div
            data-testid="storyboard-remap-notice"
            className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-control)] border border-rule bg-card p-2.5"
          >
            <div className="flex min-w-0 items-start gap-2">
              <span aria-hidden="true" className="mt-0.5 shrink-0 text-primary">
                <Icon name="insights" size={16} />
              </span>
              <span className="text-meta leading-snug text-muted">
                <strong className="font-semibold text-foreground">
                  {t("planning.storyboard.remapTitle")}:
                </strong>{" "}
                {t("planning.storyboard.remapNote")}
              </span>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button
                type="button"
                id="storyboard-remap-apply"
                onClick={() => setRemapOpen(true)}
                className={`rounded-[var(--radius-control)] bg-secondary/20 px-2.5 py-1 text-[11px] font-semibold text-foreground transition-colors hover:bg-secondary/30 ${FOCUS}`}
              >
                {t("planning.storyboard.remapApply")}
              </button>
              <button
                type="button"
                onClick={() => setPendingStructure(null)}
                className={`rounded-[var(--radius-control)] px-2.5 py-1 text-[11px] text-muted transition-colors hover:bg-surface-container ${FOCUS}`}
              >
                {t("planning.crud.cancel")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* The body — the honest state's own face; the bar above stays. */}
      {pending ? (
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <p role="status" className="text-body text-muted">
            {t("planning.storyboard.loading")}
          </p>
        </div>
      ) : failed ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div role="alert" className="space-y-2 rounded-[var(--radius-surface)] border border-danger/40 bg-panel p-5 text-center">
            <p className="text-body text-danger">{t("planning.storyboard.loadFailed")}</p>
            <button
              type="button"
              onClick={() => {
                void board.refetch();
                void chapters.refetch();
                void novel.refetch();
                void scenes.refetch();
              }}
              className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              {t("planning.storyboard.retry")}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden xl:flex-row">
          {/* The board — the staged columns, then the empty novel's
              guidance card. */}
          <div className="min-h-0 flex-1 overflow-y-auto bg-surface-container-low/30 p-4">
            <div className="mx-auto flex max-w-6xl flex-col gap-4">
              <div className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] items-start gap-3">
                {stageList.map(column)}
              </div>
              {boardChapters.length === 0 && (
                <div
                  data-testid="storyboard-empty"
                  className="flex flex-col items-center justify-between gap-4 rounded-[var(--radius-surface)] border border-rule bg-card p-4 md:flex-row"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-surface-container">
                      <span className="text-primary">
                        <Icon name="autoStories" size={20} />
                      </span>
                    </div>
                    <div>
                      <h2 className="text-label font-semibold text-foreground">{t("planning.storyboard.empty")}</h2>
                      <p className="text-meta text-muted">{t("planning.storyboard.emptyNote")}</p>
                    </div>
                  </div>
                  <Link
                    to="/novels/$novelId"
                    params={{ novelId }}
                    className={`inline-flex shrink-0 items-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
                  >
                    <Icon name="plus" size={14} /> {t("planning.storyboard.emptyDoor")}
                  </Link>
                </div>
              )}
            </div>
          </div>
          {/* The drill-in — the selected chapter's scene aggregate. */}
          <div className="shrink-0 p-4 pt-0 xl:h-full xl:overflow-hidden xl:p-4 xl:pl-0">
            <SceneDrillIn
              novelId={novelId}
              chapter={boardChapters.find((chapter) => chapter.chapter_id === selectedId) ?? null}
              aggregate={scenes.data?.find((entry) => entry.chapter_id === selectedId)}
              scenesFailed={scenes.isError}
              onRetryScenes={() => {
                void scenes.refetch();
              }}
              onDirtyChange={handleDirtyChange}
            />
          </div>
        </div>
      )}

      {/* The dirty-copy guard — a confirmed switch folds the copy into
          the new chapter's clean rows; a cancel keeps both standing. */}
      {switchGuardId !== null && selectedId !== null && (
        <DiscardDraftDialog
          chapterTitle={
            boardChapters.find((chapter) => chapter.chapter_id === selectedId)?.title.trim() === ""
              ? t("planning.crud.untitledChapter")
              : (boardChapters.find((chapter) => chapter.chapter_id === selectedId)?.title ?? "")
          }
          openerId={`storyboard-select-${switchGuardId}`}
          onCancel={() => setSwitchGuardId(null)}
          onDiscard={() => {
            setSelectedId(switchGuardId);
            setSwitchGuardId(null);
          }}
        />
      )}

      {/* The remap dialog — the preview, then the confirm. */}
      {remapOpen && pendingStructure !== null && (
        <RemapDialog
          novelId={novelId}
          structureId={pendingStructure}
          structureLabel={t(`storyboard.structure.${pendingStructure}` as MessageKey)}
          chapters={boardChapters}
          openerId="storyboard-remap-apply"
          onClose={() => setRemapOpen(false)}
          onApplied={() => setPendingStructure(null)}
        />
      )}
    </div>
  );
}
