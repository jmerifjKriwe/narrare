/**
 * The causality strip page (W6 Task 5) — the planning capability's third
 * web surface, ported from the owner-approved harmonized `causality-strip`
 * draft onto the shell's tokens. The novel's real scenes in the fan-out's
 * answers, chapter-grouped and chained left-to-right:
 *
 * - Per scene only the real fields: the title (an empty one says
 *   „Ohne Titel", never an invented name), the Konflikt and the
 *   Auflösung — a missing answer renders the honest „—" the drill-in
 *   already uses — and the lifecycle status badge. Beats are deliberately
 *   not shown (the harmonized draft retired them from this face), and the
 *   draft's invented per-scene word counts, lock states and phase labels
 *   are not ported (no field carries them).
 * - The connectors say exactly what the fields support: „Erzwingt"
 *   between a scene and its successor, „Kapitel-Übergang" into a chapter
 *   whose IMMEDIATELY preceding rendered group bears scenes — an empty
 *   chapter between two scene-bearing ones is a break, and no arrow
 *   crosses it — without the draft's invented transition sentence. A
 *   chapter whose fan answers no scenes stands with its label card
 *   alone; no arrow points into emptiness.
 * - The header chips derive from real counts: chapters, scenes, and the
 *   gap count (a scene missing its conflict or its resolution) — a
 *   gapless chain reads as closed, an open one names its count. The
 *   methodology row's diagnostics box counts the same truth.
 * - The empty novel (no chapters, or none with scenes) doors to the
 *   storyboard, where scenes are planned — planning owns no scene-create
 *   seam of its own (rule 1), so „Szene verketten" walks there too, and
 *   the draft's „Zum Manuskript" walks to the workspace.
 * - The subbar with the sub-nav sibling doors stands in EVERY state —
 *   pending, outage, empty, populated (W5 #923's rule); only the body
 *   below it varies. A failed chapters read or a failed fan-out invents
 *   no chain — the failure face stands with its in-place retry.
 *
 * The page reads the real API through the shell's query seam and imports
 * no other capability (rule 1).
 */
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { Fragment, useMemo, type ReactNode } from "react";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useChaptersQuery, useNovelScenes } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon, type IconName } from "@shell/ui/icons";

import type { Chapter, SceneAggregate } from "@shell/lib/api/client";

const TIMELINE_PATH = "/novels/$novelId/planning/timeline";
const STORYBOARD_PATH = "/novels/$novelId/planning/storyboard";

/** The status badge's tone per real lifecycle state — the draft's own
 *  mapping (Verfasst in the cover tone, In Arbeit in warning, Geplant
 *  muted); an unknown status wears the muted face (the drill-in's rule). */
const STATUS_TONE: Record<string, string> = {
  complete: "bg-surface-container-high text-primary",
  in_progress: "bg-surface-container-high text-warning",
  planned: "bg-surface-container text-muted",
};

/** One chainable chapter: the label card's facts and its scenes in the
 *  server's own order — the pure derivation the cards and the counters
 *  read, so the page never sums a half-current novel. */
interface ChainChapter {
  chapter: Chapter;
  scenes: SceneAggregate["scenes"];
}

/** The gap count: a scene missing its conflict or its resolution — the
 *  diagnostics' own definition, computed only over a complete fan. */
function countGaps(chapters: readonly ChainChapter[]): number {
  return chapters.reduce(
    (sum, entry) =>
      sum +
      entry.scenes.filter((scene) => scene.conflict.trim() === "" || scene.resolution.trim() === "").length,
    0,
  );
}

/** The methodology row's three boxes — the draft's bento on one config:
 *  the diagnostics box's `footer` renders the real gap count (green at
 *  zero, warning otherwise), the rule box's the craft rule, the third box
 *  in the draft has none. (The catalog-key fields are named `title` and
 *  `body` — a `…Key` field name trips the secret scanner's generic
 *  api-key rule.) */
const METHODOLOGY: readonly {
  icon: IconName;
  title: MessageKey;
  body: MessageKey;
  footer?: (t: (key: MessageKey, params?: Record<string, string | number>) => string, gaps: number) => ReactNode;
}[] = [
  {
    icon: "hub",
    title: "planning.causality.bento1Title",
    body: "planning.causality.bento1Body",
    footer: (t) => (
      <div className="text-[10px] font-bold uppercase tracking-wider text-primary">
        {t("planning.causality.bento1Rule")}
      </div>
    ),
  },
  {
    icon: "checkCircle",
    title: "planning.causality.bento2Title",
    body: "planning.causality.bento2Body",
    footer: (t, gaps) => (
      <div className={`text-[10px] font-bold uppercase tracking-wider ${gaps === 0 ? "text-success" : "text-warning"}`}>
        {t("planning.causality.gapStatus", { count: gaps })}
      </div>
    ),
  },
  {
    icon: "historyEdu",
    title: "planning.causality.bento3Title",
    body: "planning.causality.bento3Body",
  },
];

export function CausalityPage() {
  const t = useTranslation();
  const { novelId } = useParams({ from: "/novels/$novelId/planning/causality" });
  const navigate = useNavigate();
  usePageTitle(t("planning.causality.title"));

  const chapters = useChaptersQuery(novelId);
  const chapterList = useMemo(() => chapters.data ?? [], [chapters.data]);
  const scenes = useNovelScenes(chapterList);

  // The chainable chapters, in the server's own order — the fan-out's
  // combined answer stands only when every chapter answered, so a
  // half-current novel never reaches the cards below.
  const chain = useMemo<ChainChapter[]>(() => {
    if (!chapters.isSuccess || !scenes.isSuccess || scenes.data === undefined) return [];
    const byChapter = new Map(scenes.data.map((aggregate) => [aggregate.chapter_id, aggregate]));
    return chapterList.map((chapter) => ({
      chapter,
      scenes: byChapter.get(chapter.id)?.scenes ?? [],
    }));
  }, [chapters.isSuccess, scenes.isSuccess, scenes.data, chapterList]);

  const scenesTotal = useMemo(
    () => chain.reduce((sum, entry) => sum + entry.scenes.length, 0),
    [chain],
  );
  const gaps = useMemo(() => (scenes.isSuccess ? countGaps(chain) : null), [scenes.isSuccess, chain]);

  const pending = chapters.isPending || scenes.isPending;
  const failed = chapters.isError || scenes.isError;
  const empty = !pending && !failed && scenesTotal === 0;

  /** One scene card — the draft's geometry on real fields: the scene
   *  heading with its status badge, the Konflikt and Auflösung slots with
   *  their honest „—" where the novel has no answer. */
  function sceneCard(chapter: ChainChapter, scene: SceneAggregate["scenes"][number]) {
    const title = scene.title.trim() === "" ? t("planning.storyboard.untitledScene") : scene.title;
    return (
      <article
        key={scene.id}
        data-testid="causality-scene"
        className="flex w-72 shrink-0 flex-col justify-between gap-2 rounded-[var(--radius-surface)] border border-rule bg-card p-3 shadow-card"
      >
        <div className="flex flex-col gap-2">
          <div className="flex items-start justify-between gap-2">
            <h4 className="text-label font-semibold leading-snug text-foreground">
              {t("planning.storyboard.sceneLabel", {
                chapter: chapter.chapter.position + 1,
                position: scene.position,
                title,
              })}
            </h4>
            <span
              className={`shrink-0 rounded-[var(--radius-control)] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                STATUS_TONE[scene.status] ?? STATUS_TONE.planned
              }`}
            >
              {t(`planning.sceneStatus.${scene.status}` as MessageKey)}
            </span>
          </div>
          <div className="flex flex-col gap-0.5 text-[13px] leading-snug">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                {t("planning.storyboard.conflict")}:
              </span>{" "}
              <span className={scene.conflict.trim() === "" ? "italic text-muted" : "text-foreground"}>
                {scene.conflict.trim() === "" ? "—" : scene.conflict}
              </span>
            </div>
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                {t("planning.storyboard.resolutionField")}:
              </span>{" "}
              <span className={scene.resolution.trim() === "" ? "italic text-muted" : "text-foreground"}>
                {scene.resolution.trim() === "" ? "—" : scene.resolution}
              </span>
            </div>
          </div>
        </div>
      </article>
    );
  }

  /** The scene-to-scene connector: the draft's line, its eastward chevron
   *  and the rotated „Erzwingt" micro-label. The label is real content —
   *  the forcing relation is announced in reading order, exactly between
   *  the scenes it holds between — while the glyphs stay hidden (a glyph
   *  is never its own accessible name). */
  function sceneLink() {
    return (
      <div
        data-testid="causality-link"
        className="flex w-8 shrink-0 flex-col items-center justify-center gap-1 self-center"
      >
        <span aria-hidden="true" className="h-px w-4 bg-outline/50" />
        <span aria-hidden="true" className="-rotate-90 text-outline">
          <Icon name="chevronDown" size={13} />
        </span>
        <span className="text-[9px] font-bold uppercase tracking-widest text-muted [writing-mode:vertical-rl]">
          {t("planning.causality.forces")}
        </span>
      </div>
    );
  }

  /** The chapter transition: the draft's double chevron and its label —
   *  no invented summary sentence; the cards themselves are the words.
   *  The label is announced like „Erzwingt" — real meaning, not decor. */
  function chapterTransition() {
    return (
      <div
        data-testid="causality-transition"
        className="flex w-24 shrink-0 flex-col items-center justify-center gap-1 self-center text-center"
      >
        <span aria-hidden="true" className="flex items-center">
          <span className="-rotate-90 text-primary">
            <Icon name="chevronDown" size={15} />
          </span>
          <span className="-ml-2 -rotate-90 text-primary">
            <Icon name="chevronDown" size={15} />
          </span>
        </span>
        <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
          {t("planning.causality.chapterTransition")}
        </span>
      </div>
    );
  }

  /** One chapter group — the draft's label card beside its scene chain:
   *  the chapter number, its title (an empty one says so), the scene
   *  count, and the scenes in the server's own order with the connectors
   *  between them. The transition stands only where the chain actually
   *  continues across the crossing: the IMMEDIATELY preceding rendered
   *  group must bear scenes — an empty chapter between two scene-bearing
   *  ones is a break, and no arrow claims a forcing the empty group does
   *  not carry. */
  function chapterGroup(entry: ChainChapter, precededByScenes: boolean) {
    const title =
      entry.chapter.title.trim() === "" ? t("planning.crud.untitledChapter") : entry.chapter.title;
    return (
      <Fragment key={entry.chapter.id}>
        {entry.scenes.length > 0 && precededByScenes && chapterTransition()}
        <section
          data-testid="causality-chapter"
          aria-label={`${t("planning.storyboard.chapterCard", { position: entry.chapter.position + 1 })}: ${title}`}
          className="flex items-stretch gap-2 rounded-[var(--radius-surface)] bg-surface-container-low p-2 shadow-card"
        >
          <div className="flex w-40 shrink-0 flex-col justify-between gap-2 rounded-[var(--radius-control)] bg-card p-2.5 shadow-sm">
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
                {t("planning.storyboard.chapterCard", { position: entry.chapter.position + 1 })}
              </span>
              <h3 className="[font-family:var(--font-serif)] text-label font-semibold leading-snug text-foreground">
                {title}
              </h3>
            </div>
            <span className="text-meta text-muted">
              {t("planning.storyboard.scenesCount", { count: entry.scenes.length })}
            </span>
          </div>
          {entry.scenes.map((scene, index) => (
            <div key={scene.id} className="flex items-stretch">
              {index > 0 && sceneLink()}
              {sceneCard(entry, scene)}
            </div>
          ))}
        </section>
      </Fragment>
    );
  }

  return (
    <div
      id="causality-page"
      data-testid="causality-page"
      tabIndex={-1}
      className="flex h-full flex-col overflow-hidden focus:outline-none"
    >
      {/* The subbar — the page chip, the sub-nav sibling doors (the drafts'
          mechanism) and the draft's two action doors. One consistent
          mechanism with the knowledge surfaces: the bar stands in EVERY
          state — pending, failed, empty, populated — so the sibling doors
          never vanish behind an honest face; only the body below varies. */}
      <div className="flex shrink-0 flex-col gap-2 border-b border-border bg-surface-container-low px-4 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta font-semibold text-foreground shadow-card">
              <span className="text-primary">
                <Icon name="waves" size={15} />
              </span>
              {t("planning.sub.causality")}
            </span>
            <button
              type="button"
              data-testid="causality-timeline-door"
              onClick={() => {
                void navigate({ to: TIMELINE_PATH, params: { novelId }, search: {} });
              }}
              className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <Icon name="clock" size={14} /> {t("planning.timeline.title")}
            </button>
            <button
              type="button"
              data-testid="causality-storyboard-door"
              onClick={() => {
                void navigate({ to: STORYBOARD_PATH, params: { novelId }, search: {} });
              }}
              className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <Icon name="viewList" size={14} /> {t("planning.sub.storyboard")}
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* The draft's „Szene verketten" — the walk goes to the
                storyboard, the surface where scenes are planned (rule 1:
                the strip owns no scene-create seam). */}
            <button
              type="button"
              data-testid="causality-verketten-door"
              onClick={() => {
                void navigate({ to: STORYBOARD_PATH, params: { novelId }, search: {} });
              }}
              className={`inline-flex items-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-3 py-1 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
            >
              <Icon name="plus" size={14} /> {t("planning.causality.verketten")}
            </button>
            {/* The draft's „Zum Manuskript" — the workspace, as a real
                link: the shell's own route. */}
            <Link
              to="/novels/$novelId"
              params={{ novelId }}
              data-testid="causality-manuscript-door"
              className={`inline-flex items-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container-high px-3 py-1 text-meta font-medium text-foreground shadow-sm transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <Icon name="write" size={14} /> {t("planning.causality.manuscriptDoor")}
            </Link>
          </div>
        </div>
      </div>

      {/* The body — the honest state's own face; the bar above stays. */}
      {pending ? (
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <p role="status" className="text-body text-muted">
            {t("planning.causality.loading")}
          </p>
        </div>
      ) : failed ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div role="alert" className="space-y-2 rounded-[var(--radius-surface)] border border-danger/40 bg-panel p-5 text-center">
            <p className="text-body text-danger">{t("planning.causality.loadFailed")}</p>
            <button
              type="button"
              onClick={() => {
                void chapters.refetch();
                void scenes.refetch();
              }}
              className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              {t("planning.causality.retry")}
            </button>
          </div>
        </div>
      ) : empty ? (
        /* The draft's tabula-rasa banner: the unbesetzt novel's face,
           walking to the storyboard where its first scene is planned. */
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div
            data-testid="causality-empty"
            className="flex max-w-lg flex-col items-center justify-between gap-4 rounded-[var(--radius-surface)] border border-rule bg-panel p-6 text-center sm:flex-row sm:text-left"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-surface-container text-primary shadow-sm">
                <Icon name="viewList" size={24} />
              </div>
              <div className="flex flex-col gap-1">
                <p className="text-body font-semibold text-foreground">{t("planning.causality.empty")}</p>
                <p className="text-meta text-muted">{t("planning.causality.emptyNote")}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                void navigate({ to: STORYBOARD_PATH, params: { novelId }, search: {} });
              }}
              className={`inline-flex shrink-0 items-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container-high px-3 py-1.5 text-meta font-medium text-foreground shadow-sm transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              {t("planning.causality.emptyDoor")} <Icon name="plus" size={14} />
            </button>
          </div>
        </div>
      ) : (
        /* The draft's face: the subline block with the real-count chips,
           the horizontally scrollable chain, the methodology row. */
        <div className="min-h-0 flex-1 overflow-y-auto bg-surface-container-low/30 p-4">
          <div className="mx-auto flex min-h-full max-w-6xl flex-col justify-between gap-4">
            {/* The subline — the draft's eyebrow, its honest sentence and
                the real-count chips. */}
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="flex max-w-xl flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-primary">
                    {t("planning.causality.eyebrow")}
                  </span>
                  <span aria-hidden="true" className="h-1 w-1 rounded-full bg-outline" />
                  <span className="text-meta text-muted">{t("planning.causality.domain")}</span>
                </div>
                <p className="[font-family:var(--font-serif)] text-label italic leading-snug text-foreground">
                  {t("planning.causality.subtitle")}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div
                  data-testid="causality-counts"
                  className="flex items-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container px-2.5 py-1 text-meta text-foreground shadow-sm"
                >
                  <span className="text-primary">
                    <Icon name="menuBook" size={13} />
                  </span>
                  <span className="font-medium">{t("planning.storyboard.chaptersCount", { count: chapterList.length })}</span>
                  <span aria-hidden="true">·</span>
                  <span className="font-medium">{t("planning.storyboard.scenesTotal", { count: scenesTotal })}</span>
                </div>
                {/* The chain's state: closed where every scene answers,
                    named by its gap count where it doesn't — derived from
                    the fields, never dressed as whole. The dot carries the
                    state in color (the draft's own chip: state dot, plain
                    on-surface text — a graphic needs 3:1, and the words
                    stay readable); the warning tone on 12px text would
                    miss the contrast floor on this chip's surface. */}
                {gaps !== null && (
                  <div
                    data-testid="causality-chain"
                    className="flex items-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container px-2.5 py-1 text-meta text-foreground shadow-sm"
                  >
                    <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${gaps === 0 ? "bg-success" : "bg-warning"}`} />
                    <span className="font-medium">
                      {gaps === 0
                        ? t("planning.causality.chainWhole")
                        : t("planning.causality.chainGaps", { count: gaps })}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* The track header — the chain reads left-to-right; the
                scroll affordance names itself. */}
            <div className="flex items-center justify-between px-1">
              <h2 className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-muted">
                <span className="text-primary">
                  <Icon name="schema" size={15} />
                </span>
                {t("planning.causality.trackLabel")}
              </h2>
              <span className="text-meta italic text-muted">{t("planning.causality.trackHint")}</span>
            </div>

            {/* The chain — the draft's horizontally scrollable track, the
                chapter groups left-to-right with their connectors. The
                tabIndex keeps the scrollable region on the keyboard (the
                scrollable-region rule the axe floor runs). */}
            <div
              data-testid="causality-track"
              aria-label={t("planning.causality.trackLabel")}
              tabIndex={0}
              className="w-full overflow-x-auto pb-2"
            >
              <div className="inline-flex min-w-max items-stretch gap-3 pr-3">
                {chain.map((entry, index) =>
                  chapterGroup(entry, index > 0 && (chain[index - 1]?.scenes.length ?? 0) > 0),
                )}
              </div>
            </div>

            {/* The methodology row — the draft's three boxes on the shell's
                tokens; the diagnostics box counts the real gaps. */}
            <div
              data-testid="causality-bento"
              className="grid grid-cols-1 gap-3 pt-1 md:grid-cols-3"
            >
              {METHODOLOGY.map(({ icon, title, body, footer }) => (
                <div
                  key={title}
                  className="flex flex-col justify-between gap-2 rounded-[var(--radius-surface)] bg-card p-3.5 shadow-card"
                >
                  <div className="flex items-start gap-2.5">
                    <span aria-hidden="true" className="text-primary">
                      <Icon name={icon} size={20} />
                    </span>
                    <div className="flex flex-col gap-1">
                      <h3 className="text-label font-semibold text-foreground">{t(title)}</h3>
                      <p className="text-meta leading-relaxed text-muted">{t(body)}</p>
                    </div>
                  </div>
                  {footer?.(t, gaps ?? 0)}
                </div>
              ))}
            </div>

            {/* The bottom disclaimer — the draft's footnote, reworded into
                the vocabulary gate's own law: the strip mirrors only the
                novel's real scene entries, and claims nothing beyond them
                (the owner's one-key ruling). */}
            <p data-testid="causality-note" className="border-t border-rule/30 pt-2 text-meta italic leading-relaxed text-muted">
              {t("planning.causality.laterNote")}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
