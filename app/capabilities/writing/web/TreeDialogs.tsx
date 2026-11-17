/**
 * The tree's dialogs (W4 Task 13) — the rename/metadata edit and the delete
 * confirm, on the modal discipline the workspace already speaks: the
 * NewBookDialog's form weight for the edit (labelled fields, focus on the
 * first input, Tab wraps, Escape/scrim/cancel close, busy holds every
 * close path, a refusal keeps the answers and names the loss-free error
 * with a retry), the LeaveGuardDialog's destructive calm for the delete
 * (role="alertdialog", focus on the safe answer, Escape cancels, the scrim
 * does NOT dismiss — only the named answers leave, the consequence on the
 * delete control's own title, the drafted second step).
 *
 * The edit dialog carries the chapter's title alone, or the scene's three
 * fields — title, setting, story_time. The two labels are
 * present-and-nullable (the SceneUpdate contract): an empty input clears
 * to `null`, the honest unset; a non-empty one is trimmed and carried. The
 * body is never a field this door carries — the autosave owns the prose.
 * An empty title is the honest unnamed („" stored, the placeholder a
 * rendering), never a refused answer.
 *
 * The delete confirm names the loss before it happens: the chapter's
 * cascade with its own scene count (the zero honest — D16), the scene's
 * words with the chapter remaining. Success tells the page (the selection
 * moves, a dead scene's draft is dropped) and closes; the read family's
 * refetch carries the new truth.
 *
 * Every close returns focus to the opener — the row menu's trigger, whose
 * id the page carried in. A trigger the write itself retired (the deleted
 * row) is simply not focused, the shelf's own rule.
 */

import { useEffect, useId, useRef, useState, type Ref, type RefObject } from "react";

import type { Chapter } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import {
  sceneTitle,
  useDeleteChapter,
  useDeleteScene,
  useUpdateChapter,
  useUpdateScene,
  type SceneEntry,
} from "./workspace";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the dialogs offer. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The trap's population: every live control inside the panel, in DOM order. */
const FOCUSABLE =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

/** The schema's one length refusal, mirrored on the inputs so the writer
 *  meets the bound before the wire does. */
const TITLE_MAX = 200;

/** The shell's busy face (the quick menu's spinner): a ring with one
 *  transparent quarter, turning. No glyph — the motion is the mark. */
function Spinner({ tone = "primary" }: { tone?: "primary" | "danger" }) {
  return (
    <span
      aria-hidden="true"
      className={`h-3.5 w-3.5 shrink-0 animate-spin rounded-full border border-t-transparent ${
        tone === "danger" ? "border-danger" : "border-primary-foreground"
      }`}
    />
  );
}

/** The modal shell's keyboard discipline: Tab wraps inside the panel at
 *  both ends; Escape answers through the caller's own rule. */
function useModalKeys(panelRef: RefObject<HTMLDivElement | null>, onEscape: () => void) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onEscape();
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (panel === null) return;
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !panel.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last || !panel.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [panelRef, onEscape]);
}

/** The loss-free error line with the retry that re-runs the very ask —
 *  the shelf quick menu's gentle error, inside the panel. */
function ErrorLine({ message, onRetry }: { message: string; onRetry: () => void }) {
  const t = useTranslation();
  return (
    <div
      role="alert"
      className="rounded-lg border border-rule border-l-2 border-l-danger bg-surface-container-lowest p-2.5 text-left"
    >
      <div className="flex items-start gap-1.5">
        <span className="mt-0.5 shrink-0 text-danger">
          <Icon name="warning" size={14} />
        </span>
        <div className="flex-1">
          <p className="text-meta leading-tight text-foreground">{message}</p>
          <button
            type="button"
            onClick={onRetry}
            className={`mt-1 inline-flex items-center gap-1 text-meta font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
          >
            {t("writing.shelf.error.retry")}
            <Icon name="refresh" size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

/** One labelled field — the dialog's input geometry. */
function Field({
  label,
  value,
  onChange,
  inputRef,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  inputRef?: Ref<HTMLInputElement>;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-meta font-medium text-foreground">
        {label}
      </label>
      <input
        id={id}
        ref={inputRef}
        type="text"
        value={value}
        maxLength={TITLE_MAX}
        onChange={(event) => onChange(event.target.value)}
        className={`w-full rounded border border-border bg-surface-container-low px-2.5 py-1.5 text-body text-foreground ${FOCUS}`}
      />
    </div>
  );
}

export type EditTarget =
  | { kind: "chapter"; chapter: Chapter }
  | { kind: "scene"; entry: SceneEntry };

/** The rename/metadata edit — one dialog, two shapes: the chapter carries
 *  the title alone, the scene the two nullable labels beside it. */
export function TreeEditDialog({
  novelId,
  target,
  openerId,
  onClose,
}: {
  novelId: string;
  target: EditTarget;
  openerId: string;
  onClose: () => void;
}) {
  const t = useTranslation();
  const chapter = target.kind === "chapter" ? target.chapter : target.entry.chapter;
  const scene = target.kind === "scene" ? target.entry.scene : null;
  const [title, setTitle] = useState(scene?.title ?? chapter.title);
  const [setting, setSetting] = useState(scene?.setting ?? "");
  const [storyTime, setStoryTime] = useState(scene?.story_time ?? "");
  const [error, setError] = useState(false);
  const updateChapter = useUpdateChapter(novelId);
  const updateScene = useUpdateScene(novelId);
  const busy = updateChapter.isPending || updateScene.isPending;

  const panelRef = useRef<HTMLDivElement | null>(null);
  const titleRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();

  // Focus lands on the title field (the rename's own answer); every close
  // returns it to the opener — a trigger the write retired is not focused.
  useEffect(() => {
    titleRef.current?.focus();
    titleRef.current?.select();
    return () => {
      document.getElementById(openerId)?.focus();
    };
  }, [openerId]);

  useModalKeys(panelRef, () => {
    if (!busy) onClose();
  });

  function save() {
    setError(false);
    const trimmed = title.trim();
    const settle = { onSuccess: onClose, onError: () => setError(true) };
    if (scene === null) {
      updateChapter.mutate({ chapterId: chapter.id, title: trimmed }, settle);
    } else {
      // The labels are present-and-nullable: an empty input clears to null
      // (the honest unset), a non-empty one rides trimmed. The body stays
      // the autosave's — never a field this door carries.
      updateScene.mutate(
        {
          sceneId: scene.id,
          chapterId: chapter.id,
          changes: {
            title: trimmed,
            setting: setting.trim() === "" ? null : setting.trim(),
            story_time: storyTime.trim() === "" ? null : storyTime.trim(),
          },
        },
        settle,
      );
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        className="w-full max-w-sm space-y-3 rounded-lg border border-border bg-panel p-5 shadow-overlay"
      >
        <div className="flex items-start justify-between gap-2">
          <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
            {t(scene === null ? "writing.workspace.crud.editChapterTitle" : "writing.workspace.crud.editSceneTitle")}
          </h2>
          <button
            type="button"
            disabled={busy}
            aria-label={t("writing.workspace.crud.close")}
            onClick={onClose}
            className={`rounded p-0.5 text-muted transition-colors hover:text-foreground ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
          >
            <Icon name="cross" size={14} />
          </button>
        </div>
        <Field
          label={t("writing.workspace.crud.titleLabel")}
          value={title}
          onChange={setTitle}
          inputRef={titleRef}
        />
        {scene !== null && (
          <>
            <Field label={t("writing.workspace.crud.settingLabel")} value={setting} onChange={setSetting} />
            <Field label={t("writing.workspace.crud.storyTimeLabel")} value={storyTime} onChange={setStoryTime} />
            <p className="text-[11px] leading-snug text-muted">{t("writing.workspace.crud.labelsHint")}</p>
          </>
        )}
        {error && <ErrorLine message={t("writing.workspace.crud.error")} onRetry={save} />}
        <div className="flex items-center justify-end gap-2 border-t border-rule pt-3">
          <button
            type="button"
            disabled={busy}
            onClick={onClose}
            className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
          >
            {t("writing.workspace.crud.cancel")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={save}
            className={`inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
          >
            {busy && <Spinner />}
            {busy ? t("writing.workspace.crud.busy") : t("writing.workspace.crud.save")}
          </button>
        </div>
      </div>
    </div>
  );
}

export type DeleteTarget =
  | { kind: "chapter"; chapter: Chapter }
  | { kind: "scene"; entry: SceneEntry };

/** The delete confirm — the loss named before it happens, the safe answer
 *  first, the consequence on the destructive control (Kachel 10's calm). */
export function DeleteTreeDialog({
  novelId,
  target,
  openerId,
  onClose,
  onDeleted,
}: {
  novelId: string;
  target: DeleteTarget;
  openerId: string;
  onClose: () => void;
  /** The write landed: the page moves the selection and drops a dead
   *  scene's draft before the dialog closes. */
  onDeleted: () => void;
}) {
  const t = useTranslation();
  const chapter = target.kind === "chapter" ? target.chapter : target.entry.chapter;
  const scene = target.kind === "scene" ? target.entry.scene : null;
  const [error, setError] = useState(false);
  const deleteChapter = useDeleteChapter(novelId);
  const deleteScene = useDeleteScene(novelId);
  const busy = deleteChapter.isPending || deleteScene.isPending;

  const panelRef = useRef<HTMLDivElement | null>(null);
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const bodyId = useId();

  const name =
    scene === null
      ? sceneTitle(chapter.title, t("writing.workspace.untitledChapter"))
      : sceneTitle(scene.title, t("writing.workspace.untitledScene"));

  // Focus lands on the safe answer; every close returns it to the opener.
  useEffect(() => {
    cancelRef.current?.focus();
    return () => {
      document.getElementById(openerId)?.focus();
    };
  }, [openerId]);

  useModalKeys(panelRef, () => {
    if (!busy) onClose();
  });

  function confirm() {
    setError(false);
    const settle = {
      onSuccess: () => {
        onDeleted();
        onClose();
      },
      onError: () => setError(true),
    };
    if (scene === null) deleteChapter.mutate(chapter.id, settle);
    else deleteScene.mutate({ sceneId: scene.id, chapterId: chapter.id }, settle);
  }

  return (
    // The scrim does NOT dismiss — a press outside the question is not an
    // answer (the guard's calm, no accidental loss).
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]">
      <div
        ref={panelRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={headingId}
        aria-describedby={bodyId}
        className="w-full max-w-xs space-y-2.5 rounded-lg border border-border bg-panel p-4 text-center shadow-overlay"
      >
        <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full border border-danger/30 bg-danger/10 text-danger">
          <Icon name="trash" size={17} />
        </div>
        <div>
          <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
            {t(scene === null ? "writing.workspace.crud.deleteChapterTitle" : "writing.workspace.crud.deleteSceneTitle")}
          </h2>
          <p id={bodyId} className="mt-0.5 text-meta leading-snug text-muted">
            {scene === null
              ? t("writing.workspace.crud.deleteChapterBody", { title: name, count: chapter.scene_count })
              : t("writing.workspace.crud.deleteSceneBody", { title: name })}
          </p>
        </div>
        {error && <ErrorLine message={t("writing.workspace.crud.deleteError")} onRetry={confirm} />}
        <div className="flex items-center justify-center gap-2 pt-1">
          <button
            type="button"
            ref={cancelRef}
            disabled={busy}
            onClick={onClose}
            className={`rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
          >
            {t("writing.workspace.crud.cancel")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={confirm}
            title={t(scene === null ? "writing.workspace.crud.deleteChapterNote" : "writing.workspace.crud.deleteSceneNote")}
            className={`inline-flex items-center gap-1.5 rounded border border-danger/40 px-2.5 py-1.5 text-meta font-medium text-danger transition-colors hover:bg-danger/10 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
          >
            {busy && <Spinner tone="danger" />}
            {busy ? t("writing.workspace.crud.deleteBusy") : t("writing.workspace.crud.deleteConfirm")}
          </button>
        </div>
      </div>
    </div>
  );
}