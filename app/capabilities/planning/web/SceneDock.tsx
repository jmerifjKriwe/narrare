import { useQuery } from "@tanstack/react-query";
import { useParams, useSearch } from "@tanstack/react-router";
import { useId, useRef, useState } from "react";

import { LeaveBlocker } from "@shell/components/LeaveBlocker";
import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { activeChapterFallback, queryClient, useChaptersQuery } from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Input } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Row } from "@shell/ui/Row";

type SceneRead = components["schemas"]["SceneRead"];

/** The scene lifecycle's three states, as the planning contract fixes them. */
type SceneStatus = "planned" | "in_progress" | "complete";

const STATUSES: readonly SceneStatus[] = ["planned", "in_progress", "complete"];

/** The status a scene advances to, if any — complete ends the lifecycle. */
const NEXT: Record<SceneStatus, SceneStatus | null> = {
  planned: "in_progress",
  in_progress: "complete",
  complete: null,
};

const STATUS_LABEL: Record<SceneStatus, MessageKey> = {
  planned: "planning.status.planned",
  in_progress: "planning.status.in_progress",
  complete: "planning.status.complete",
};

/** The dock's editable copy of one scene: the server's fields, no timestamps. */
type SceneDraft = {
  id: string;
  title: string;
  purpose: string;
  conflict: string;
  resolution: string;
  beats: string[];
  status: SceneStatus;
};

function toDraft(scene: SceneRead): SceneDraft {
  return {
    id: scene.id,
    title: scene.title,
    purpose: scene.purpose,
    conflict: scene.conflict,
    resolution: scene.resolution,
    beats: [...scene.beats],
    status: STATUSES.includes(scene.status as SceneStatus)
      ? (scene.status as SceneStatus)
      : "planned",
  };
}

/** Order-sensitive equality: a reorder is a change, like any edit. */
function sameScenes(left: SceneDraft[], right: SceneDraft[]): boolean {
  return (
    left.length === right.length &&
    left.every(
      (row, index) =>
        row.id === right[index]?.id &&
        row.title === right[index]?.title &&
        row.purpose === right[index]?.purpose &&
        row.conflict === right[index]?.conflict &&
        row.resolution === right[index]?.resolution &&
        row.status === right[index]?.status &&
        row.beats.length === (right[index]?.beats.length ?? -1) &&
        row.beats.every((beat, beatIndex) => beat === right[index]?.beats[beatIndex]),
    )
  );
}

/** The server's refusal, when it named one — the PlanningErrorRead detail. */
function refusalDetail(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null | undefined)?.detail;
  return typeof detail === "string" && detail !== "" ? detail : null;
}

/**
 * The scene plans beside the editor: the chapter's scenes in order, edited
 * as a whole list and saved with one PUT. The words the server last handed
 * this chapter are the snapshot; anything else is dirty and asks before it
 * is thrown away — the prompts editor's guard, not a third one.
 */
export function SceneDock() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  // The chapter is the editor's, and the selection's address is the URL: the
  // panel reads the workspace's own chapter param, and when the address
  // names none it falls back to the last chapter written in — the same
  // cached list the workbench reads, one truth for both. Nothing is written
  // back to the URL for it.
  const { chapter: chapterParam } = useSearch({ from: "/novels/$id" });
  const chapters = useChaptersQuery(novelId);
  const chapterId = chapterParam ?? activeChapterFallback(chapters.data ?? []);
  const headingId = useId();

  if (chapterId === null) {
    return (
      <section aria-labelledby={headingId}>
        <h3 id={headingId} className="text-body font-semibold">
          {t("planning.panelHeading")}
        </h3>
        <Notice tone="quiet" live="status" className="mt-2">
          {chapters.isPending ? t("planning.loading") : t("planning.noActiveChapter")}
        </Notice>
      </section>
    );
  }
  // The chapter owns the held rows: a switch remounts the list below, so
  // the previous chapter's edits can never stand in for the next
  // chapter's scenes — not even for a frame. The guard lives inside,
  // beside the dirt it watches, so a dirty list still asks first.
  return <SceneList key={chapterId} novelId={novelId} chapterId={chapterId} headingId={headingId} />;
}

/** The chapter's scene list: the held draft beside the server's answer. */
function SceneList({
  novelId,
  chapterId,
  headingId,
}: {
  novelId: string;
  chapterId: string;
  headingId: string;
}) {
  const t = useTranslation();

  const scenesQuery = useQuery({
    queryKey: ["planning", "scenes", novelId, chapterId],
    queryFn: async () => {
      const { data, response } = await client.GET(
        "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
        { params: { path: { novel_id: novelId, chapter_id: chapterId } } },
      );
      if (!response.ok || data === undefined) {
        throw new Error(`scenes unavailable: ${response.status}`);
      }
      return data;
    },
  });

  // The held draft beside the server's answer: null is clean, an array is
  // edited — compared field by field, so an edit undone is clean again.
  // The remount above owns the reset: held starts clean for every chapter.
  const [held, setHeld] = useState<SceneDraft[] | null>(null);
  const serverRows = scenesQuery.data?.scenes.map(toDraft) ?? null;
  const rows = held ?? serverRows ?? [];
  const dirty = held !== null && (serverRows === null || !sameScenes(held, serverRows));

  const [savePending, setSavePending] = useState(false);
  const [saveFailed, setSaveFailed] = useState<string | null>(null);

  // The leave guard's ask, lifted from the prompts page: one ask stands at
  // a time, and a dismissed dialog means "stay".
  const [guardOpen, setGuardOpen] = useState(false);
  const guardAnswer = useRef<((leave: boolean) => void) | null>(null);

  /** Resolve the standing ask; a dismissed dialog means "stay". */
  function settle(leave: boolean): void {
    const answer = guardAnswer.current;
    guardAnswer.current = null;
    setGuardOpen(false);
    answer?.(leave);
  }

  /** Ask before unsaved scenes are thrown away; a second ask while one stands is a no. */
  function askToLeave(): Promise<boolean> {
    if (guardAnswer.current !== null) return Promise.resolve(false);
    setGuardOpen(true);
    return new Promise<boolean>((resolve) => {
      guardAnswer.current = resolve;
    });
  }

  function replace(next: SceneDraft[]): void {
    setSaveFailed(null);
    setHeld(next);
  }

  /** Persist the whole list in its shown order; the refused save names itself. */
  async function save(): Promise<void> {
    if (!dirty || savePending) return;
    setSavePending(true);
    setSaveFailed(null);
    try {
      const { data, error, response } = await client.PUT(
        "/api/planning/novels/{novel_id}/chapters/{chapter_id}/scenes",
        {
          params: { path: { novel_id: novelId, chapter_id: chapterId } },
          body: {
            scenes: rows.map((row) => ({
              id: row.id,
              title: row.title,
              purpose: row.purpose,
              conflict: row.conflict,
              resolution: row.resolution,
              beats: row.beats,
              status: row.status,
            })),
          },
        },
      );
      if (response.ok && data !== undefined) {
        // The answer reaches the cache before the invalidation asks again:
        // the settled list is this key's truth at once, so no refetch can
        // remount the old order over it. The chapter's own stamp moved with
        // the write, so the rail's order and the shelf's hero refetch too.
        queryClient.setQueryData(["planning", "scenes", novelId, chapterId], data);
        void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
        void queryClient.invalidateQueries({ queryKey: ["novels"] });
        return;
      }
      setSaveFailed(refusalDetail(error) ?? t("planning.saveOffline"));
    } catch {
      // A rejected fetch has no response to inspect: the dock still says
      // so, in the same place a server-reachable refusal appears.
      setSaveFailed(t("planning.saveOffline"));
    } finally {
      setSavePending(false);
    }
  }

  function addScene(): void {
    replace([
      ...rows,
      {
        id: crypto.randomUUID(),
        title: "",
        purpose: "",
        conflict: "",
        resolution: "",
        beats: [],
        status: "planned",
      },
    ]);
  }

  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId} className="text-body font-semibold">
        {t("planning.panelHeading")}
      </h3>
      {scenesQuery.isPending ? (
        <Notice tone="quiet" live="status" className="mt-2">
          {t("planning.loading")}
        </Notice>
      ) : scenesQuery.isError ? (
        <Notice
          tone="danger"
          live="alert"
          className="mt-2"
          action={
            <Button variant="secondary" onClick={() => void scenesQuery.refetch()}>
              {t("planning.retry")}
            </Button>
          }
        >
          {t("planning.loadFailed")}
        </Notice>
      ) : (
        <>
          {rows.length === 0 ? (
            <Notice tone="quiet" className="mt-2">
              {t("planning.empty")}
            </Notice>
          ) : (
            <ul className="mt-2 flex flex-col">
              {rows.map((row, index) => {
                const name = row.title.trim() === "" ? t("planning.untitledScene") : row.title;
                const next = NEXT[row.status];
                return (
                  <li key={row.id}>
                    {/* The row owns its gutter here: the list stands on the
                        column's own inset, so a heading and the rows under
                        it start on one edge. A row with controls inside is
                        a div — a button in a button is invalid HTML — and
                        the stack (title above the deeds) leaves the
                        single-line control height behind, the GridList
                        precedent. */}
                    <Row
                      as="div"
                      role="group"
                      aria-label={name}
                      flush
                      className="h-auto min-h-7 flex-col items-stretch gap-1 py-2"
                    >
                      <Input
                        value={row.title}
                        maxLength={200}
                        placeholder={t("planning.untitledScene")}
                        aria-label={t("planning.titleFor", { n: index + 1 })}
                        onChange={(event) =>
                          replace(
                            rows.map((candidate, candidateIndex) =>
                              candidateIndex === index
                                ? { ...candidate, title: event.target.value }
                                : candidate,
                            ),
                          )
                        }
                      />
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-label text-muted">{t(STATUS_LABEL[row.status])}</span>
                        {next !== null ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() =>
                              replace(
                                rows.map((candidate, candidateIndex) =>
                                  candidateIndex === index
                                    ? { ...candidate, status: next }
                                    : candidate,
                                ),
                              )
                            }
                          >
                            {t("planning.advanceStatus", { status: t(STATUS_LABEL[next]) })}
                          </Button>
                        ) : null}
                        <span className="ml-auto flex gap-1">
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={index === 0}
                            onClick={() =>
                              replace(
                                rows.flatMap((candidate, candidateIndex) =>
                                  candidateIndex === index - 1
                                    ? [rows[index]!, rows[index - 1]!]
                                    : candidateIndex === index
                                      ? []
                                      : [candidate],
                                ),
                              )
                            }
                          >
                            {t("planning.moveUp")}
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={index === rows.length - 1}
                            onClick={() =>
                              replace(
                                rows.flatMap((candidate, candidateIndex) =>
                                  candidateIndex === index
                                    ? [rows[index + 1]!, rows[index]!]
                                    : candidateIndex === index + 1
                                      ? []
                                      : [candidate],
                                ),
                              )
                            }
                          >
                            {t("planning.moveDown")}
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() =>
                              replace(rows.filter((_, candidateIndex) => candidateIndex !== index))
                            }
                          >
                            {t("planning.deleteScene")}
                          </Button>
                        </span>
                      </div>
                    </Row>
                  </li>
                );
              })}
            </ul>
          )}
          {saveFailed !== null ? (
            <Notice
              tone="danger"
              live="alert"
              className="mt-2"
              action={
                <Button variant="secondary" onClick={() => void save()}>
                  {t("planning.retry")}
                </Button>
              }
            >
              {t("planning.saveFailed", { detail: saveFailed })}
            </Notice>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {/* The save is this panel's one filled primary; every companion
                action — add, retry — is a bordered equal. */}
            <Button variant="primary" disabled={!dirty || savePending} onClick={() => void save()}>
              {t("planning.save")}
            </Button>
            <Button variant="secondary" onClick={addScene}>
              {t("planning.addScene")}
            </Button>
            {dirty ? (
              <span role="status" className="text-label text-muted">
                {t("planning.unsavedChanges")}
              </span>
            ) : null}
          </div>
        </>
      )}

      {/* The third door: a route change with unsaved scenes asks too — the
          shared blocker, mounted only where a router exists, so the panel
          stays testable and the guard stays real. */}
      <LeaveBlocker dirty={dirty} ask={askToLeave} />

      <Dialog
        title={t("save.leaveTitle")}
        isOpen={guardOpen}
        onOpenChange={(open) => {
          if (!open) settle(false);
        }}
      >
        {(close) => (
          <>
            <p className="mt-2 text-body text-muted">{t("dirty.confirmLeave")}</p>
            <div className="mt-6 flex justify-end gap-3">
              <Button
                onClick={() => {
                  settle(false);
                  close();
                }}
              >
                {t("save.leaveStay")}
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  settle(true);
                  close();
                }}
              >
                {t("save.leaveGo")}
              </Button>
            </div>
          </>
        )}
      </Dialog>
    </section>
  );
}
