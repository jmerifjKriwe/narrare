/**
 * The storyboard dialogs (W6 Task 4) — the planning capability's second
 * editing layer, speaking the modal discipline the house dialogs speak
 * (the timeline family's own re-ownership): the form weight for the scene
 * edit (labelled fields, focus on the first answer, Tab wraps, busy holds
 * every close path, a dirty guard keeps the answers, a refusal names the
 * loss-free error with a retry) and the destructive calm for the scene
 * remove (role="alertdialog", focus on the safe answer, the scrim does
 * NOT dismiss). The keyboard discipline rides the shell's one home
 * (`@shell/ui/modalKeys`): the trap and the wrap shared, the Escape
 * answer each dialog's own.
 *
 * The remap dialog is the server's own two-step contract made visible:
 * it opens with the preview (`confirm: false` — nothing written), lists
 * every chapter's move from the stage it stands in to the one the target
 * structure's position-ratio suggests, and only its confirm writes
 * (`confirm: true` — the assignments plus the novel setting in one
 * transaction, exactly the previewed mapping). A refusal carries the
 * API's own words: the 422 that names an unknown structure id gets the
 * refusal face (Review Focus 2), never a bricked switcher; every other
 * failure is the loss-free error with a retry.
 *
 * The scene edit applies into the drill-in's working copy — the
 * aggregate PUT is the dock's own save, not the dialog's. Its fields are
 * the row's real ones only: the title (empty is the honest default — the
 * dock shows its own placeholder), purpose, conflict, resolution, the
 * beats (committed one by one on Enter, comma or blur) and the lifecycle
 * status. The module imports no other capability (rule 1).
 */
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";

import type { RemapRead, StoryboardChapter } from "@shell/lib/api/client";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { useRemapStoryboard, type SceneDraft } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";
import { useModalKeys } from "@shell/ui/modalKeys";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The schema's bounds, mirrored on the input so the writer meets them
 *  before the wire does: the scene title's width. */
const TITLE_MAX = 200;

const INPUT =
  "w-full rounded border border-border bg-surface-container-low px-2.5 py-1.5 text-body text-foreground";

/** The scene lifecycle's three states, the UI's mirror of the server's
 *  own tuple — the select offers nothing the PUT would refuse. */
const SCENE_STATUSES = ["planned", "in_progress", "complete"] as const;

/** The shell's busy face (the quick menu's spinner): a ring with one
 *  transparent quarter, turning. No glyph — the motion is the mark. */
function Spinner({ tone = "primary" }: { tone?: "primary" | "danger" }) {
  const ring = tone === "danger" ? "border-danger" : "border-primary-foreground";
  return (
    <span aria-hidden="true" className={`h-3.5 w-3.5 shrink-0 animate-spin rounded-full border border-t-transparent ${ring}`} />
  );
}

/** The loss-free error line with the retry that re-runs the very ask — the
 *  shelf quick menu's gentle error, inside the panel. */
function ErrorLine({ message, onRetry }: { message: string; onRetry: () => void }) {
  const t = useTranslation();
  return (
    <div role="alert" className="rounded-lg border border-rule border-l-2 border-l-danger bg-surface-container-lowest p-2.5 text-left">
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
            {t("planning.storyboard.retry")}
            <Icon name="refresh" size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

/** The modal frame: the scrim, the panel, the shared keyboard discipline and
 *  the focus contract. `onDismiss` is the dialog's own guarded close (Escape
 *  and, when `scrimDismiss`, a press outside); focus lands on `focusRef` and
 *  returns to the opener on unmount. */
function Modal({
  openerId,
  role,
  headingId,
  bodyId,
  onDismiss,
  scrimDismiss,
  focusRef,
  panelClassName,
  children,
}: {
  openerId: string;
  role: "dialog" | "alertdialog";
  headingId: string;
  bodyId?: string;
  onDismiss: () => void;
  scrimDismiss: boolean;
  focusRef: RefObject<HTMLElement | null>;
  panelClassName: string;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  useModalKeys(panelRef, onDismiss, { enabled: true });
  useEffect(() => {
    focusRef.current?.focus();
  }, [focusRef]);
  useEffect(() => {
    return () => {
      document.getElementById(openerId)?.focus();
    };
  }, [openerId]);
  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]`}
      onMouseDown={(event) => {
        if (scrimDismiss && event.target === event.currentTarget) onDismiss();
      }}
    >
      <div
        ref={panelRef}
        role={role}
        aria-modal="true"
        aria-labelledby={headingId}
        aria-describedby={bodyId}
        className={panelClassName}
      >
        {children}
      </div>
    </div>
  );
}

/** The form panel's header: the serif heading and the cross that closes
 *  (honestly unavailable while busy or dirty). */
function FormHeader({
  headingId,
  title,
  busy,
  dirty,
  onClose,
}: {
  headingId: string;
  title: string;
  busy: boolean;
  dirty: boolean;
  onClose: () => void;
}) {
  const t = useTranslation();
  const held = busy || dirty;
  return (
    <div className="flex items-start justify-between gap-2">
      <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
        {title}
      </h2>
      <button
        type="button"
        disabled={held}
        aria-label={t("planning.crud.close")}
        onClick={onClose}
        className={`rounded p-0.5 text-muted transition-colors hover:text-foreground ${FOCUS} ${held ? "cursor-not-allowed opacity-50" : ""}`}
      >
        <Icon name="cross" size={14} />
      </button>
    </div>
  );
}

/** The panels' viewport law, the writing family's NewBookDialog answer:
 *  never taller than the scrim's box (100vh minus its p-4), the overflow
 *  scrolling inside the frame on a short screen. */
const FORM_PANEL =
  "max-h-[calc(100vh-2rem)] w-full max-w-sm space-y-3 overflow-y-auto rounded-lg border border-border bg-panel p-5 shadow-overlay";
const CONFIRM_PANEL =
  "max-h-[calc(100vh-2rem)] w-full max-w-xs space-y-2.5 overflow-y-auto rounded-lg border border-border bg-panel p-4 text-center shadow-overlay";
const REMAP_PANEL =
  "max-h-[calc(100vh-2rem)] w-full max-w-md space-y-3 overflow-y-auto rounded-lg border border-border bg-panel p-5 shadow-overlay";

// --- The remap dialog -------------------------------------------------------

/** The remap's chapter move in words: the chapter's number, the stage it
 *  stands in, the one the target suggests — both through the i18n key the
 *  server's own registry names. */
export function stageLabel(t: ReturnType<typeof useTranslation>, key: string): string {
  return t(`storyboard.stage.${key}` as MessageKey);
}

/**
 * The structure change, both steps: the preview the open asks for
 * (nothing written), the confirm the writer's answer applies (the
 * assignments plus the novel setting, exactly the previewed mapping). A
 * 422 that names an unknown structure id gets the API's refusal face —
 * the switcher outside never bricks.
 */
export function RemapDialog({
  novelId,
  structureId,
  structureLabel,
  chapters,
  openerId,
  onClose,
  onApplied,
}: {
  novelId: string;
  structureId: string;
  structureLabel: string;
  chapters: readonly StoryboardChapter[];
  openerId: string;
  onClose: () => void;
  /** The confirm landed: the caller folds its pending selection. */
  onApplied: () => void;
}) {
  const t = useTranslation();
  const [preview, setPreview] = useState<RemapRead | null>(null);
  const [failed, setFailed] = useState<{ status?: number } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const remap = useRemapStoryboard(novelId);

  const positionById = new Map(chapters.map((chapter) => [chapter.chapter_id, chapter.position]));
  const headingId = useId();
  const bodyId = useId();
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const ranRef = useRef(false);

  function run(confirm: boolean) {
    setFailed(null);
    remap.mutate(
      { structureId, confirm },
      {
        onSuccess: (answer) => {
          if (confirm) {
            onApplied();
            onClose();
          } else {
            setPreview(answer);
          }
        },
        onError: (error) => {
          setFailed({ status: (error as { status?: number }).status });
        },
      },
    );
  }

  // The preview asks once on mount — the dialog IS the preview step, and
  // a re-render of it must never re-ask (the ref holds the once).
  // biome-ignore lint/correctness/useExhaustiveDependencies: the mount is the deliberate once-ask — the preview runs when the dialog opens, never on every render of it.
  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;
    run(false);
  }, []);

  const busy = remap.isPending;
  const unknownStructure = failed?.status === 422;

  return (
    <Modal
      openerId={openerId}
      role="dialog"
      headingId={headingId}
      bodyId={bodyId}
      onDismiss={() => {
        if (!busy) onClose();
      }}
      scrimDismiss
      focusRef={closeRef}
      panelClassName={REMAP_PANEL}
    >
      <FormHeader
        headingId={headingId}
        title={t("planning.storyboard.remapDialogTitle")}
        busy={busy}
        dirty={false}
        onClose={onClose}
      />
      <p id={bodyId} className="text-meta leading-snug text-muted">
        {structureLabel} · {t("planning.storyboard.remapDialogBody")}
      </p>
      {preview === null && failed === null && (
        <p role="status" className="text-meta text-muted">
          {t("planning.storyboard.loading")}
        </p>
      )}
      {preview !== null && (
        <ul className="max-h-64 space-y-1 overflow-y-auto rounded-lg border border-rule bg-surface-container-low p-2.5">
          {preview.mapping.map((entry) => {
            // A chapter the board cannot name (its row raced away between
            // the read and the preview) keeps its move — the stages are
            // the mapping's own fact — without a number that would name
            // the wrong chapter.
            const position = positionById.get(entry.chapter_id);
            return (
              <li key={entry.chapter_id} className="flex items-center gap-1.5 text-meta text-foreground">
                <span className="shrink-0 text-muted">
                  <Icon name="arrowRight" size={12} />
                </span>
                {position === undefined
                  ? t("planning.storyboard.remapMoveUnnumbered", {
                      from: stageLabel(t, entry.from_stage),
                      to: stageLabel(t, entry.to_stage),
                    })
                  : t("planning.storyboard.remapMove", {
                      position: position + 1,
                      from: stageLabel(t, entry.from_stage),
                      to: stageLabel(t, entry.to_stage),
                    })}
              </li>
            );
          })}
        </ul>
      )}
      {unknownStructure && (
        <p role="alert" className="rounded-lg border border-rule border-l-2 border-l-danger bg-surface-container-lowest p-2.5 text-meta leading-snug text-foreground">
          {t("planning.storyboard.remapUnknownStructure")}
        </p>
      )}
      {failed !== null && !unknownStructure && (
        <ErrorLine message={t("planning.storyboard.remapError")} onRetry={() => run(false)} />
      )}
      <div className="flex items-center justify-end gap-2 border-t border-rule pt-3">
        <button
          type="button"
          ref={closeRef}
          disabled={busy}
          onClick={onClose}
          className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
        >
          {t("planning.crud.cancel")}
        </button>
        <button
          type="button"
          disabled={busy || preview === null}
          onClick={() => {
            setConfirming(true);
            run(true);
          }}
          className={`inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${
            busy || preview === null ? "cursor-not-allowed opacity-60" : ""
          }`}
        >
          {busy && confirming && <Spinner />}
          {busy && confirming ? t("planning.storyboard.remapBusy") : t("planning.storyboard.remapConfirm")}
        </button>
      </div>
    </Modal>
  );
}

// --- The scene edit ---------------------------------------------------------

/** The beats editor (the names box's pattern): the input commits one beat
 *  on Enter, a comma or a blur, and each beat carries its own remove
 *  control. A beat already standing is not doubled; an empty trim commits
 *  nothing. */
function BeatsEditor({
  beats,
  onChange,
}: {
  beats: readonly string[];
  onChange: (beats: string[]) => void;
}) {
  const t = useTranslation();
  const [draft, setDraft] = useState("");

  function commit() {
    const beat = draft.trim();
    setDraft("");
    if (beat === "" || beats.includes(beat)) return;
    onChange([...beats, beat]);
  }

  return (
    <div>
      <div className="flex flex-col gap-1 pb-1">
        {beats.map((beat, at) => (
          <span
            key={`${at}-${beat}`}
            className="flex items-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container px-2 py-0.5 text-meta text-foreground"
          >
            <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60" />
            <span className="flex-1">{beat}</span>
            <button
              type="button"
              aria-label={t("planning.crud.removeName", { name: beat })}
              onClick={() => onChange(beats.filter((standing) => standing !== beat))}
              className={`rounded p-0.5 text-muted transition-colors hover:text-danger ${FOCUS}`}
            >
              <Icon name="cross" size={12} />
            </button>
          </span>
        ))}
      </div>
      <input
        type="text"
        value={draft}
        aria-label={t("planning.storyboard.beats")}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === ",") {
            event.preventDefault();
            commit();
          }
        }}
        onBlur={commit}
        className={`${INPUT} ${FOCUS}`}
      />
      <p className="mt-0.5 text-[11px] leading-snug text-muted">{t("planning.storyboard.beatsHint")}</p>
    </div>
  );
}

/** The scene form's fields: the state a fresh scene seeds empty and an
 *  edit prefills from the working copy's row. */
interface SceneFormState {
  title: string;
  purpose: string;
  conflict: string;
  resolution: string;
  beats: string[];
  status: string;
}

/**
 * The scene edit: the drill-in's working-copy editor. Saving applies the
 * answers into the copy — the aggregate PUT stays the dock's own save, so
 * the dialog never writes and never guards a version it cannot see. The
 * title's emptiness is honest (the dock shows its own placeholder); the
 * status select offers the lifecycle's three states only.
 */
export function SceneEditDialog({
  scene,
  openerId,
  onClose,
  onApply,
}: {
  scene: SceneDraft;
  openerId: string;
  onClose: () => void;
  /** The answers land in the dock's working copy. */
  onApply: (fields: SceneFormState) => void;
}) {
  const t = useTranslation();
  const [form, setForm] = useState<SceneFormState>({
    title: scene.title,
    purpose: scene.purpose,
    conflict: scene.conflict,
    resolution: scene.resolution,
    beats: [...scene.beats],
    status: scene.status,
  });
  const dirty =
    form.title !== scene.title ||
    form.purpose !== scene.purpose ||
    form.conflict !== scene.conflict ||
    form.resolution !== scene.resolution ||
    form.beats.join("\u0000") !== scene.beats.join("\u0000") ||
    form.status !== scene.status;

  const titleRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();
  const suffix = useId();

  return (
    <Modal
      openerId={openerId}
      role="dialog"
      headingId={headingId}
      onDismiss={() => {
        if (!dirty) onClose();
      }}
      scrimDismiss
      focusRef={titleRef}
      panelClassName={FORM_PANEL}
    >
      <FormHeader
        headingId={headingId}
        title={t("planning.storyboard.editScene")}
        busy={false}
        dirty={dirty}
        onClose={onClose}
      />
      <div>
        <label htmlFor={`scene-title-${suffix}`} className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.storyboard.sceneTitleField")}
        </label>
        <input
          id={`scene-title-${suffix}`}
          ref={titleRef}
          type="text"
          value={form.title}
          maxLength={TITLE_MAX}
          onChange={(event) => setForm((previous) => ({ ...previous, title: event.target.value }))}
          className={`${INPUT} font-semibold ${FOCUS}`}
        />
        <p className="mt-0.5 text-[11px] leading-snug text-muted">{t("planning.storyboard.sceneTitleHint")}</p>
      </div>
      <div>
        <label htmlFor={`scene-purpose-${suffix}`} className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.storyboard.purpose")}
        </label>
        <textarea
          id={`scene-purpose-${suffix}`}
          rows={2}
          value={form.purpose}
          onChange={(event) => setForm((previous) => ({ ...previous, purpose: event.target.value }))}
          className={`${INPUT} resize-y leading-relaxed ${FOCUS}`}
        />
      </div>
      <div>
        <label htmlFor={`scene-conflict-${suffix}`} className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.storyboard.conflict")}
        </label>
        <textarea
          id={`scene-conflict-${suffix}`}
          rows={2}
          value={form.conflict}
          onChange={(event) => setForm((previous) => ({ ...previous, conflict: event.target.value }))}
          className={`${INPUT} resize-y leading-relaxed ${FOCUS}`}
        />
      </div>
      <div>
        <label htmlFor={`scene-resolution-${suffix}`} className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.storyboard.resolutionField")}
        </label>
        <textarea
          id={`scene-resolution-${suffix}`}
          rows={2}
          value={form.resolution}
          onChange={(event) => setForm((previous) => ({ ...previous, resolution: event.target.value }))}
          className={`${INPUT} resize-y leading-relaxed ${FOCUS}`}
        />
      </div>
      <div>
        <label htmlFor={`scene-status-${suffix}`} className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.storyboard.statusLabel")}
        </label>
        <select
          id={`scene-status-${suffix}`}
          value={form.status}
          onChange={(event) => setForm((previous) => ({ ...previous, status: event.target.value }))}
          className={`${INPUT} ${FOCUS}`}
        >
          {SCENE_STATUSES.map((status) => (
            <option key={status} value={status}>
              {t(`planning.sceneStatus.${status}` as MessageKey)}
            </option>
          ))}
        </select>
      </div>
      <div>
        <span className="mb-1 block text-meta font-medium text-foreground">{t("planning.storyboard.beats")}</span>
        <BeatsEditor beats={form.beats} onChange={(beats) => setForm((previous) => ({ ...previous, beats }))} />
      </div>
      <div className="flex items-center justify-end gap-2 border-t border-rule pt-3">
        <button
          type="button"
          onClick={onClose}
          className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS}`}
        >
          {t("planning.crud.cancel")}
        </button>
        <button
          type="button"
          onClick={() => {
            onApply({ ...form, title: form.title, beats: [...form.beats] });
            onClose();
          }}
          className={`inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
        >
          {t("planning.crud.saveChanges")}
        </button>
      </div>
    </Modal>
  );
}

// --- The dirty-copy discard guard -------------------------------------------

/**
 * The chapter-switch guard over a dirty working copy (the review's
 * Important fix): leaving the chapter through a card asks before the copy
 * folds — the same destructive calm the scene remove speaks. Confirming
 * folds the copy into the new chapter's clean rows; cancelling keeps the
 * copy and the chapter it belongs to. The scrim does not dismiss; focus
 * lands on the safe answer.
 */
export function DiscardDraftDialog({
  chapterTitle,
  openerId,
  onCancel,
  onDiscard,
}: {
  chapterTitle: string;
  openerId: string;
  /** The safe answer: the guard stands down, the copy keeps standing. */
  onCancel: () => void;
  /** The writer named the loss: the switch proceeds and the copy folds. */
  onDiscard: () => void;
}) {
  const t = useTranslation();
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const bodyId = useId();

  return (
    <Modal
      openerId={openerId}
      role="alertdialog"
      headingId={headingId}
      bodyId={bodyId}
      onDismiss={onCancel}
      scrimDismiss={false}
      focusRef={cancelRef}
      panelClassName={CONFIRM_PANEL}
    >
      <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full border border-warning/40 bg-warning/10 text-warning">
        <Icon name="warning" size={17} />
      </div>
      <div>
        <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
          {t("planning.storyboard.discardDraftTitle")}
        </h2>
        <p id={bodyId} className="mt-0.5 text-meta leading-snug text-muted">
          {t("planning.storyboard.discardDraftBody", { title: chapterTitle })}
        </p>
      </div>
      <div className="flex items-center justify-center gap-2 pt-1">
        <button
          type="button"
          ref={cancelRef}
          onClick={onCancel}
          className={`rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
        >
          {t("planning.crud.cancel")}
        </button>
        <button
          type="button"
          onClick={onDiscard}
          title={t("planning.storyboard.discardDraftTitle")}
          className={`rounded border border-danger/40 px-2.5 py-1.5 text-meta font-medium text-danger transition-colors hover:bg-danger/10 ${FOCUS}`}
        >
          {t("planning.storyboard.discardDraftConfirm")}
        </button>
      </div>
    </Modal>
  );
}

// --- The scene remove -------------------------------------------------------

/** The display title a scene carries on the dock: its own, or the
 *  placeholder an untitled scene reads — the confirm names the row it
 *  takes, never an empty string. */
export function sceneDisplayTitle(t: ReturnType<typeof useTranslation>, scene: SceneDraft): string {
  return scene.title.trim() === "" ? t("planning.storyboard.untitledScene") : scene.title;
}

/**
 * The scene remove: the destructive calm over the working copy — the row
 * leaves the copy (and with it the next PUT's body, where an absent id is
 * the delete), nothing written yet. The scrim does not dismiss; focus
 * lands on the safe answer.
 */
export function RemoveSceneDialog({
  scene,
  openerId,
  onCancel,
  onRemoved,
}: {
  scene: SceneDraft;
  openerId: string;
  onCancel: () => void;
  onRemoved: () => void;
}) {
  const t = useTranslation();
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const bodyId = useId();

  return (
    <Modal
      openerId={openerId}
      role="alertdialog"
      headingId={headingId}
      bodyId={bodyId}
      onDismiss={onCancel}
      scrimDismiss={false}
      focusRef={cancelRef}
      panelClassName={CONFIRM_PANEL}
    >
      <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full border border-danger/30 bg-danger/10 text-danger">
        <Icon name="trash" size={17} />
      </div>
      <div>
        <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
          {t("planning.storyboard.deleteSceneTitle")}
        </h2>
        <p id={bodyId} className="mt-0.5 text-meta leading-snug text-muted">
          {t("planning.storyboard.deleteSceneBody", { title: sceneDisplayTitle(t, scene) })}
        </p>
      </div>
      <div className="flex items-center justify-center gap-2 pt-1">
        <button
          type="button"
          ref={cancelRef}
          onClick={onCancel}
          className={`rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
        >
          {t("planning.crud.cancel")}
        </button>
        <button
          type="button"
          onClick={onRemoved}
          title={t("planning.storyboard.deleteSceneTitle")}
          className={`rounded border border-danger/40 px-2.5 py-1.5 text-meta font-medium text-danger transition-colors hover:bg-danger/10 ${FOCUS}`}
        >
          {t("planning.storyboard.deleteSceneConfirm")}
        </button>
      </div>
    </Modal>
  );
}
