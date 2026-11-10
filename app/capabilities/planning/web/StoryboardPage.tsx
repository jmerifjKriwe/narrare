import { Link, useSearch } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { t as translate, useTranslation, type MessageKey } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useNovelsQuery } from "@shell/lib/query";
import { ActionMenu } from "@shell/ui/Menu";
import { Notice } from "@shell/ui/Notice";
import { Row } from "@shell/ui/Row";
import { stageName } from "./stageNames";

type StoryboardChapter = components["schemas"]["StoryboardChapterRead"];
type StoryboardStage = components["schemas"]["StoryboardStageRead"];
type Storyboard = components["schemas"]["StoryboardRead"];
type Remap = components["schemas"]["RemapRead"];

/** The canvas never renders more cards than this: a longer storyboard
 *  states its size beside the slice it shows, and the rest stays one
 *  query away. */
export const CHAPTER_LIMIT = 200;

/** The structures the switcher offers, in the backend registry's own ids. */
const STRUCTURES = ["three-act", "heros-journey"] as const;

/**
 * The seam the canvas reads through: the page renders only what this
 * returns, and the return names the one honest split — an answer that is
 * not "ok" is `failed`, never an empty board, because "no chapters" is a
 * fact only a reachable service can claim (the timeline read's F14
 * precedent). An ok answer with data passes through untouched.
 * Exported for the unit test.
 */
export function readStoryboard(result: {
  data?: Storyboard;
  response: { ok: boolean };
}): { kind: "ok"; board: Storyboard } | { kind: "failed" } {
  if (!result.response.ok || result.data === undefined) return { kind: "failed" };
  return { kind: "ok", board: result.data };
}

/**
 * The sync badge's wording, beside its first consumer — the knowledge
 * extraction's TYPE_KEYS precedent. A status outside the sync rule falls
 * back to the raw status instead of crashing the render.
 */
const SYNC_KEYS = {
  empty: "storyboard.sync.empty",
  planned: "storyboard.sync.planned",
  deviated: "storyboard.sync.deviated",
  completed: "storyboard.sync.completed",
  on_track: "storyboard.sync.on_track",
} as const;

function syncLabel(t: typeof translate, status: string): string {
  return status in SYNC_KEYS ? t(SYNC_KEYS[status as keyof typeof SYNC_KEYS]) : status;
}

/** The server's refusal, when it named one — the PlanningErrorRead detail. */
function refusalDetail(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null | undefined)?.detail;
  return typeof detail === "string" && detail !== "" ? detail : null;
}

/**
 * The storyboard canvas as a full page: the novel's chapters as cards in
 * one column per stage of its structure, in the aggregate's own order.
 * The novel arrives as the `?novel=` search param (the graph's sibling:
 * tolerant in, absent means the picker); a param naming nothing the read
 * returns degrades to the missing-novel state, never an error.
 */
export function StoryboardPage() {
  const t = useTranslation();
  // The tab's name: this page is "Storyboard" until it goes.
  usePageTitle(t("storyboard.heading"));
  const { novel: novelId } = useSearch({ from: "/planning/storyboard" });
  // A param naming no novel is no novel: the empty string is the absent
  // state, not a novel called "".
  const current = novelId === "" ? undefined : novelId;

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("storyboard.heading")}</h1>
      {current === undefined ? <NovelPicker /> : <NovelStoryboard novelId={current} />}
    </div>
  );
}

/** No novel named: the novels to board, one link each. */
function NovelPicker() {
  const t = useTranslation();
  const novels = useNovelsQuery();

  if (novels.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-6">
        {t("storyboard.loading")}
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
        {t("storyboard.loadFailed")}
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
    <nav aria-label={t("storyboard.pickNovel")} className="mt-6 flex flex-col gap-2">
      {rows.map((novel) => (
        <Link
          key={novel.id}
          to="/planning/storyboard"
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

/** The named novel's canvas: its chapters standing in their stages. */
function NovelStoryboard({ novelId }: { novelId: string }) {
  const t = useTranslation();
  const boardQuery = useQuery({
    queryKey: ["planning", "storyboard", novelId],
    queryFn: async () => {
      const answer = await client.GET("/api/planning/novels/{novel_id}/storyboard", {
        params: { path: { novel_id: novelId } },
      });
      const read = readStoryboard(answer);
      if (read.kind === "failed") {
        const error = new Error(
          `storyboard unavailable: ${answer.response.status}`,
        ) as BoardError;
        error.status = answer.response.status;
        throw error;
      }
      return read.board;
    },
  });
  // The optimistic ground a move stands on while its PUT is out: the
  // chapter renders in the chosen column at once, and a refused PUT lifts
  // the override — the card snaps back to the server's column — beside
  // the Notice that carries the retry.
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  // A move in flight: cards stop being draggable and a second drop lands
  // nowhere, so one chapter never carries two PUTs at once.
  const [pending, setPending] = useState(false);
  // The column under the pointer during a drag, for the visible drop target.
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [failed, setFailed] = useState<{
    chapterId: string;
    stageKey: string;
    detail: string;
  } | null>(null);

  async function reload() {
    await boardQuery.refetch();
  }

  async function moveChapter(chapterId: string, stageKey: string): Promise<void> {
    if (pending) return;
    setPending(true);
    setOverrides((previous) => ({ ...previous, [chapterId]: stageKey }));
    setFailed(null);
    try {
      const answer = await client.PUT("/api/planning/novels/{novel_id}/chapters/{chapter_id}/stage", {
        params: { path: { novel_id: novelId, chapter_id: chapterId } },
        body: { stage_key: stageKey },
      });
      if (!answer.response.ok) {
        setOverrides((previous) => {
          const next = { ...previous };
          delete next[chapterId];
          return next;
        });
        setFailed({
          chapterId,
          stageKey,
          detail: refusalDetail(answer.error) ?? t("planning.saveOffline"),
        });
        setPending(false);
        return;
      }
    } catch {
      // A service that does not answer is a refused write, not silence:
      // the override lifts and the refusal names the retry below.
      setOverrides((previous) => {
        const next = { ...previous };
        delete next[chapterId];
        return next;
      });
      setFailed({ chapterId, stageKey, detail: t("planning.saveOffline") });
      setPending(false);
      return;
    }
    // The write moved the server's truth: the override lifts and the
    // board re-asks, so no stale column stands in for the moved card.
    setOverrides((previous) => {
      const next = { ...previous };
      delete next[chapterId];
      return next;
    });
    try {
      await reload();
    } catch {
      // A refetch that rejects carries no error state of its own — the read
      // it tried to repeat keeps its cached answer — and every moveChapter
      // caller voids the move, so the rejection would leak as an unhandled
      // rejection. It ends here instead. Pending still clears below: the
      // canvas never wedges on a failed re-read.
    } finally {
      // A refetch that rejects must not wedge the canvas: pending clears
      // whether the re-read lands or not (the query's own error state
      // carries the failure to the retry beside it).
      setPending(false);
    }
  }

  // A drop's half of the one move path: the menu calls moveChapter, and so
  // does this — same optimistic override, same rollback, same Notice. A
  // drop onto the card's own column is a no-op, never a request.
  function dropChapterOnto(targetKey: string, chapterId: string, sourceKey: string): void {
    setDropTarget(null);
    if (pending || sourceKey === targetKey) return;
    void moveChapter(chapterId, targetKey);
  }

  if (boardQuery.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-6">
        {t("storyboard.loading")}
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
              to="/planning/storyboard"
              className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
            >
              {t("planning.changeNovel")}
            </Link>
          </p>
          <Notice tone="quiet" className="mt-6">
            {t("storyboard.novelMissing")}
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
        {t("storyboard.loadFailed")}
      </Notice>
    );
  }
  const board = boardQuery.data;
  const entries = board.stages.flatMap((column) => column.chapters ?? []);
  const total = entries.length;
  if (total === 0) {
    return (
      <>
        <p className="mt-2 text-body text-muted">
          <Link
            to="/planning/storyboard"
            className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("planning.changeNovel")}
          </Link>
        </p>
        {/* The honest empty: no chapters is a fact the service confirmed,
            and the next step stands beside it. */}
        <Notice tone="quiet" className="mt-6">
          {t("storyboard.noChapters")}
        </Notice>
      </>
    );
  }
  const shown = entries.slice(0, CHAPTER_LIMIT);
  return (
    <>
      <p className="mt-2 text-body text-muted">
        <Link
          to="/planning/storyboard"
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("planning.changeNovel")}
        </Link>
      </p>
      {failed !== null ? (
        <Notice
          tone="danger"
          live="alert"
          className="mt-3"
          action={
            <Button
              variant="secondary"
              onClick={() => void moveChapter(failed.chapterId, failed.stageKey)}
            >
              {t("planning.retry")}
            </Button>
          }
        >
          {t("planning.saveFailed", { detail: failed.detail })}
        </Notice>
      ) : null}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-label text-muted">{t("storyboard.structure")}</span>
        <span className="font-semibold text-body">{structureName(t, board.structure_id)}</span>
        <Dialog
          title={t("storyboard.remapTitle")}
          triggerLabel={t("storyboard.previewChange")}
        >
          {(close) => (
            <RemapForm board={board} novelId={novelId} close={close} onApplied={reload} />
          )}
        </Dialog>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {board.stages.map((column) => (
          <StageColumn
            key={column.key}
            column={column}
            novelId={novelId}
            entries={shown.filter(
              (entry) => (overrides[entry.chapter_id] ?? entry.stage_key) === column.key,
            )}
            stages={board.stages}
            pending={pending}
            isDropTarget={dropTarget === column.key}
            onHighlightStage={setDropTarget}
            onMove={moveChapter}
            onDropChapter={dropChapterOnto}
          />
        ))}
      </div>
      {total > CHAPTER_LIMIT ? (
        <Notice tone="info" className="mt-3">
          {t("storyboard.showingLimited", { shown: shown.length, total })}
        </Notice>
      ) : null}
    </>
  );
}

/** The structure's name: the catalog's when it holds one, the id else. */
function structureName(t: typeof translate, structureId: string): string {
  const key = `storyboard.structure.${structureId}`;
  if (structureId === "three-act" || structureId === "heros-journey") {
    return t(key as MessageKey);
  }
  return structureId;
}

/** The drag payload's wire type: the card's id and the column it stands in. */
const DRAG_MIME = "application/x-storyboard-chapter";

/** What a drop carries, or null when the gesture brought no chapter. */
function readDragPayload(transfer: DataTransfer | null): {
  chapterId: string;
  stageKey: string;
} | null {
  if (transfer === null) return null;
  const raw =
    transfer.getData(DRAG_MIME) !== ""
      ? transfer.getData(DRAG_MIME)
      : transfer.getData("text/plain");
  if (raw === "") return null;
  try {
    const parsed = JSON.parse(raw) as { chapterId?: unknown; stageKey?: unknown };
    if (typeof parsed.chapterId !== "string" || typeof parsed.stageKey !== "string") return null;
    return { chapterId: parsed.chapterId, stageKey: parsed.stageKey };
  } catch {
    return null;
  }
}

/** One stage's column: the chapters standing in it, in aggregate order. */
function StageColumn({
  column,
  novelId,
  entries,
  stages,
  pending,
  isDropTarget,
  onHighlightStage,
  onMove,
  onDropChapter,
}: {
  column: StoryboardStage;
  novelId: string;
  entries: StoryboardChapter[];
  stages: StoryboardStage[];
  pending: boolean;
  isDropTarget: boolean;
  onHighlightStage: (stageKey: string | null) => void;
  onMove: (chapterId: string, stageKey: string) => Promise<void>;
  onDropChapter: (targetKey: string, chapterId: string, sourceKey: string) => void;
}) {
  const t = useTranslation();
  const headingId = useId();

  return (
    <section
      aria-labelledby={`${headingId}-stage`}
      className={`min-w-0${isDropTarget ? " rounded ring-2 ring-focus" : ""}`}
      data-drop-active={isDropTarget ? "true" : undefined}
      onDragOver={(event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        if (!pending) onHighlightStage(column.key);
      }}
      onDragLeave={() => onHighlightStage(null)}
      // A cancelled drag (Esc, or a drop outside after re-enter without
      // leave) never fires leave or drop: the end clears the ring instead.
      onDragEnd={() => onHighlightStage(null)}
      onDrop={(event) => {
        event.preventDefault();
        const payload = readDragPayload(event.dataTransfer);
        if (payload === null) {
          onHighlightStage(null);
          return;
        }
        onDropChapter(column.key, payload.chapterId, payload.stageKey);
      }}
    >
      <h2 id={`${headingId}-stage`} className="text-label font-semibold text-muted">
        {stageName(t, column.title_key, column.key)}
      </h2>
      {entries.length === 0 ? null : (
        <ul className="mt-1 flex flex-col gap-2">
          {entries.map((entry) => (
            <li key={entry.chapter_id}>
              <ChapterCard
                entry={entry}
                novelId={novelId}
                stageKey={column.key}
                stages={stages}
                pending={pending}
                onMove={onMove}
                onClearHighlight={() => onHighlightStage(null)}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** One chapter: its title, its size, how the writing follows the plan. */
function ChapterCard({
  entry,
  novelId,
  stageKey,
  stages,
  pending,
  onMove,
  onClearHighlight,
}: {
  entry: StoryboardChapter;
  novelId: string;
  /** The column the card stands in: the drag payload's source. */
  stageKey: string;
  stages: StoryboardStage[];
  /** A move in flight: the card stops being draggable until it lands. */
  pending: boolean;
  onMove: (chapterId: string, stageKey: string) => Promise<void>;
  /** The drag is over (dropped or cancelled): the column ring goes out. */
  onClearHighlight: () => void;
}) {
  const t = useTranslation();
  const name = entry.title.trim() === "" ? t("planning.untitledChapter") : entry.title;

  return (
    <Row
      as="div"
      role="group"
      aria-label={name}
      flush
      className="h-auto flex-col items-stretch gap-1 py-2"
      draggable={!pending}
      onDragStart={(event) => {
        // A drag that carries nothing is not a move: guard the bag the
        // way the drop side guards its read.
        const transfer: DataTransfer | null | undefined = event.dataTransfer;
        if (transfer == null) return;
        transfer.setData(
          DRAG_MIME,
          JSON.stringify({ chapterId: entry.chapter_id, stageKey }),
        );
        transfer.effectAllowed = "move";
      }}
      onDragEnd={onClearHighlight}
    >
      <div className="flex flex-wrap items-baseline gap-x-2">
        {/* The card's title is a navigation, never an action: a Link to
            the chapter in the workspace, painted as the card's heading —
            Button renders a <button> and cannot carry a destination. */}
        <Link
          to="/novels/$id"
          params={{ id: novelId }}
          search={{ chapter: entry.chapter_id }}
          className="min-w-0 flex-1 text-body font-semibold underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {name}
        </Link>
        <span className="shrink-0 text-label text-muted">
          {t("storyboard.words", { count: entry.word_count })}
        </span>
        <span className="shrink-0 text-label text-muted">{syncLabel(t, entry.sync_status)}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {/* Moving is a menu first: each card carries the whole stage list
            as its one move control, and the menu stays the keyboard path.
            Pointer dragging is the second path onto the same move — a drop
            calls the same moveChapter, with the same optimistic update and
            the same rollback and retry. */}
        <ActionMenu
          label={t("storyboard.move")}
          triggerAriaLabel={t("storyboard.moveFor", { title: name })}
          items={stages.map((column) => ({
            id: column.key,
            label: stageName(t, column.title_key, column.key),
            disabled: column.key === entry.stage_key,
            onSelect: () => void onMove(entry.chapter_id, column.key),
          }))}
        />
      </div>
    </Row>
  );
}

/**
 * The structure change: the target, the previewed moves, the confirm.
 * Preview first (`confirm: false` writes nothing), apply only on the
 * confirm (`confirm: true` writes exactly the previewed mapping) — the
 * dialog closes after the board has re-read onto the new structure.
 */
function RemapForm({
  board,
  novelId,
  close,
  onApplied,
}: {
  board: Storyboard;
  novelId: string;
  close: () => void;
  onApplied: () => Promise<void>;
}) {
  const t = useTranslation();
  const [target, setTarget] = useState<string | null>(null);
  const [preview, setPreview] = useState<Remap | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const byChapter = new Map(
    board.stages
      .flatMap((column) => column.chapters ?? [])
      .map((entry) => [entry.chapter_id, entry]),
  );

  async function choose(structureId: string): Promise<void> {
    if (busy) return;
    setTarget(structureId);
    setPreview(null);
    setFailed(null);
    if (structureId === board.structure_id) return;
    setBusy(true);
    try {
      const answer = await client.POST("/api/planning/novels/{novel_id}/remap", {
        params: { path: { novel_id: novelId } },
        body: { structure_id: structureId, confirm: false },
      });
      if (!answer.response.ok) {
        setFailed(refusalDetail(answer.error) ?? t("planning.saveOffline"));
        return;
      }
      setPreview(answer.data ?? null);
    } catch {
      setFailed(t("planning.saveOffline"));
    } finally {
      setBusy(false);
    }
  }

  async function apply(): Promise<void> {
    if (busy || target === null || target === board.structure_id) return;
    setBusy(true);
    setFailed(null);
    try {
      const answer = await client.POST("/api/planning/novels/{novel_id}/remap", {
        params: { path: { novel_id: novelId } },
        body: { structure_id: target, confirm: true },
      });
      if (!answer.response.ok) {
        setFailed(refusalDetail(answer.error) ?? t("planning.saveOffline"));
        return;
      }
    } catch {
      setFailed(t("planning.saveOffline"));
      return;
    } finally {
      setBusy(false);
    }
    await onApplied();
    close();
  }

  return (
    <div className="mt-4 flex flex-col gap-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("storyboard.structure")}>
        {STRUCTURES.map((structureId) => (
          <Button
            key={structureId}
            variant="secondary"
            aria-pressed={target === structureId || (target === null && structureId === board.structure_id)}
            onClick={() => void choose(structureId)}
          >
            {structureName(t, structureId)}
          </Button>
        ))}
      </div>
      {target !== null && target !== board.structure_id ? (
        <p className="text-body text-muted">{t("storyboard.remapIntro")}</p>
      ) : null}
      {preview !== null && target !== null && target !== board.structure_id ? (
        preview.mapping.length === 0 ? (
          <Notice tone="quiet">{t("storyboard.noMoves")}</Notice>
        ) : (
          <ul className="flex flex-col gap-1">
            {preview.mapping.map((move) => {
              const entry = byChapter.get(move.chapter_id);
              const name =
                entry === undefined || entry.title.trim() === ""
                  ? t("planning.untitledChapter")
                  : entry.title;
              return (
                <li key={move.chapter_id} className="text-body">
                  {name}: {stageName(t, "", move.from_stage)} → {stageName(t, "", move.to_stage)}
                </li>
              );
            })}
          </ul>
        )
      ) : null}
      {failed !== null ? (
        <Notice
          tone="danger"
          live="alert"
          action={
            <Button variant="secondary" onClick={() => void apply()}>
              {t("planning.retry")}
            </Button>
          }
        >
          {t("planning.saveFailed", { detail: failed })}
        </Notice>
      ) : null}
      <div className="mt-2 flex justify-end gap-3">
        <Button onClick={close}>{t("planning.cancel")}</Button>
        <Button
          variant="primary"
          disabled={busy || preview === null || target === board.structure_id}
          onClick={() => void apply()}
        >
          {t("storyboard.remapConfirm")}
        </Button>
      </div>
    </div>
  );
}
