/**
 * The explorer column (W4 Tasks 11/13) — the scene-centric draft's 280px
 * left column on the shell's tokens: the identity card, the daily ring,
 * the tension card, the scene tree and the shelf mini-card. The tree's
 * CRUD doors are LIVE (Task 13): create chapter/scene, the row menus
 * (rename/edit, delete — the shelf quick menu's discipline, the drafts
 * draw no tree affordance of their own), drag reorder at both levels and
 * the honest notice under the tree. The column itself writes nothing —
 * every action asks the page through a callback; the page owns the
 * mutations, the selection and the optimistic order.
 *
 * Honest readings of the draft (the gap doc records them):
 * - The daily ring is REAL: the activity aggregate's goal fields — the
 *   same source the shelf banner reads (today_words vs daily_goal_words,
 *   goal_remaining, goal_met). Unset keeps the honest neutral; the inline
 *   setter affordance (D20) is LIVE (Task 19) — it opens the goal dialog
 *   on the atelier's daily goal. The identity card carries the
 *   book-settings door (the dialog's opener — the draft draws none).
 * - The tension card's stage label is REAL (the planning storyboard's own
 *   title key, resolved against the catalog); the curve is the drafted
 *   PLACEHOLDER (INTERIM #879 — no tension data exists, the draft's curve
 *   and figures never ship as data). The label row carries the real scene
 *   codes: first, active, last.
 * - The tree's status dots are NEUTRAL (INTERIM #873 — no chapter/scene
 *   status field exists): faint ink, terracotta for the active scene. The
 *   active marker is the last-edited scene (updated_at) — the hero door's
 *   own rule.
 * - The draft's drag handles are REAL now (Task 11 omitted them as false
 *   affordance): the scene rows carry the drawn `drag_indicator` (faint
 *   until hover, always on the active row); the chapter header carries
 *   the same grip one level up — the draft draws no chapter grip, the
 *   brief's chapter reorder owns the extension. The focused grip moves
 *   one step with the arrow keys (the keyboard's own drag — HTML5 drag
 *   is mouse-only); a scene never crosses its chapter (spec §12: the
 *   cross-chapter move is not drafted, just absent).
 * - Word counts are the rows' own, tabular; long titles truncate with the
 *   full title in the tooltip (Kachel 5); many chapters scroll (Kachel 6).
 */

import { Link } from "@tanstack/react-router";
import type { UseQueryResult } from "@tanstack/react-query";
import { useRef, useState, type DragEvent } from "react";

import type { Activity, Chapter, Novel, Scene, Storyboard } from "@shell/lib/api/client";
import { BookCover, PALETTE } from "@shell/lib/cover/BookCover";
import { coverModel } from "@shell/lib/cover/cover";
import { formatNumber } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { progress } from "./shelf";
import { Bone } from "./ShelfStates";
import { TreeMenu } from "./TreeMenu";
import {
  movedIds,
  sceneTitle,
  stageTitleKey,
  tensionCodes,
  type SceneEntry,
  type TreeNotice,
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

/** The identity card — the real cover chip, title, author, genre, and
 *  the book-settings door (Task 19 — the draft draws no opener; the
 *  card is the book's identity face, the dialog's natural home). */
function IdentityCard({ novel, onOpenSettings }: { novel: Novel; onOpenSettings: () => void }) {
  const t = useTranslation();
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
      <button
        type="button"
        id="book-settings-door"
        onClick={onOpenSettings}
        aria-label={t("writing.workspace.identity.settings")}
        title={t("writing.workspace.identity.settings")}
        className={`shrink-0 rounded p-1 text-muted transition-colors hover:bg-surface-container-low hover:text-foreground ${FOCUS}`}
      >
        <Icon name="tune" size={13} />
      </button>
    </div>
  );
}

/** The daily ring — the aggregate's own goal fields, the banner's source.
 *  The setter affordance is LIVE (Task 19, D20): it asks the page, which
 *  opens the goal dialog on the atelier's daily goal. */
function DailyRing({ activity, onEditGoal }: { activity: UseQueryResult<Activity>; onEditGoal: () => void }) {
  const t = useTranslation();
  const data = activity.data;
  const result = data != null ? progress(data.today_words, data.daily_goal_words) : null;
  return (
    <div data-testid="explorer-ring" className="rounded-lg border border-border bg-panel p-3 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <span className={EYEBROW}>{t("writing.workspace.ring.title")}</span>
        {/* D20's inline setter affordance — LIVE (Task 19): the goal
            dialog writes the atelier's daily goal. */}
        <button
          type="button"
          id="explorer-goal-door"
          onClick={onEditGoal}
          aria-label={t("writing.workspace.ring.edit")}
          title={t("writing.workspace.ring.edit")}
          className={`rounded p-0.5 text-muted transition-colors hover:text-foreground ${FOCUS}`}
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

/** The two levels the tree reorders — the chapter rail and a chapter's
 *  scenes (within-chapter only, spec §12). */
type Level = "chapter" | "scene";

/** The drag in flight — what is lifted, and (for a scene) its chapter. */
interface DragState {
  level: Level;
  id: string;
  chapterId: string | null;
}

/**
 * The tree's drag contract — the column owns the state, the rows ask
 * through it. `over` marks the insertion edge (the target's midpoint
 * decides before/after), `finish` computes the whole permutation and asks
 * the page; `move` is the keyboard's one-step drag on the focused grip.
 * A busy reorder holds every path — one arrangement on the wire at a time.
 */
interface DragContract {
  drag: DragState | null;
  drop: { id: string; before: boolean } | null;
  busy: boolean;
  start: (level: Level, id: string, chapterId: string | null) => void;
  over: (event: DragEvent, level: Level, targetId: string, chapterId: string | null) => void;
  finish: (
    event: DragEvent,
    level: Level,
    targetId: string,
    chapterId: string | null,
    ids: readonly string[],
  ) => void;
  end: () => void;
  move: (level: Level, id: string, chapterId: string | null, ids: readonly string[], direction: -1 | 1) => void;
}

/** The insertion edge — an inset rule on the target's top or bottom, no
 *  layout shift (the shadow paints inside the row's own box). */
function edgeClass(drop: { id: string; before: boolean } | null, id: string): string {
  if (drop?.id !== id) return "";
  return drop.before
    ? "shadow-[inset_0_2px_0_0_var(--color-primary)]"
    : "shadow-[inset_0_-2px_0_0_var(--color-primary)]";
}

/** The draft's `drag_indicator` grip — draggable, and a real button: the
 *  focused grip steps one row per arrow key (the keyboard's own drag, no
 *  invented geometry). Faint until hover or focus on an inactive row, the
 *  draft's own calm; always visible on the active scene. */
function DragGrip({
  label,
  level,
  id,
  chapterId,
  ids,
  contract,
  visible,
  active,
}: {
  label: string;
  level: Level;
  id: string;
  chapterId: string | null;
  ids: readonly string[];
  contract: DragContract;
  visible: boolean;
  active: boolean;
}) {
  const t = useTranslation();
  return (
    <button
      type="button"
      draggable
      aria-label={label}
      title={t("writing.workspace.tree.moveHint")}
      onDragStart={(event) => {
        event.dataTransfer.setData("text/plain", id);
        event.dataTransfer.effectAllowed = "move";
        contract.start(level, id, chapterId);
      }}
      onDragEnd={contract.end}
      onKeyDown={(event) => {
        if (event.key === "ArrowUp") {
          event.preventDefault();
          contract.move(level, id, chapterId, ids, -1);
        } else if (event.key === "ArrowDown") {
          event.preventDefault();
          contract.move(level, id, chapterId, ids, 1);
        }
      }}
      className={`shrink-0 cursor-grab rounded p-0.5 transition-opacity active:cursor-grabbing ${FOCUS} ${
        active ? "text-primary/70" : "text-muted"
      } ${visible ? "" : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"}`}
    >
      <Icon name="dragIndicator" size={13} />
    </button>
  );
}

/** One scene row — the neutral dot (#873), the label, the tabular count,
 *  the draft's grip and the row's options menu. The select button keeps
 *  the row's name; grip and menu are siblings, never nested controls. */
function SceneRow({
  entry,
  active,
  contract,
  sceneIds,
  onSelect,
  onEdit,
  onDelete,
}: {
  entry: SceneEntry;
  active: boolean;
  contract: DragContract;
  sceneIds: readonly string[];
  onSelect: (sceneId: string) => void;
  onEdit: (entry: SceneEntry, openerId: string) => void;
  onDelete: (entry: SceneEntry, openerId: string) => void;
}) {
  const t = useTranslation();
  const { scene, chapter } = entry;
  const label = t("writing.workspace.tree.sceneLabel", {
    number: scene.position,
    title: sceneTitle(scene.title, t("writing.workspace.untitledScene")),
  });
  return (
    <div
      data-testid={`tree-scene-${scene.id}`}
      onDragOver={(event) => contract.over(event, "scene", scene.id, chapter.id)}
      onDrop={(event) => contract.finish(event, "scene", scene.id, chapter.id, sceneIds)}
      className={`group flex items-center gap-1 rounded border px-2 py-1.5 transition-colors ${
        active
          ? "border-primary/30 bg-primary/10 shadow-sm"
          : "border-transparent hover:bg-surface-container-low"
      } ${edgeClass(contract.drop, scene.id)} ${contract.drag?.id === scene.id ? "opacity-50" : ""}`}
    >
      <DragGrip
        label={t("writing.workspace.tree.moveScene", { number: scene.position, chapter: chapter.position + 1 })}
        level="scene"
        id={scene.id}
        chapterId={chapter.id}
        ids={sceneIds}
        contract={contract}
        visible={active}
        active={active}
      />
      <button
        type="button"
        onClick={() => onSelect(scene.id)}
        aria-current={active ? "true" : undefined}
        className={`flex min-w-0 flex-1 items-center justify-between rounded text-left ${FOCUS} ${
          active ? "font-medium text-primary" : "text-muted hover:text-foreground"
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
          {t("writing.workspace.tree.words", { count: scene.word_count })}
        </span>
      </button>
      <TreeMenu
        label={t("writing.workspace.tree.sceneOptions")}
        editLabel={t("writing.workspace.tree.editScene")}
        onEdit={(openerId) => onEdit(entry, openerId)}
        onDelete={(openerId) => onDelete(entry, openerId)}
      />
    </div>
  );
}

/** One chapter card — the header (chevron + select + count + grip + menu)
 *  and the scenes. The card is the chapter level's drop target; the grip
 *  sits at the header's right (the draft draws no chapter grip — the
 *  brief's chapter reorder owns the extension, the drawn left anatomy
 *  stands). */
function ChapterCard({
  chapter,
  scenes,
  scenesPending,
  scenesError,
  collapsed,
  activeSceneId,
  contract,
  chapterIds,
  onToggle,
  onSelect,
  onSelectScene,
  onEditChapter,
  onDeleteChapter,
  onEditScene,
  onDeleteScene,
}: {
  chapter: Chapter;
  scenes: readonly Scene[];
  scenesPending: boolean;
  scenesError: boolean;
  collapsed: boolean;
  activeSceneId: string | null;
  contract: DragContract;
  chapterIds: readonly string[];
  onToggle: (chapterId: string) => void;
  onSelect: (chapterId: string) => void;
  onSelectScene: (sceneId: string) => void;
  onEditChapter: (chapter: Chapter, openerId: string) => void;
  onDeleteChapter: (chapter: Chapter, openerId: string) => void;
  onEditScene: (entry: SceneEntry, openerId: string) => void;
  onDeleteScene: (entry: SceneEntry, openerId: string) => void;
}) {
  const t = useTranslation();
  const number = chapter.position + 1;
  const name = t("writing.workspace.tree.chapterName", {
    number,
    title: sceneTitle(chapter.title, t("writing.workspace.untitledChapter")),
  });
  const ordered = [...scenes].sort((a, b) => a.position - b.position);
  const sceneIds = ordered.map((scene) => scene.id);
  return (
    <div
      data-testid={`tree-chapter-${chapter.id}`}
      onDragOver={(event) => contract.over(event, "chapter", chapter.id, null)}
      onDrop={(event) => contract.finish(event, "chapter", chapter.id, null, chapterIds)}
      className={`overflow-hidden rounded-lg border border-border bg-panel ${edgeClass(contract.drop, chapter.id)} ${
        contract.drag?.id === chapter.id ? "opacity-50" : ""
      }`}
    >
      <div className="group flex items-center justify-between gap-1 border-b border-border bg-surface-container-low/50 px-2.5 py-2">
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
        <div className="flex shrink-0 items-center gap-1">
          <span className="font-mono text-[10px] tabular-nums text-muted">
            {t("writing.workspace.tree.words", { count: chapter.word_count })}
          </span>
          <DragGrip
            label={t("writing.workspace.tree.moveChapter", { number })}
            level="chapter"
            id={chapter.id}
            chapterId={null}
            ids={chapterIds}
            contract={contract}
            visible={false}
            active={false}
          />
          <TreeMenu
            label={t("writing.workspace.tree.chapterOptions")}
            editLabel={t("writing.workspace.tree.rename")}
            onEdit={(openerId) => onEditChapter(chapter, openerId)}
            onDelete={(openerId) => onDeleteChapter(chapter, openerId)}
          />
        </div>
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
          ) : ordered.length === 0 ? (
            /* D16's real state — the chapter stands, no scene invented. */
            <p className="px-2 py-1.5 pl-5 text-[10px] italic text-muted">
              {t("writing.workspace.tree.emptyChapter")}
            </p>
          ) : (
            ordered.map((scene) => (
              <SceneRow
                key={scene.id}
                entry={{ scene, chapter }}
                active={scene.id === activeSceneId}
                contract={contract}
                sceneIds={sceneIds}
                onSelect={onSelectScene}
                onEdit={onEditScene}
                onDelete={onDeleteScene}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

/** The honest notice under the tree — the shelf quick menu's gentle error
 *  line: the loss-free message (or the conflict's current-truth note), the
 *  retry that re-runs the very ask, and the dismissal. */
function NoticeLine({
  notice,
  onRetry,
  onDismiss,
}: {
  notice: TreeNotice;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  const t = useTranslation();
  const messageKey = {
    createChapterFailed: "writing.workspace.crud.createChapterError",
    createSceneFailed: "writing.workspace.crud.createSceneError",
    reorderConflict: "writing.workspace.crud.reorderConflict",
    reorderFailed: "writing.workspace.crud.reorderError",
  } as const;
  return (
    <div
      data-testid="explorer-notice"
      role="alert"
      className="rounded-lg border border-rule border-l-2 border-l-danger bg-surface-container-lowest p-2.5 shadow-sm"
    >
      <div className="flex items-start gap-1.5">
        <span className="mt-0.5 shrink-0 text-danger">
          <Icon name="warning" size={14} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-meta leading-tight text-foreground">{t(messageKey[notice.kind])}</p>
          <button
            type="button"
            onClick={onRetry}
            className={`mt-1 inline-flex items-center gap-1 text-meta font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
          >
            {t("writing.shelf.error.retry")}
            <Icon name="refresh" size={12} />
          </button>
        </div>
        <button
          type="button"
          aria-label={t("writing.workspace.crud.noticeClose")}
          onClick={onDismiss}
          className={`shrink-0 rounded p-0.5 text-muted transition-colors hover:text-foreground ${FOCUS}`}
        >
          <Icon name="cross" size={12} />
        </button>
      </div>
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
  onCreateChapter,
  onCreateScene,
  onEditChapter,
  onEditScene,
  onDeleteChapter,
  onDeleteScene,
  onReorderChapters,
  onReorderScenes,
  reorderBusy,
  createBusy,
  notice,
  onNoticeRetry,
  onNoticeDismiss,
  onOpenSettings,
  onEditGoal,
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
  /** The create doors — the page owns the write and the selection move. */
  onCreateChapter: () => void;
  onCreateScene: (chapterId: string) => void;
  /** The row menus' hand-offs — the page opens the dialog; the opener id
   *  is the menu trigger's, the dialog's focus return. */
  onEditChapter: (chapter: Chapter, openerId: string) => void;
  onEditScene: (entry: SceneEntry, openerId: string) => void;
  onDeleteChapter: (chapter: Chapter, openerId: string) => void;
  onDeleteScene: (entry: SceneEntry, openerId: string) => void;
  /** The whole permutation the drag asks for — the page writes it into
   *  the cache optimistically and PUTs the whole set. */
  onReorderChapters: (ids: string[]) => void;
  onReorderScenes: (chapterId: string, ids: string[]) => void;
  reorderBusy: boolean;
  createBusy: boolean;
  notice: TreeNotice | null;
  onNoticeRetry: () => void;
  onNoticeDismiss: () => void;
  /** The settings doors (Task 19) — the identity card's book-settings
   *  door and the ring's daily-goal setter; the page owns the dialogs. */
  onOpenSettings: () => void;
  onEditGoal: () => void;
  activity: UseQueryResult<Activity>;
  storyboard: UseQueryResult<Storyboard>;
}) {
  const t = useTranslation();
  const active = entries.find((entry) => entry.scene.id === activeSceneId) ?? null;
  const monogram = coverModel({ title: novel.title, genre: novel.genre, size: "mini" });
  const palette = PALETTE[monogram.channel];

  // The drag state — the column owns it, the rows ask through the
  // contract. The LOGIC reads refs: a drag's events can land in one task
  // (the browser's native sequence spans tasks, but a synthetic dispatch
  // may not), and a state read would see the pre-drag render. The state
  // mirrors the refs for the paint alone — the lifted row's dim, the
  // insertion edge.
  const dragRef = useRef<DragState | null>(null);
  const dropRef = useRef<{ id: string; before: boolean } | null>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [drop, setDrop] = useState<{ id: string; before: boolean } | null>(null);
  const chapterIds = chapters.map((chapter) => chapter.id);

  const contract: DragContract = {
    drag,
    drop,
    busy: reorderBusy,
    start: (level, id, chapterId) => {
      if (reorderBusy) return;
      dragRef.current = { level, id, chapterId };
      setDrag(dragRef.current);
    },
    over: (event, level, targetId, chapterId) => {
      const lifted = dragRef.current;
      if (lifted === null || lifted.level !== level) return;
      if (level === "scene" && lifted.chapterId !== chapterId) return;
      if (lifted.id === targetId) {
        dropRef.current = null;
        setDrop(null);
        return;
      }
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      const rect = event.currentTarget.getBoundingClientRect();
      const before = event.clientY < rect.top + rect.height / 2;
      if (dropRef.current?.id !== targetId || dropRef.current.before !== before) {
        dropRef.current = { id: targetId, before };
        setDrop(dropRef.current);
      }
    },
    finish: (event, level, targetId, chapterId, ids) => {
      const lifted = dragRef.current;
      if (lifted === null || lifted.level !== level) return;
      if (level === "scene" && lifted.chapterId !== chapterId) return;
      event.preventDefault();
      const edge = dropRef.current;
      const before = edge?.id === targetId ? edge.before : false;
      const next = movedIds(ids, lifted.id, targetId, before);
      dragRef.current = null;
      dropRef.current = null;
      setDrag(null);
      setDrop(null);
      // The stored order unchanged is no arrangement — no write owed.
      if (next.join("\u0000") === ids.join("\u0000")) return;
      if (level === "chapter") onReorderChapters(next);
      else if (chapterId !== null) onReorderScenes(chapterId, next);
    },
    end: () => {
      dragRef.current = null;
      dropRef.current = null;
      setDrag(null);
      setDrop(null);
    },
    move: (level, id, chapterId, ids, direction) => {
      if (reorderBusy) return;
      const at = ids.indexOf(id);
      const target = ids[at + direction];
      if (at < 0 || target === undefined) return;
      const next = movedIds(ids, id, target, direction === -1);
      if (level === "chapter") onReorderChapters(next);
      else if (chapterId !== null) onReorderScenes(chapterId, next);
    },
  };

  // The scene door's target: the active chapter (the resolved one — the
  // last-edited fallback when no selection stands). The tree renders only
  // with chapters, so the fallback always names a row.
  const sceneTarget = activeChapterId ?? chapterIds[0] ?? null;

  return (
    <aside
      aria-label={t("writing.workspace.explorer.label")}
      className="flex h-full w-[280px] shrink-0 flex-col border-r border-border bg-surface-container-low/60 text-meta"
    >
      <div data-testid="explorer-body" className="flex-1 space-y-3 overflow-y-auto p-3">
        <IdentityCard novel={novel} onOpenSettings={onOpenSettings} />
        <DailyRing activity={activity} onEditGoal={onEditGoal} />
        <TensionCard
          storyboard={storyboard}
          entries={entries}
          active={active}
          activeChapterId={activeChapterId}
        />
        {chapters.length === 0 ? (
          /* Kachel 3 — the empty book's invitation, the first chapter's
             door live (D16: the new chapter opens on the empty-chapter
             face, the canonical first-scene invitation). */
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
              disabled={createBusy}
              onClick={onCreateChapter}
              className={`mt-3 flex w-full items-center justify-center gap-1 rounded bg-primary px-2 py-1.5 text-[11px] font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${createBusy ? "cursor-not-allowed opacity-50" : ""}`}
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
                contract={contract}
                chapterIds={chapterIds}
                onToggle={onToggleChapter}
                onSelect={onSelectChapter}
                onSelectScene={onSelectScene}
                onEditChapter={onEditChapter}
                onDeleteChapter={onDeleteChapter}
                onEditScene={onEditScene}
                onDeleteScene={onDeleteScene}
              />
            ))}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                disabled={createBusy}
                onClick={onCreateChapter}
                className={`flex items-center justify-center gap-1 rounded border border-border bg-panel px-2 py-1.5 text-[11px] text-muted transition-colors hover:bg-surface-container-low hover:text-foreground ${FOCUS} ${createBusy ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <Icon name="plus" size={12} />
                <span>{t("writing.workspace.tree.newChapter")}</span>
              </button>
              <button
                type="button"
                disabled={createBusy || sceneTarget === null}
                onClick={() => {
                  if (sceneTarget !== null) onCreateScene(sceneTarget);
                }}
                className={`flex items-center justify-center gap-1 rounded border border-border bg-panel px-2 py-1.5 text-[11px] text-muted transition-colors hover:bg-surface-container-low hover:text-foreground ${FOCUS} ${createBusy || sceneTarget === null ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <Icon name="plus" size={12} />
                <span>{t("writing.workspace.tree.newScene")}</span>
              </button>
            </div>
          </div>
        )}
        {notice !== null && <NoticeLine notice={notice} onRetry={onNoticeRetry} onDismiss={onNoticeDismiss} />}
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
