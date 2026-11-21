/**
 * The scene drill-in (W6 Task 4) — the storyboard's inspector dock, ported
 * from the owner-approved harmonized `three-act-storyboard-2` draft onto
 * the shell's tokens. The draft's read cards became the aggregate editor
 * the API's own shape demands: the PUT replaces the chapter's WHOLE scene
 * list, so the dock keeps a working copy — the per-scene edit dialog
 * applies into it, positions move by hand, scenes join with client-minted
 * ids and leave through the confirm — and one save commits the list in
 * its new order.
 *
 * The stale-version contract (Review Focus 1) is the save's own first
 * step: the server does NO version compare (two concurrent saves resolve
 * last-writer-wins), so the dock snapshots the chapter's stamp at load
 * and the save mutation re-reads it before the PUT — a stamp that moved
 * under the snapshot refuses as the conflict face, which offers the fresh
 * load (the server's copy, the local answers dropped) or the honest
 * overwrite (last-writer-wins, named as the overwrite it is). The face
 * carries the API's actual answer, never a guess.
 *
 * The dock imports no other capability (rule 1): the aggregate arrives
 * through the fan-out seam (`useNovelScenes`'s per-chapter entry), and
 * the workspace door is the shell's own route.
 */
import { Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";

import type { SceneAggregate, StoryboardChapter } from "@shell/lib/api/client";
import { formatNumber } from "@shell/lib/format";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { SceneVersionConflict, useSaveChapterScenes, type SceneDraft } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { sceneDisplayTitle, SceneEditDialog, RemoveSceneDialog } from "./storyboardDialogs";

/** The status chip's tone per real lifecycle state — the causality strip's
 *  own mapping: complete in the success tone, planned quiet in the muted
 *  ink that clears AA on the chip's ground (the hairline token is an edge,
 *  never text ink). */
const STATUS_CHIP: Record<string, string> = {
  complete: "bg-surface-container text-success",
  in_progress: "bg-secondary/15 text-foreground",
  planned: "bg-surface-container text-muted",
};

/** A client-minted id for a scene the draft adds: the diff treats an id
 *  no row owns as a creation, so the mint IS the create — no claim step.
 *  randomUUID preferred; a runtime without it gets getRandomValues —
 *  universal among crypto-having runtimes — 16 crypto-random bytes
 *  dressed as the UUID the schema's own id field demands
 *  (`SceneUpsert.id: UUID`; a plain hex line would 422 the whole
 *  add-scene flow). Both lookups guard the same way: no crypto at all
 *  has no honest answer, and refuses instead of minting an id the
 *  server would refuse anyway. */
function mintSceneId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  const bytes = globalThis.crypto?.getRandomValues?.(new Uint8Array(16));
  if (bytes === undefined) {
    throw new Error("a scene id needs crypto randomness and no crypto is available");
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** The whole list as one comparable line: the dirty check and the PUT's
 *  body read the same truth — fields, order, membership. */
function serialize(scenes: readonly SceneDraft[]): string {
  return scenes
    .map((scene) =>
      [scene.id, scene.title, scene.purpose, scene.conflict, scene.resolution, scene.beats.join("\u0001"), scene.status].join("\u0002"),
    )
    .join("\u0003");
}

/** The working copy from the server's rows: the PUT's own shape, position
 *  implied by the array (the server renumbers 1..N). */
function draftFrom(aggregate: SceneAggregate): SceneDraft[] {
  return aggregate.scenes.map((scene) => ({
    id: scene.id,
    title: scene.title,
    purpose: scene.purpose,
    conflict: scene.conflict,
    resolution: scene.resolution,
    beats: [...scene.beats],
    status: scene.status,
  }));
}

export function SceneDrillIn({
  novelId,
  chapter,
  aggregate,
  scenesFailed,
  onRetryScenes,
  onDirtyChange,
}: {
  novelId: string;
  chapter: StoryboardChapter | null;
  /** The chapter's fan entry — the same cache the save invalidates. */
  aggregate: SceneAggregate | undefined;
  scenesFailed: boolean;
  onRetryScenes: () => void;
  /** The dock's dirtiness, reported upward: the page guards the chapter
   *  switch behind its own confirm while a copy stands unsaved. */
  onDirtyChange: (dirty: boolean) => void;
}) {
  const t = useTranslation();
  const saveScenes = useSaveChapterScenes(novelId);

  // The working copy: null is clean — the dock shows the server's rows.
  const [draft, setDraft] = useState<SceneDraft[] | null>(null);
  // The stamp the copy was loaded under — the save compares against it.
  const [snapshot, setSnapshot] = useState<string | null>(null);
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [removeIndex, setRemoveIndex] = useState<number | null>(null);
  // The mode of the attempt the failed face would retry: a conflict's
  // overwrite must retry AS the overwrite — a bare retry would re-run the
  // version check against the stamp that already moved and bounce straight
  // back into the conflict face.
  const lastOverwrite = useRef(false);

  const chapterId = chapter?.chapter_id ?? null;

  // A chapter switch (and the first mount) folds the copy: the editor
  // edits one chapter at a time, and a stale copy must not leak across
  // the boundary. The failed attempt retires with it — its error face and
  // its overwrite mode belong to the chapter that earned them, and a
  // retry standing into the next chapter's save would leave as an
  // unversioned PUT.
  // biome-ignore lint/correctness/useExhaustiveDependencies: chapterId is the deliberate re-run key, not a value the body reads — a chapter switch must reset the editor (the WorkspacePage novelId reset's own pattern).
  useEffect(() => {
    setDraft(null);
    setSnapshot(null);
    setEditIndex(null);
    setRemoveIndex(null);
    saveScenes.reset();
    lastOverwrite.current = false;
  }, [chapterId]);

  // The snapshot follows the server's rows while the copy is clean — the
  // stamp the NEXT save compares against, recaptured after every refetch
  // (its own save, another surface's, the conflict's fresh load).
  useEffect(() => {
    if (draft === null && aggregate !== undefined && chapter !== null && aggregate.chapter_id === chapter.chapter_id) {
      setSnapshot(aggregate.version_updated_at);
    }
  }, [draft, aggregate, chapter]);

  // The rows the dock shows: the copy while it stands, the server's
  // otherwise — one order, one truth per moment.
  const rows = useMemo<SceneDraft[]>(
    () => draft ?? (aggregate !== undefined && chapter !== null && aggregate.chapter_id === chapter.chapter_id ? draftFrom(aggregate) : []),
    [draft, aggregate, chapter],
  );
  const serverRows = useMemo<SceneDraft[]>(
    () => (aggregate !== undefined && chapter !== null && aggregate.chapter_id === chapter.chapter_id ? draftFrom(aggregate) : []),
    [aggregate, chapter],
  );
  const dirty = draft !== null && serialize(draft) !== serialize(serverRows);
  const conflict = saveScenes.error instanceof SceneVersionConflict;
  const busy = saveScenes.isPending;
  const failed = saveScenes.error !== null && !conflict;

  // The dirtiness rides upward as it changes: the page's chapter-switch
  // guard reads it, so an unsaved copy never folds behind a silent card.
  // The cleanup retires the report with the dock: a body swap (an outage
  // face, a pending refetch) folds the copy silently, and the page's
  // route blocker must not keep guarding a copy that no longer stands.
  useEffect(() => {
    onDirtyChange(dirty);
    return () => onDirtyChange(false);
  }, [dirty, onDirtyChange]);

  function beginDraft(): SceneDraft[] {
    const standing = draft ?? serverRows;
    return standing;
  }

  function save(overwrite = false) {
    if (draft === null || snapshot === null || chapter === null) return;
    lastOverwrite.current = overwrite;
    saveScenes.mutate(
      { chapterId: chapter.chapter_id, scenes: draft, expectedVersion: snapshot, overwrite },
      { onSuccess: () => setDraft(null) },
    );
  }

  /** The dock's placeholder face — no chapter stands selected. */
  if (chapter === null) {
    return (
      <aside
        data-testid="drill-in"
        aria-label={t("planning.storyboard.drillInTitle")}
        className="flex w-full flex-col gap-3 rounded-[var(--radius-surface)] border border-rule bg-panel p-4 shadow-card xl:w-[22rem] xl:shrink-0"
      >
        <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
          {t("planning.storyboard.drillInTitle")}
        </span>
        <p className="text-meta leading-relaxed text-muted">{t("planning.storyboard.drillInNone")}</p>
      </aside>
    );
  }

  const chapterNumber = chapter.position + 1;

  return (
    <aside
      data-testid="drill-in"
      aria-label={t("planning.storyboard.drillInTitle")}
      className="flex max-h-[70vh] w-full flex-col gap-3 overflow-y-auto rounded-[var(--radius-surface)] border border-rule bg-panel p-4 shadow-card xl:max-h-full xl:w-[22rem] xl:shrink-0"
    >
      {/* The header — the draft's eyebrow row, chip, serif title and meta. */}
      <div className="flex flex-col gap-1 border-b border-rule pb-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-muted">
            {t("planning.storyboard.drillInTitle")}
          </span>
          <span className="rounded-full bg-secondary/15 px-2 py-0.5 font-mono text-[10px] font-bold text-foreground">
            {t("planning.storyboard.drillInChip", { position: chapterNumber, count: rows.length })}
          </span>
        </div>
        <h3 className="[font-family:var(--font-serif)] text-body font-semibold text-primary">
          {chapter.title.trim() === "" ? t("planning.crud.untitledChapter") : chapter.title}
        </h3>
        <p className="text-meta text-muted">
          {t("planning.storyboard.drillInMeta", {
            words: formatNumber(chapter.word_count),
            status: t(`planning.sync.${chapter.sync_status}` as MessageKey),
          })}
        </p>
      </div>

      {/* The rows — or the honest faces a broken fan owes. */}
      {scenesFailed ? (
        <div className="flex items-center gap-2 text-meta text-muted">
          <span aria-hidden="true" className="text-warning">
            <Icon name="warning" size={13} />
          </span>
          <span>{t("planning.storyboard.scenesUnavailable")}</span>
          <button
            type="button"
            onClick={onRetryScenes}
            className={`font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
          >
            {t("planning.storyboard.retry")}
          </button>
        </div>
      ) : aggregate === undefined ? (
        <p role="status" className="text-meta text-muted">
          {t("planning.storyboard.loading")}
        </p>
      ) : (
        <div className="flex flex-col gap-2.5">
          {rows.map((scene, index) => (
            <article
              key={scene.id}
              data-testid="drill-in-scene"
              className="flex flex-col gap-1.5 rounded-[var(--radius-control)] border border-rule bg-card p-3 shadow-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-label font-semibold leading-snug text-foreground">
                  {t("planning.storyboard.sceneLabel", {
                    chapter: chapterNumber,
                    position: index + 1,
                    title: sceneDisplayTitle(t, scene),
                  })}
                </span>
                <span className={`shrink-0 rounded-[var(--radius-control)] px-1.5 py-0.5 font-mono text-[11px] font-medium ${STATUS_CHIP[scene.status] ?? STATUS_CHIP.planned}`}>
                  {t(`planning.sceneStatus.${scene.status}` as MessageKey)}
                </span>
              </div>
              <div className="flex flex-col gap-0.5 text-[13px] leading-snug text-muted">
                <div>
                  <strong className="font-semibold text-primary">{t("planning.storyboard.purpose")}:</strong>{" "}
                  {scene.purpose.trim() === "" ? "—" : scene.purpose}
                </div>
                <div>
                  <strong className="font-semibold text-primary">{t("planning.storyboard.conflict")}:</strong>{" "}
                  {scene.conflict.trim() === "" ? "—" : scene.conflict}
                </div>
                <div>
                  <strong className="font-semibold text-primary">{t("planning.storyboard.resolutionField")}:</strong>{" "}
                  {scene.resolution.trim() === "" ? "—" : scene.resolution}
                </div>
              </div>
              <div className="border-t border-rule/60 pt-1">
                <span className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-muted">
                  {t("planning.storyboard.beats")}
                </span>
                <ul className="flex flex-col gap-0.5">
                  {scene.beats.map((beat, at) => (
                    <li key={`${at}-${beat}`} className="flex items-center gap-1.5 text-meta text-muted">
                      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60" />
                      {beat}
                    </li>
                  ))}
                </ul>
              </div>
              {/* The row's controls: order, edit, remove — all held while
                  the save is in flight, so no edit can slip into a copy
                  the PUT's success would fold away. */}
              <div className="flex items-center justify-between gap-1 border-t border-rule/60 pt-1.5">
                <div className="flex items-center gap-0.5">
                  <button
                    type="button"
                    disabled={index === 0 || busy}
                    aria-label={t("planning.storyboard.moveUp")}
                    onClick={() => {
                      const standing = beginDraft();
                      if (index <= 0) return;
                      const moved = [...standing];
                      [moved[index - 1], moved[index]] = [moved[index], moved[index - 1]];
                      setDraft(moved);
                    }}
                    className={`rounded p-1 text-muted transition-colors hover:text-foreground ${FOCUS} ${index === 0 || busy ? "cursor-not-allowed opacity-40" : ""}`}
                  >
                    <Icon name="expandLess" size={14} />
                  </button>
                  <button
                    type="button"
                    disabled={index === rows.length - 1 || busy}
                    aria-label={t("planning.storyboard.moveDown")}
                    onClick={() => {
                      const standing = beginDraft();
                      if (index >= standing.length - 1) return;
                      const moved = [...standing];
                      [moved[index], moved[index + 1]] = [moved[index + 1], moved[index]];
                      setDraft(moved);
                    }}
                    className={`rounded p-1 text-muted transition-colors hover:text-foreground ${FOCUS} ${index === rows.length - 1 || busy ? "cursor-not-allowed opacity-40" : ""}`}
                  >
                    <Icon name="chevronDown" size={14} />
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    id={`drill-scene-${scene.id}-edit`}
                    disabled={busy}
                    onClick={() => setEditIndex(index)}
                    className={`inline-flex items-center gap-1 rounded-[var(--radius-control)] border border-rule px-2 py-0.5 text-meta font-medium text-primary transition-colors hover:bg-surface-container ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
                  >
                    <Icon name="editNote" size={13} /> {t("planning.storyboard.editScene")}
                  </button>
                  <button
                    type="button"
                    id={`drill-scene-${scene.id}-remove`}
                    disabled={busy}
                    aria-label={t("planning.storyboard.removeScene")}
                    onClick={() => setRemoveIndex(index)}
                    className={`rounded p-1 text-muted transition-colors hover:text-danger ${FOCUS} ${busy ? "cursor-not-allowed opacity-40" : ""}`}
                  >
                    <Icon name="trash" size={13} />
                  </button>
                </div>
              </div>
            </article>
          ))}

          {/* The add door — a scene is born in the copy, minted and
              untitled; the PUT is its create. Held while a save is in
              flight, like every other edit into the copy. */}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              const standing = beginDraft();
              setDraft([
                ...standing,
                { id: mintSceneId(), title: "", purpose: "", conflict: "", resolution: "", beats: [], status: "planned" },
              ]);
            }}
            className={`flex w-full items-center justify-center gap-1.5 rounded-[var(--radius-control)] border border-rule bg-card py-2 text-label text-primary shadow-sm transition-colors hover:bg-surface-container ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
          >
            <Icon name="plus" size={15} />
            {t("planning.storyboard.addScene", { position: chapterNumber })}
          </button>
        </div>
      )}

      {/* The save bar — the copy's commit, or the conflict's own face. */}
      {(dirty || conflict || failed) && draft !== null && (
        <div className="mt-auto flex flex-col gap-2 border-t border-rule pt-2">
          {conflict && (
            <div data-testid="drill-in-conflict" role="alert" className="space-y-1.5 rounded-lg border border-warning/50 bg-surface-container-low p-2.5">
              <div className="flex items-center gap-1.5 text-meta font-semibold text-foreground">
                <span aria-hidden="true" className="text-warning">
                  <Icon name="warning" size={14} />
                </span>
                {t("planning.storyboard.conflictTitle")}
              </div>
              <p className="text-meta leading-snug text-muted">{t("planning.storyboard.conflictBody")}</p>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => {
                    // The copy folds onto the reloaded rows AND the spent
                    // attempt retires with it: a stale conflict face over
                    // the next edit would hide the honest save bar and
                    // offer only its own unversioned overwrite.
                    setDraft(null);
                    saveScenes.reset();
                  }}
                  className={`rounded border border-border px-2 py-1 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
                >
                  {t("planning.storyboard.conflictReload")}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => save(true)}
                  className={`rounded bg-primary px-2 py-1 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
                >
                  {t("planning.storyboard.conflictOverwrite")}
                </button>
              </div>
            </div>
          )}
          {failed && (
            <div role="alert" className="rounded-lg border border-rule border-l-2 border-l-danger bg-surface-container-lowest p-2.5">
              <p className="text-meta leading-tight text-foreground">{t("planning.crud.error")}</p>
              <button
                type="button"
                onClick={() => save(lastOverwrite.current)}
                className={`mt-1 inline-flex items-center gap-1 text-meta font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
              >
                {t("planning.storyboard.retry")}
                <Icon name="refresh" size={12} />
              </button>
            </div>
          )}
          {dirty && !conflict && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => setDraft(null)}
                className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
              >
                {t("planning.storyboard.discardAggregate")}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => save()}
                className={`inline-flex flex-1 items-center justify-center gap-1.5 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
              >
                {busy && (
                  <span aria-hidden="true" className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border border-primary-foreground border-t-transparent" />
                )}
                {t("planning.storyboard.saveAggregate")}
              </button>
            </div>
          )}
        </div>
      )}

      {/* The workspace door — the draft's foot, the shell's own route. */}
      <Link
        to="/novels/$novelId"
        params={{ novelId }}
        className={`flex w-full items-center justify-center gap-2 rounded-[var(--radius-control)] bg-primary py-2 text-label font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
      >
        <Icon name="editNote" size={16} /> {t("planning.storyboard.openWorkspace")}
      </Link>

      {/* The dialogs — one lead at a time. */}
      {editIndex !== null && rows[editIndex] !== undefined && (
        <SceneEditDialog
          scene={rows[editIndex]}
          openerId={`drill-scene-${rows[editIndex].id}-edit`}
          onClose={() => setEditIndex(null)}
          onApply={(fields) => {
            const standing = beginDraft();
            setDraft(standing.map((scene, at) => (at === editIndex ? { ...scene, ...fields } : scene)));
          }}
        />
      )}
      {removeIndex !== null && rows[removeIndex] !== undefined && (
        <RemoveSceneDialog
          scene={rows[removeIndex]}
          openerId={`drill-scene-${rows[removeIndex].id}-remove`}
          onCancel={() => setRemoveIndex(null)}
          onRemoved={() => {
            const standing = beginDraft();
            setDraft(standing.filter((_, at) => at !== removeIndex));
            setRemoveIndex(null);
          }}
        />
      )}
    </aside>
  );
}
