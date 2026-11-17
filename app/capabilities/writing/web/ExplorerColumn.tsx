/**
 * The explorer column (W4 Task 11, read-only) — the scene-centric draft's
 * 280px left column on the shell's tokens: the identity card, the daily
 * ring, the tension card, the scene tree and the shelf mini-card.
 *
 * Honest readings of the draft (the gap doc records them):
 * - The daily ring is REAL: the activity aggregate's goal fields — the
 *   same source the shelf banner reads (today_words vs daily_goal_words,
 *   goal_remaining, goal_met). Unset keeps the honest neutral; the inline
 *   setter affordance (D20) waits disabled for Task 19's goal surface.
 * - The tension card's stage label is REAL (the planning storyboard's own
 *   title key, resolved against the catalog); the curve is the drafted
 *   PLACEHOLDER (INTERIM #879 — no tension data exists, the draft's curve
 *   and figures never ship as data). The label row carries the real scene
 *   codes: first, active, last.
 * - The tree's status dots are NEUTRAL (INTERIM #873 — no chapter/scene
 *   status field exists): faint ink, terracotta for the active scene. The
 *   active marker is the last-edited scene (updated_at) — the hero door's
 *   own rule. The draft's drag handles wait for Task 13's reorder; a grip
 *   that moves nothing would be a false affordance, so none renders.
 * - „+ Neues Kapitel" / „+ Neue Szene" render DISABLED (Task 13 wires the
 *   CRUD); the empty book's invitation door likewise (Kachel 3).
 * - Word counts are the rows' own, tabular; long titles truncate with the
 *   full title in the tooltip (Kachel 5); many chapters scroll (Kachel 6).
 */

import { Link } from "@tanstack/react-router";
import type { UseQueryResult } from "@tanstack/react-query";

import type { Activity, Chapter, Novel, Scene, Storyboard } from "@shell/lib/api/client";
import { BookCover, PALETTE } from "@shell/lib/cover/BookCover";
import { coverModel } from "@shell/lib/cover/cover";
import { formatNumber } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { progress } from "./shelf";
import { Bone } from "./ShelfStates";
import {
  sceneTitle,
  stageTitleKey,
  tensionCodes,
  type SceneEntry,
} from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the column offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The draft's card eyebrow. */
const EYEBROW = "text-[10px] font-semibold uppercase tracking-wider text-muted";

/** The ring's circle — the draft's 36-viewBox path, one turn = 100. */
const RING_PATH =
  "M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831";

/** The identity card — the real cover chip, title, author, genre. */
function IdentityCard({ novel }: { novel: Novel }) {
  return (
    <div
      data-testid="explorer-identity"
      className="flex items-center gap-2.5 rounded-lg border border-border bg-panel p-2.5 shadow-card"
    >
      <BookCover title={novel.title} genre={novel.genre} author={novel.author} size="mini" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-1">
          <h2
            className={`${SERIF} truncate text-body font-bold tracking-tight text-foreground`}
            title={novel.title}
          >
            {novel.title}
          </h2>
          {novel.author != null && novel.author.trim() !== "" && (
            <span className="shrink-0 text-[10px] text-muted">{novel.author}</span>
          )}
        </div>
        {novel.genre != null && novel.genre.trim() !== "" && (
          <p className="mt-0.5 truncate text-[11px] text-muted" title={novel.genre}>
            {novel.genre}
          </p>
        )}
      </div>
    </div>
  );
}

/** The daily ring — the aggregate's own goal fields, the banner's source. */
function DailyRing({ activity }: { activity: UseQueryResult<Activity> }) {
  const t = useTranslation();
  const data = activity.data;
  const result = data != null ? progress(data.today_words, data.daily_goal_words) : null;
  return (
    <div data-testid="explorer-ring" className="rounded-lg border border-border bg-panel p-3 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <span className={EYEBROW}>{t("writing.workspace.ring.title")}</span>
        {/* D20's inline setter affordance — INTERIM Task 19: the goal
            surface owns the write; the geometry stands, the action waits. */}
        <button
          type="button"
          disabled
          aria-label={t("writing.workspace.ring.edit")}
          title={t("writing.workspace.ring.editNote")}
          className="cursor-not-allowed rounded p-0.5 text-muted opacity-60"
        >
          <Icon name="write" size={12} />
        </button>
      </div>
      {activity.isPending ? (
        <div className="flex items-center gap-3">
          <Bone className="h-11 w-11 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Bone className="h-4 w-24" />
            <Bone className="h-2.5 w-32" />
          </div>
        </div>
      ) : data == null ? (
        /* The error neutral — the aggregate unreachable is no zero day. */
        <p className="font-mono text-meta text-muted">—</p>
      ) : (
        <div className="flex items-center gap-3">
          <div className="relative flex h-11 w-11 shrink-0 items-center justify-center">
            <svg aria-hidden="true" className="h-11 w-11 -rotate-90" viewBox="0 0 36 36">
              <path
                className="stroke-border"
                strokeWidth={3.5}
                stroke="currentColor"
                fill="none"
                d={RING_PATH}
              />
              {result !== null && (
                <path
                  data-ring-progress
                  className="stroke-primary"
                  strokeDasharray={`${result.percent}, 100`}
                  strokeWidth={3.5}
                  strokeLinecap="round"
                  stroke="currentColor"
                  fill="none"
                  d={RING_PATH}
                />
              )}
            </svg>
            <span className="absolute font-mono text-[11px] font-semibold text-primary">
              {result !== null ? t("writing.shelf.card.percent", { percent: result.percent }) : "—"}
            </span>
          </div>
          <div className="min-w-0">
            {/* The draft's split typography: the day's count bold, the
                goal suffix faint — the catalog owns the suffix's words. */}
            <div className="flex items-baseline font-mono">
              <span className="text-base font-bold tabular-nums text-foreground">
                {formatNumber(data.today_words)}
              </span>
              <span className="text-meta text-muted">
                {data.daily_goal_words != null
                  ? t("writing.workspace.ring.pairSuffix", { goal: data.daily_goal_words })
                  : t("writing.workspace.ring.todaySuffix")}
              </span>
            </div>
            <p className="mt-0.5 text-[10px] text-muted">
              {data.daily_goal_words == null
                ? t("writing.workspace.ring.noGoal")
                : data.goal_met
                  ? t("writing.workspace.ring.met")
                  : t("writing.workspace.ring.remaining", { count: data.goal_remaining })}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

/** The tension card — the real stage label over the placeholder curve. */
function TensionCard({
  storyboard,
  entries,
  active,
  activeChapterId,
}: {
  storyboard: UseQueryResult<Storyboard>;
  entries: readonly SceneEntry[];
  active: SceneEntry | null;
  activeChapterId: string | null;
}) {
  const t = useTranslation();
  const stageKey = stageTitleKey(storyboard.data, activeChapterId);
  const codes = tensionCodes(entries, active);
  return (
    <div data-testid="explorer-tension" className="rounded-lg border border-border bg-panel p-3 shadow-card">
      <div className="mb-1.5 flex items-center justify-between">
        <span className={EYEBROW}>{t("writing.workspace.tension.title")}</span>
        <span className={`${SERIF} text-[11px] font-medium text-primary`}>
          {stageKey !== null ? t(stageKey) : "—"}
        </span>
      </div>
      {/* INTERIM #879: the curve is the draft's placeholder geometry — no
          tension data exists on any model. The pulse dot is the drafted
          mark, not a measured position; the real facts are the stage label
          above and the scene codes below. */}
      <div className="relative flex h-9 w-full items-center">
        <svg aria-hidden="true" className="h-8 w-full overflow-visible" viewBox="0 0 240 32" fill="none">
          <line x1="0" y1="28" x2="240" y2="28" className="stroke-border" strokeWidth="1" strokeDasharray="3 3" />
          <path
            d="M 0 26 Q 40 24 80 18 T 150 7 T 200 14 T 240 22"
            className="stroke-outline-variant"
            strokeWidth="1.75"
            strokeLinecap="round"
          />
          <path
            d="M 0 26 Q 40 24 80 18 T 142 8"
            className="stroke-primary"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <circle cx="142" cy="8" r="3.5" className="animate-pulse fill-primary" />
          <circle cx="142" cy="8" r="7" className="stroke-primary" strokeWidth="1" strokeOpacity="0.35" />
        </svg>
      </div>
      {codes.length > 0 && (
        <div className="mt-1 flex justify-between font-mono text-[9.5px] text-muted">
          {codes.map((code) => (
            <span
              key={`${code.chapter}-${code.scene}`}
              className={code.active ? "font-semibold text-primary" : undefined}
            >
              {t("writing.workspace.sceneCode", { chapter: code.chapter, scene: code.scene })}
              {code.active && <span> {t("writing.workspace.tension.activeMark")}</span>}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** One scene row — the neutral dot (#873), the label, the tabular count. */
function SceneRow({
  entry,
  active,
  onSelect,
}: {
  entry: SceneEntry;
  active: boolean;
  onSelect: (sceneId: string) => void;
}) {
  const t = useTranslation();
  const label = t("writing.workspace.tree.sceneLabel", {
    number: entry.scene.position,
    title: sceneTitle(entry.scene.title, t("writing.workspace.untitledScene")),
  });
  return (
    <button
      type="button"
      onClick={() => onSelect(entry.scene.id)}
      aria-current={active ? "true" : undefined}
      className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left transition-colors ${FOCUS} ${
        active
          ? "border border-primary/30 bg-primary/10 font-medium text-primary shadow-sm"
          : "border border-transparent text-muted hover:bg-surface-container-low hover:text-foreground"
      }`}
    >
      <span className="flex min-w-0 items-center gap-2">
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${active ? "bg-primary" : "bg-muted/60"}`}
        />
        <span className="truncate text-meta" title={label}>
          {label}
        </span>
      </span>
      <span
        className={`shrink-0 pl-1 font-mono text-[10px] tabular-nums ${active ? "font-semibold text-primary" : "text-muted"}`}
      >
        {t("writing.workspace.tree.words", { count: entry.scene.word_count })}
      </span>
    </button>
  );
}

/** One chapter card — the header (chevron + select + count) and the scenes. */
function ChapterCard({
  chapter,
  scenes,
  scenesPending,
  scenesError,
  collapsed,
  activeSceneId,
  onToggle,
  onSelect,
  onSelectScene,
}: {
  chapter: Chapter;
  scenes: readonly Scene[];
  scenesPending: boolean;
  scenesError: boolean;
  collapsed: boolean;
  activeSceneId: string | null;
  onToggle: (chapterId: string) => void;
  onSelect: (chapterId: string) => void;
  onSelectScene: (sceneId: string) => void;
}) {
  const t = useTranslation();
  const number = chapter.position + 1;
  const name = t("writing.workspace.tree.chapterName", {
    number,
    title: sceneTitle(chapter.title, t("writing.workspace.untitledChapter")),
  });
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-panel">
      <div className="flex items-center justify-between gap-1 border-b border-border bg-surface-container-low/50 px-2.5 py-2">
        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          <button
            type="button"
            onClick={() => onToggle(chapter.id)}
            aria-label={t(collapsed ? "writing.workspace.tree.expand" : "writing.workspace.tree.collapse", { number })}
            aria-expanded={!collapsed}
            className={`shrink-0 rounded text-muted transition-colors hover:text-foreground ${FOCUS}`}
          >
            <Icon name={collapsed ? "expandLess" : "chevronDown"} size={14} />
          </button>
          <button
            type="button"
            onClick={() => onSelect(chapter.id)}
            className={`min-w-0 flex-1 rounded text-left ${FOCUS}`}
          >
            <span className={`${SERIF} block truncate text-meta font-semibold text-foreground`} title={name}>
              {name}
            </span>
          </button>
        </div>
        <span className="shrink-0 font-mono text-[10px] tabular-nums text-muted">
          {t("writing.workspace.tree.words", { count: chapter.word_count })}
        </span>
      </div>
      {!collapsed && (
        <div className="space-y-0.5 p-1">
          {scenesPending ? (
            <>
              <Bone className="h-6 w-full" />
              <Bone className="h-6 w-4/5" />
            </>
          ) : scenesError ? (
            <p className="px-2 py-1.5 font-mono text-[10px] text-muted">—</p>
          ) : scenes.length === 0 ? (
            /* D16's real state — the chapter stands, no scene invented. */
            <p className="px-2 py-1.5 pl-5 text-[10px] italic text-muted">
              {t("writing.workspace.tree.emptyChapter")}
            </p>
          ) : (
            [...scenes]
              .sort((a, b) => a.position - b.position)
              .map((scene) => (
                <SceneRow
                  key={scene.id}
                  entry={{ scene, chapter }}
                  active={scene.id === activeSceneId}
                  onSelect={onSelectScene}
                />
              ))
          )}
        </div>
      )}
    </div>
  );
}

export function ExplorerColumn({
  novel,
  chapters,
  sceneResults,
  entries,
  activeSceneId,
  activeChapterId,
  collapsed,
  onToggleChapter,
  onSelectChapter,
  onSelectScene,
  activity,
  storyboard,
}: {
  novel: Novel;
  chapters: readonly Chapter[];
  /** Aligned with `chapters` — one scene answer per chapter. */
  sceneResults: readonly UseQueryResult<Scene[]>[];
  entries: readonly SceneEntry[];
  activeSceneId: string | null;
  activeChapterId: string | null;
  collapsed: ReadonlySet<string>;
  onToggleChapter: (chapterId: string) => void;
  onSelectChapter: (chapterId: string) => void;
  onSelectScene: (sceneId: string) => void;
  activity: UseQueryResult<Activity>;
  storyboard: UseQueryResult<Storyboard>;
}) {
  const t = useTranslation();
  const active = entries.find((entry) => entry.scene.id === activeSceneId) ?? null;
  const monogram = coverModel({ title: novel.title, genre: novel.genre, size: "mini" });
  const palette = PALETTE[monogram.channel];
  return (
    <aside
      aria-label={t("writing.workspace.explorer.label")}
      className="flex h-full w-[280px] shrink-0 flex-col border-r border-border bg-surface-container-low/60 text-meta"
    >
      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        <IdentityCard novel={novel} />
        <DailyRing activity={activity} />
        <TensionCard
          storyboard={storyboard}
          entries={entries}
          active={active}
          activeChapterId={activeChapterId}
        />
        {chapters.length === 0 ? (
          /* Kachel 3 — the empty book's invitation, the create door
             disabled until Task 13 wires the CRUD. */
          <div
            data-testid="explorer-empty-book"
            className="flex flex-col justify-between rounded-lg border border-dashed border-primary/40 bg-panel p-3.5"
          >
            <div>
              <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-primary">
                {t("writing.workspace.emptyBook.eyebrow")}
              </span>
              <p className="mt-1.5 text-meta font-medium text-foreground">
                {t("writing.workspace.emptyBook.title")}
              </p>
              <p className="mt-1 text-[11px] leading-snug text-muted">
                {t("writing.workspace.emptyBook.body")}
              </p>
            </div>
            <button
              type="button"
              disabled
              title={t("writing.workspace.crudNote")}
              className={`mt-3 flex w-full cursor-not-allowed items-center justify-center gap-1 rounded bg-primary px-2 py-1.5 text-[11px] font-medium text-primary-foreground opacity-50 shadow-sm ${FOCUS}`}
            >
              <Icon name="plus" size={13} />
              <span>{t("writing.workspace.emptyBook.action")}</span>
            </button>
          </div>
        ) : (
          <div data-testid="explorer-tree" className="space-y-2 pt-1">
            <div className="flex items-center justify-between px-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
                {t("writing.workspace.tree.title")}
              </span>
              <span className="font-mono text-[10px] tabular-nums text-muted">
                {t("writing.workspace.tree.total", { count: novel.word_count })}
              </span>
            </div>
            {chapters.map((chapter, at) => (
              <ChapterCard
                key={chapter.id}
                chapter={chapter}
                scenes={sceneResults[at]?.data ?? []}
                scenesPending={sceneResults[at]?.isPending ?? false}
                scenesError={sceneResults[at]?.isError ?? false}
                collapsed={collapsed.has(chapter.id)}
                activeSceneId={activeSceneId}
                onToggle={onToggleChapter}
                onSelect={onSelectChapter}
                onSelectScene={onSelectScene}
              />
            ))}
            {/* Task 13 wires the CRUD — the doors keep their geometry. */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                disabled
                title={t("writing.workspace.crudNote")}
                className="flex cursor-not-allowed items-center justify-center gap-1 rounded border border-border bg-panel px-2 py-1.5 text-[11px] text-muted opacity-60"
              >
                <Icon name="plus" size={12} />
                <span>{t("writing.workspace.tree.newChapter")}</span>
              </button>
              <button
                type="button"
                disabled
                title={t("writing.workspace.crudNote")}
                className="flex cursor-not-allowed items-center justify-center gap-1 rounded border border-border bg-panel px-2 py-1.5 text-[11px] text-muted opacity-60"
              >
                <Icon name="plus" size={12} />
                <span>{t("writing.workspace.tree.newScene")}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* The shelf mini-card — the cover system's pigment at chip size,
          the way back to the atelier's overview. */}
      <div className="shrink-0 border-t border-border bg-panel/70 p-3">
        <Link
          to="/"
          className={`group flex items-center gap-2.5 rounded-md p-2 transition-colors hover:bg-surface-container-low ${FOCUS}`}
        >
          <span
            className={`flex h-8 w-6 shrink-0 items-center justify-center rounded-sm shadow-sm ${palette.ground} ${palette.ink}`}
          >
            <span className={`${SERIF} text-[7px] font-bold leading-none`}>{monogram.monogramText}</span>
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1 text-foreground transition-colors group-hover:text-primary">
              <span className="rotate-180">
                <Icon name="arrowRight" size={12} />
              </span>
              <span className="truncate text-meta font-medium">{t("writing.workspace.mini.back")}</span>
            </span>
            <span className="block truncate text-[10px] text-muted">{t("writing.workspace.mini.sub")}</span>
          </span>
        </Link>
      </div>
    </aside>
  );
}
