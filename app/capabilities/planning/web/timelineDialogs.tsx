/**
 * The timeline CRUD dialogs (W6 Task 3) — the planning capability's editing
 * layer, ported onto the modal discipline the house dialogs speak (the
 * writing and knowledge families): the form weight for the create and the
 * edit (labelled fields, focus on the first answer, Tab wraps, busy holds
 * every close path, a refusal keeps the answers and names the loss-free
 * error with a retry) and the destructive calm for the delete
 * (role="alertdialog", focus on the safe answer, Escape cancels, the scrim
 * does NOT dismiss, the loss named before it happens). The keyboard
 * discipline rides the shell's one home (`@shell/ui/modalKeys`): the trap
 * and the wrap shared, the Escape answer each dialog's own.
 *
 * The fields are the row's real ones only — the title (never blank, the
 * chapters' rule), the free-text date label with its hint, the
 * description, the optional chapter link, the free-text character names
 * (committed as chips on Enter, comma or blur — plain text, no KB
 * linkage; the pending draft rides the form's state so the dirty-close
 * guard sees it), and the manual position (empty = unordered, listed
 * last).
 * The create POSTs the whole writer-facing row; the edit PUTs ONLY the
 * dirtied fields — the client's mirror of the server's `model_fields_set`
 * contract, a carried null clearing the chapter link or the position
 * (TimelineEventChanges in the query seam). The edit carries the
 * destructive remove as the draft's inspector does; it hands the event to
 * the page, which opens the confirm.
 *
 * The module imports no other capability (rule 1): the busy spinner, the
 * error line and the modal frame are re-owned here on the shell's tokens,
 * the knowledge family's geometry, speaking the planning catalog's own
 * words.
 */
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";

import type { Chapter, TimelineEvent } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import {
  useCreateTimelineEvent,
  useDeleteTimelineEvent,
  useUpdateTimelineEvent,
  type TimelineEventChanges,
} from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";
import { useModalKeys } from "@shell/ui/modalKeys";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The schema's bounds, mirrored on the inputs so the writer meets them
 *  before the wire does: the title's and the date label's width. */
const TITLE_MAX = 500;
const DATE_MAX = 200;

const INPUT =
  "w-full rounded border border-border bg-surface-container-low px-2.5 py-1.5 text-body text-foreground";

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
            {t("planning.crud.retry")}
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
 *  returns to the opener on unmount. A destructive write that RETIRES its
 *  opener (a deleted row) sets `retiredRef`; the return then lands on
 *  `survivorFocusId` — the container that survives the write — instead of an
 *  opener that is gone, so focus never falls to the body. */
function Modal({
  openerId,
  role,
  headingId,
  bodyId,
  onDismiss,
  scrimDismiss,
  focusRef,
  panelClassName,
  survivorFocusId,
  retiredRef,
  suspended = false,
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
  survivorFocusId?: string;
  retiredRef?: RefObject<boolean>;
  /** A confirm stands over this dialog: keep its state, stand its trap
   *  down, hide it from the pointer and the reader until it leads again. */
  suspended?: boolean;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  useModalKeys(panelRef, onDismiss, { enabled: !suspended });
  // The landing: focus on mount, and again whenever a standing confirm
  // hands the keyboard back.
  useEffect(() => {
    if (suspended) return;
    focusRef.current?.focus();
  }, [suspended, focusRef]);
  // The return: focus goes back to the opener when the dialog unmounts —
  // to the survivor instead when the write retired the opener.
  useEffect(() => {
    return () => {
      const retired = retiredRef?.current === true;
      const id = retired && survivorFocusId !== undefined ? survivorFocusId : openerId;
      document.getElementById(id)?.focus();
    };
  }, [openerId, survivorFocusId, retiredRef]);
  return (
    <div
      aria-hidden={suspended || undefined}
      className={`fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px] ${suspended ? "pointer-events-none" : ""}`}
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
        inert={suspended || undefined}
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

/** The form panel's footer: Abbrechen and the busy save — the edit
 *  speaks the draft's „Änderungen speichern", the create its plain word. */
function FormFooter({
  busy,
  saveLabel,
  onClose,
  onSave,
}: {
  busy: boolean;
  saveLabel: string;
  onClose: () => void;
  onSave: () => void;
}) {
  const t = useTranslation();
  return (
    <div className="flex items-center justify-end gap-2 border-t border-rule pt-3">
      <button
        type="button"
        disabled={busy}
        onClick={onClose}
        className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
      >
        {t("planning.crud.cancel")}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={onSave}
        className={`inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
      >
        {busy && <Spinner />}
        {busy ? t("planning.crud.busy") : saveLabel}
      </button>
    </div>
  );
}

/** A validation line — the required guard's own words, shown once a save was
 *  attempted against an incomplete answer. */
function ValidationLine({ message }: { message: string }) {
  return (
    <p role="alert" className="text-meta leading-tight text-danger">
      {message}
    </p>
  );
}

/** The chapter options: the placeholder plus the novel's chapters in
 *  position order, each named by its number and title. */
function ChapterOptions({ chapters }: { chapters: readonly Chapter[] }) {
  const t = useTranslation();
  return (
    <>
      <option value="">{t("planning.crud.noChapterOption")}</option>
      {chapters.map((chapter) => (
        <option key={chapter.id} value={chapter.id}>
          {t("planning.crud.chapterOption", {
            position: chapter.position + 1,
            title: chapter.title.trim() === "" ? t("planning.crud.untitledChapter") : chapter.title,
          })}
        </option>
      ))}
    </>
  );
}

/**
 * The free-text name editor (the draft's chips box): the input commits a
 * chip on Enter, a comma or a blur — the draft's comma-separated way of
 * typing works unchanged — and each chip carries its own remove control.
 * A name already standing is not doubled; an empty trim commits nothing.
 * The pending draft rides the FORM's state (`namesDraft`), not a local
 * one, so a typed-but-uncommitted name holds the close paths like any
 * other answer in progress — Escape no longer discards it silently.
 */
function NamesEditor({
  names,
  draft,
  onDraftChange,
  onChange,
}: {
  names: readonly string[];
  draft: string;
  onDraftChange: (draft: string) => void;
  onChange: (names: string[]) => void;
}) {
  const t = useTranslation();

  function commit() {
    const name = draft.trim();
    onDraftChange("");
    if (name === "" || names.includes(name)) return;
    onChange([...names, name]);
  }

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 pb-0.5">
        {names.map((name) => (
          <span
            key={name}
            className="inline-flex items-center gap-1 rounded-[var(--radius-control)] bg-secondary/15 px-2 py-0.5 text-meta text-foreground"
          >
            {name}
            <button
              type="button"
              aria-label={t("planning.crud.removeName", { name })}
              onClick={() => onChange(names.filter((standing) => standing !== name))}
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
        aria-label={t("planning.crud.namesLabel")}
        onChange={(event) => onDraftChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === ",") {
            event.preventDefault();
            commit();
          }
        }}
        onBlur={commit}
        className={`${INPUT} ${FOCUS}`}
      />
      <p className="mt-0.5 text-[11px] leading-snug text-muted">{t("planning.crud.namesHint")}</p>
    </div>
  );
}

/** The panels keep to the viewport — the writing family's NewBookDialog
 *  answer: never taller than the scrim's box (100vh minus its p-4), the
 *  overflow scrolling inside the frame on a short screen. */
const FORM_PANEL =
  "max-h-[calc(100vh-2rem)] w-full max-w-sm space-y-3 overflow-y-auto rounded-lg border border-border bg-panel p-5 shadow-overlay";
const CONFIRM_PANEL =
  "max-h-[calc(100vh-2rem)] w-full max-w-xs space-y-2.5 overflow-y-auto rounded-lg border border-border bg-panel p-4 text-center shadow-overlay";

/** The confirm family's footer: the safe answer first (primary), the
 *  destructive answer beside it with the consequence on its own title. */
function ConfirmFooter({
  busy,
  confirmTitle,
  busyLabel,
  confirmLabel,
  onCancel,
  onConfirm,
  cancelRef,
}: {
  busy: boolean;
  confirmTitle: string;
  busyLabel: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
  cancelRef: RefObject<HTMLButtonElement | null>;
}) {
  const t = useTranslation();
  return (
    <div className="flex items-center justify-center gap-2 pt-1">
      <button
        type="button"
        ref={cancelRef}
        disabled={busy}
        onClick={onCancel}
        className={`rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
      >
        {t("planning.crud.cancel")}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={onConfirm}
        title={confirmTitle}
        className={`inline-flex items-center gap-1.5 rounded border border-danger/40 px-2.5 py-1.5 text-meta font-medium text-danger transition-colors hover:bg-danger/10 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
      >
        {busy && <Spinner tone="danger" />}
        {busy ? busyLabel : confirmLabel}
      </button>
    </div>
  );
}

/** The confirm family's icon badge — the destructive mark in its calm ring. */
function ConfirmBadge({ icon }: { icon: Parameters<typeof Icon>[0]["name"] }) {
  return (
    <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-full border border-danger/30 bg-danger/10 text-danger">
      <Icon name={icon} size={17} />
    </div>
  );
}

/** The event form's shared fields: the state a create seeds empty and an
 *  edit prefills from the row — plus the names editor's pending draft:
 *  never a field of the row (it crosses no wire), but the dirty guard
 *  must see it or Escape would discard it silently. */
interface EventFormState {
  title: string;
  dateLabel: string;
  description: string;
  chapterId: string;
  positionInput: string;
  names: string[];
  namesDraft: string;
}

function eventFormState(event: TimelineEvent | null): EventFormState {
  return {
    title: event?.title ?? "",
    dateLabel: event?.date_label ?? "",
    description: event?.description ?? "",
    chapterId: event?.chapter_id ?? "",
    positionInput: event?.position == null ? "" : String(event.position),
    names: event ? [...event.character_names] : [],
    namesDraft: "",
  };
}

/** The position input's honest answer: null for the empty box (unordered,
 *  listed last), the whole number the writer typed, or null when the text
 *  names none — the dialogs' guard shows its own words before the wire
 *  would answer a 422 for a fraction. */
function parsePosition(input: string): number | null {
  const text = input.trim();
  if (text === "") return null;
  const value = Number(text);
  return Number.isInteger(value) ? value : null;
}

/** The names that cross the wire: the standing chips plus a pending
 *  draft — a save commits what the writer typed, exactly as Enter, a
 *  comma and a blur do; an empty trim or a doubled name adds nothing. */
function committedNames(form: EventFormState): string[] {
  const name = form.namesDraft.trim();
  if (name === "" || form.names.includes(name)) return form.names;
  return [...form.names, name];
}

/** The dirtied fields of an edit, as the PUT's partial body: only what the
 *  writer changed crosses the wire, and a cleared chapter link or position
 *  rides as the carried null that clears it (the server's contract). */
function eventChanges(event: TimelineEvent, form: EventFormState): TimelineEventChanges {
  const changes: TimelineEventChanges = {};
  if (form.title.trim() !== event.title) changes.title = form.title.trim();
  if (form.description !== event.description) changes.description = form.description;
  if (form.dateLabel !== event.date_label) changes.date_label = form.dateLabel;
  if (form.names.join("\u0000") !== event.character_names.join("\u0000")) {
    changes.character_names = form.names;
  }
  if (form.chapterId !== (event.chapter_id ?? "")) {
    changes.chapter_id = form.chapterId === "" ? null : form.chapterId;
  }
  const originalPosition = event.position == null ? "" : String(event.position);
  if (form.positionInput.trim() !== originalPosition) {
    changes.position = parsePosition(form.positionInput);
  }
  return changes;
}

// --- The event create ------------------------------------------------------

export function CreateEventDialog({
  novelId,
  chapters,
  openerId,
  onClose,
  survivorFocusId,
  retiredRef,
}: {
  novelId: string;
  chapters: readonly Chapter[];
  openerId: string;
  onClose: () => void;
  /** The switch-close path's survivor landing: the create's openers are
   *  page chrome (the header door always stands), but the board-anchored
   *  ones leave the DOM behind the loading face — a close that retired
   *  the opener lands on the survivor instead. */
  survivorFocusId?: string;
  retiredRef?: RefObject<boolean>;
}) {
  const t = useTranslation();
  const [form, setForm] = useState<EventFormState>(() => eventFormState(null));
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState(false);
  const create = useCreateTimelineEvent(novelId);
  const busy = create.isPending;
  const dirty =
    form.title !== "" || form.dateLabel !== "" || form.description !== "" ||
    form.chapterId !== "" || form.positionInput !== "" || form.names.length > 0 ||
    form.namesDraft.trim() !== "";

  const titleRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();

  const positionText = form.positionInput.trim();
  const positionInvalid = positionText !== "" && parsePosition(positionText) === null;

  function save() {
    setError(false);
    setAttempted(true);
    if (form.title.trim() === "" || positionInvalid) return;
    create.mutate(
      {
        title: form.title.trim(),
        description: form.description,
        date_label: form.dateLabel,
        // The names cross the wire with any pending draft committed — the
        // save itself is a commit, exactly as Enter, comma and blur are.
        character_names: committedNames(form),
        chapter_id: form.chapterId === "" ? null : form.chapterId,
        position: parsePosition(positionText),
      },
      { onSuccess: onClose, onError: () => setError(true) },
    );
  }

  return (
    <Modal
      openerId={openerId}
      role="dialog"
      headingId={headingId}
      onDismiss={() => {
        if (!busy && !dirty) onClose();
      }}
      scrimDismiss
      focusRef={titleRef}
      panelClassName={FORM_PANEL}
      survivorFocusId={survivorFocusId}
      retiredRef={retiredRef}
    >
      <FormHeader headingId={headingId} title={t("planning.crud.createTitle")} busy={busy} dirty={dirty} onClose={onClose} />
      <EventFields form={form} onChange={(patch) => setForm((previous) => ({ ...previous, ...patch }))} chapters={chapters} titleRef={titleRef} />
      {attempted && form.title.trim() === "" && <ValidationLine message={t("planning.crud.titleRequired")} />}
      {attempted && positionInvalid && <ValidationLine message={t("planning.crud.positionInteger")} />}
      {error && <ErrorLine message={t("planning.crud.error")} onRetry={save} />}
      <FormFooter busy={busy} saveLabel={t("planning.crud.save")} onClose={onClose} onSave={save} />
    </Modal>
  );
}

// --- The event edit --------------------------------------------------------

export function EditEventDialog({
  event,
  chapters,
  openerId,
  onClose,
  onRemove,
  suspended = false,
  survivorFocusId,
  retiredRef,
}: {
  event: TimelineEvent;
  chapters: readonly Chapter[];
  openerId: string;
  onClose: () => void;
  /** The destructive hand-off: the page opens the confirm. */
  onRemove: (event: TimelineEvent) => void;
  /** The confirm stands over this form: it keeps its state and waits. */
  suspended?: boolean;
  /** The destructive path's survivor landing: when the page's confirm
   *  retired the opener (retiredRef), this edit's own focus-return lands
   *  on the survivor instead — the landing never depends on which
   *  sibling modal's cleanup runs last. */
  survivorFocusId?: string;
  retiredRef?: RefObject<boolean>;
}) {
  const t = useTranslation();
  const [form, setForm] = useState<EventFormState>(() => eventFormState(event));
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState(false);
  const update = useUpdateTimelineEvent(event.novel_id);
  const busy = update.isPending;
  // The draft never crosses the wire (eventChanges ignores it), but it
  // holds the close paths: an answer in progress is a dirty form.
  const dirty = Object.keys(eventChanges(event, form)).length > 0 || form.namesDraft.trim() !== "";

  const titleRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();

  const positionText = form.positionInput.trim();
  const positionInvalid = positionText !== "" && parsePosition(positionText) === null;

  function save() {
    setError(false);
    setAttempted(true);
    if (form.title.trim() === "" || positionInvalid) return;
    update.mutate(
      // The names cross the wire with any pending draft committed — the
      // save itself is a commit, exactly as Enter, comma and blur are.
      { eventId: event.id, changes: eventChanges(event, { ...form, names: committedNames(form) }) },
      { onSuccess: onClose, onError: () => setError(true) },
    );
  }

  return (
    <Modal
      openerId={openerId}
      role="dialog"
      headingId={headingId}
      onDismiss={() => {
        if (!busy && !dirty && !suspended) onClose();
      }}
      scrimDismiss
      focusRef={titleRef}
      panelClassName={FORM_PANEL}
      suspended={suspended}
      survivorFocusId={survivorFocusId}
      retiredRef={retiredRef}
    >
      <FormHeader headingId={headingId} title={t("planning.crud.editTitle")} busy={busy} dirty={dirty} onClose={onClose} />
      <EventFields form={form} onChange={(patch) => setForm((previous) => ({ ...previous, ...patch }))} chapters={chapters} titleRef={titleRef} />
      {attempted && form.title.trim() === "" && <ValidationLine message={t("planning.crud.titleRequired")} />}
      {attempted && positionInvalid && <ValidationLine message={t("planning.crud.positionInteger")} />}
      {error && <ErrorLine message={t("planning.crud.error")} onRetry={save} />}
      <FormFooter busy={busy} saveLabel={t("planning.crud.saveChanges")} onClose={onClose} onSave={save} />
      {/* The draft's inspector carries the destructive remove at the form's
          foot; it hands the row to the page, which opens the confirm. Busy
          holds it — a write and a delete must not race. */}
      <button
        type="button"
        disabled={busy}
        onClick={() => onRemove(event)}
        className={`mx-auto block py-1 text-meta text-danger underline-offset-2 transition-colors hover:underline ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
      >
        {t("planning.crud.remove")}
      </button>
    </Modal>
  );
}

// --- The shared fields -----------------------------------------------------

/** The row's real fields in the draft's order: title, free-text date with
 *  its hint, description, the chapter select, the names chips, the manual
 *  position with its hint. */
function EventFields({
  form,
  onChange,
  chapters,
  titleRef,
}: {
  form: EventFormState;
  onChange: (patch: Partial<EventFormState>) => void;
  chapters: readonly Chapter[];
  titleRef: RefObject<HTMLInputElement | null>;
}) {
  const t = useTranslation();
  return (
    <>
      <div>
        <label htmlFor="event-title" className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.crud.titleLabel")}
        </label>
        <input
          id="event-title"
          ref={titleRef}
          type="text"
          value={form.title}
          maxLength={TITLE_MAX}
          onChange={(event) => onChange({ title: event.target.value })}
          className={`${INPUT} font-semibold ${FOCUS}`}
        />
      </div>
      <div>
        <label htmlFor="event-date" className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.crud.dateLabel")}
        </label>
        <input
          id="event-date"
          type="text"
          value={form.dateLabel}
          maxLength={DATE_MAX}
          onChange={(event) => onChange({ dateLabel: event.target.value })}
          className={`${INPUT} font-mono text-meta ${FOCUS}`}
        />
        <p className="mt-0.5 text-[11px] leading-snug text-muted">{t("planning.crud.dateHint")}</p>
      </div>
      <div>
        <label htmlFor="event-description" className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.crud.descriptionLabel")}
        </label>
        <textarea
          id="event-description"
          rows={3}
          value={form.description}
          onChange={(event) => onChange({ description: event.target.value })}
          className={`${INPUT} resize-y leading-relaxed ${FOCUS}`}
        />
      </div>
      <div>
        <label htmlFor="event-chapter" className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.crud.chapterLabel")}
        </label>
        <select
          id="event-chapter"
          value={form.chapterId}
          onChange={(event) => onChange({ chapterId: event.target.value })}
          className={`${INPUT} ${FOCUS}`}
        >
          <ChapterOptions chapters={chapters} />
        </select>
      </div>
      <div>
        <span className="mb-1 block text-meta font-medium text-foreground">{t("planning.crud.namesLabel")}</span>
        <NamesEditor
          names={form.names}
          draft={form.namesDraft}
          onDraftChange={(namesDraft) => onChange({ namesDraft })}
          onChange={(names) => onChange({ names })}
        />
      </div>
      <div>
        <label htmlFor="event-position" className="mb-1 block text-meta font-medium text-foreground">
          {t("planning.crud.positionLabel")}
        </label>
        <input
          id="event-position"
          type="number"
          step={1}
          value={form.positionInput}
          onChange={(event) => onChange({ positionInput: event.target.value })}
          className={`${INPUT} font-mono text-meta ${FOCUS}`}
        />
        <p className="mt-0.5 text-[11px] leading-snug text-muted">{t("planning.crud.positionHint")}</p>
      </div>
    </>
  );
}

// --- The event delete ------------------------------------------------------

export function DeleteEventDialog({
  event,
  novelId,
  openerId,
  onCancel,
  onDeleted,
  fallbackFocusId = "timeline-page",
  retiredRef,
}: {
  event: TimelineEvent;
  novelId: string;
  openerId: string;
  /** The safe answer: the confirm stands, the row stays, focus returns. */
  onCancel: () => void;
  /** The write landed: the page folds whatever pointed at the row. */
  onDeleted: () => void;
  /** The container that survives the delete, for focus when the opener goes. */
  fallbackFocusId?: string;
  /** The page's opener-retirement flag, set before the closing unmount
   *  (delete success or novel switch): the return lands on the survivor
   *  exactly then, never on an opener the close retired. Standalone, the
   *  return keeps the opener. */
  retiredRef?: RefObject<boolean>;
}) {
  const t = useTranslation();
  const [error, setError] = useState(false);
  const remove = useDeleteTimelineEvent(novelId);
  const busy = remove.isPending;

  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const bodyId = useId();

  function confirm() {
    setError(false);
    remove.mutate(event.id, {
      onSuccess: () => onDeleted(),
      onError: () => setError(true),
    });
  }

  return (
    <Modal
      openerId={openerId}
      role="alertdialog"
      headingId={headingId}
      bodyId={bodyId}
      onDismiss={() => {
        if (!busy) onCancel();
      }}
      scrimDismiss={false}
      focusRef={cancelRef}
      panelClassName={CONFIRM_PANEL}
      survivorFocusId={fallbackFocusId}
      retiredRef={retiredRef}
    >
      <ConfirmBadge icon="trash" />
      <div>
        <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
          {t("planning.crud.deleteTitle")}
        </h2>
        <p id={bodyId} className="mt-0.5 text-meta leading-snug text-muted">
          {t("planning.crud.deleteBody", { title: event.title })}
        </p>
      </div>
      {error && <ErrorLine message={t("planning.crud.deleteError")} onRetry={confirm} />}
      <ConfirmFooter
        busy={busy}
        confirmTitle={t("planning.crud.deleteNote")}
        busyLabel={t("planning.crud.deleteBusy")}
        confirmLabel={t("planning.crud.deleteConfirm")}
        onCancel={onCancel}
        onConfirm={confirm}
        cancelRef={cancelRef}
      />
    </Modal>
  );
}
