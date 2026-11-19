/**
 * The knowledge CRUD dialogs (W5 Task 4) — the editing layer the lore graph
 * and the dossiers mount, ported onto the modal discipline the writing
 * dialogs speak (TreeDialogs / NewBookDialog / LeaveGuardDialog): the form
 * weight for the edits (labelled fields, focus on the first answer, Tab wraps,
 * busy holds every close path, a refusal keeps the answers and names the
 * loss-free error with a retry) and the destructive calm for the deletes and
 * the merge (role="alertdialog", focus on the safe answer, Escape cancels,
 * the scrim does NOT dismiss, the consequence named before it happens). The
 * keyboard discipline rides the shell's one home (`@shell/ui/modalKeys`):
 * the trap and the wrap shared, the Escape answer each dialog's own.
 *
 * The DIRTY-STATE RULE the edits carry: pristine keeps the scrim/Escape close;
 * any typed change refuses both silent paths and holds the cross unavailable,
 * so only Abbrechen and Speichern answer while edits stand. The confirms carry
 * no typed prose — their choices are selections, and Escape cancels unless busy.
 *
 * Every mutation fires the REAL client call through the shell's query seam
 * (useUpdateEntity / useDeleteEntity / useAddRelation / useUpdateRelation /
 * useDeleteRelation / useMergeEntities); each invalidates on settling, so the
 * graph and the dossiers refetch the server's truth — no optimistic mutation,
 * the deterministic layout recomputes on the refetched rows. A 409 on an edge
 * is named as the duplicate it is (the mutation carries the status), never an
 * outage. Every close returns focus to the opener; a trigger the write itself
 * retired (a deleted row) is simply not focused, the shelf's own rule.
 *
 * New-entity creation has NO endpoint — entities are born through the
 * extraction review (the plan binds „no new backend"). There is no
 * CreateEntityDialog here; the graph's new-entity door stands an honest
 * disabled gap with its note, the wave's gap-ledger pattern.
 *
 * The module imports no other capability (rule 1): the busy spinner and the
 * error line are re-owned here on the shell's tokens, the writing family's
 * geometry, speaking the knowledge catalog's own words.
 */
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";

import type { Entity, Relation } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import {
  useAddRelation,
  useDeleteEntity,
  useDeleteRelation,
  useMergeEntities,
  useUpdateEntity,
  useUpdateRelation,
} from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";
import { useModalKeys } from "@shell/ui/modalKeys";

import { TYPE_KEYS, entityTypeLabel } from "./entityTypes";
import { relationTypeLabel, relationTypeOptions, resolveRelationType } from "./relations";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The schema's bounds, mirrored on the inputs so the writer meets them
 *  before the wire does: the name column's width, the relation type's cap. */
const NAME_MAX = 200;
const RELATION_TYPE_MAX = 80;

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
            {t("knowledge.crud.retry")}
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
  useModalKeys(panelRef, onDismiss);
  useEffect(() => {
    focusRef.current?.focus();
    return () => {
      document.getElementById(openerId)?.focus();
    };
  }, [openerId, focusRef]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]"
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
        aria-label={t("knowledge.crud.close")}
        onClick={onClose}
        className={`rounded p-0.5 text-muted transition-colors hover:text-foreground ${FOCUS} ${held ? "cursor-not-allowed opacity-50" : ""}`}
      >
        <Icon name="cross" size={14} />
      </button>
    </div>
  );
}

/** The form panel's footer: Abbrechen and the busy Speichern. */
function FormFooter({ busy, onClose, onSave }: { busy: boolean; onClose: () => void; onSave: () => void }) {
  const t = useTranslation();
  return (
    <div className="flex items-center justify-end gap-2 border-t border-rule pt-3">
      <button
        type="button"
        disabled={busy}
        onClick={onClose}
        className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
      >
        {t("knowledge.crud.cancel")}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={onSave}
        className={`inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
      >
        {busy && <Spinner />}
        {busy ? t("knowledge.crud.busy") : t("knowledge.crud.save")}
      </button>
    </div>
  );
}

function LabelledInput({
  label,
  value,
  onChange,
  inputRef,
  maxLength,
  list,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  inputRef?: RefObject<HTMLInputElement | null>;
  maxLength?: number;
  list?: string;
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
        maxLength={maxLength}
        list={list}
        onChange={(event) => onChange(event.target.value)}
        className={`${INPUT} ${FOCUS}`}
      />
    </div>
  );
}

function LabelledTextarea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-meta font-medium text-foreground">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        rows={4}
        onChange={(event) => onChange(event.target.value)}
        className={`${INPUT} resize-y leading-relaxed ${FOCUS}`}
      />
    </div>
  );
}

function LabelledSelect({
  label,
  value,
  onChange,
  selectRef,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  selectRef?: RefObject<HTMLSelectElement | null>;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-meta font-medium text-foreground">
        {label}
      </label>
      <select
        id={id}
        ref={selectRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`${INPUT} ${FOCUS}`}
      >
        {children}
      </select>
    </div>
  );
}

/** The entity options of a select: the empty placeholder plus the novel's
 *  rows, each named. `exclude` drops a row that cannot be an end (the merge's
 *  own source). */
function EntityOptions({ entities, exclude }: { entities: readonly Entity[]; exclude?: string }) {
  const t = useTranslation();
  return (
    <>
      <option value="">{t("knowledge.crud.chooseEntity")}</option>
      {entities
        .filter((entity) => entity.id !== exclude)
        .map((entity) => (
          <option key={entity.id} value={entity.id}>
            {entity.name}
          </option>
        ))}
    </>
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

const FORM_PANEL = "w-full max-w-sm space-y-3 rounded-lg border border-border bg-panel p-5 shadow-overlay";
const CONFIRM_PANEL = "w-full max-w-xs space-y-2.5 rounded-lg border border-border bg-panel p-4 text-center shadow-overlay";

/** The confirm family's footer: the safe answer first (primary), the
 *  destructive answer beside it with the consequence on its own title. */
function ConfirmFooter({
  busy,
  confirmDisabled,
  confirmTitle,
  busyLabel,
  confirmLabel,
  onCancel,
  onConfirm,
  cancelRef,
}: {
  busy: boolean;
  confirmDisabled?: boolean;
  confirmTitle: string;
  busyLabel: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
  cancelRef: RefObject<HTMLButtonElement | null>;
}) {
  const t = useTranslation();
  const held = busy || (confirmDisabled ?? false);
  return (
    <div className="flex items-center justify-center gap-2 pt-1">
      <button
        type="button"
        ref={cancelRef}
        disabled={busy}
        onClick={onCancel}
        className={`rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${busy ? "cursor-not-allowed opacity-60" : ""}`}
      >
        {t("knowledge.crud.cancel")}
      </button>
      <button
        type="button"
        disabled={held}
        onClick={onConfirm}
        title={confirmTitle}
        className={`inline-flex items-center gap-1.5 rounded border border-danger/40 px-2.5 py-1.5 text-meta font-medium text-danger transition-colors hover:bg-danger/10 ${FOCUS} ${held ? "cursor-not-allowed opacity-60" : ""}`}
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

// --- The entity edit -------------------------------------------------------

export function EditEntityDialog({
  entity,
  openerId,
  onClose,
}: {
  entity: Entity;
  openerId: string;
  onClose: () => void;
}) {
  const t = useTranslation();
  const [name, setName] = useState(entity.name);
  const [type, setType] = useState(entity.type);
  const [content, setContent] = useState(entity.content);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState(false);
  const update = useUpdateEntity(entity.novel_id);
  const busy = update.isPending;
  const dirty = name !== entity.name || type !== entity.type || content !== entity.content;

  const nameRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();

  function save() {
    setError(false);
    setAttempted(true);
    const trimmed = name.trim();
    if (trimmed === "") return;
    update.mutate(
      {
        entityId: entity.id,
        changes: { name: trimmed, type, content: content.trim() === "" ? null : content },
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
      focusRef={nameRef}
      panelClassName={FORM_PANEL}
    >
      <FormHeader headingId={headingId} title={t("knowledge.crud.editEntityTitle")} busy={busy} dirty={dirty} onClose={onClose} />
      <LabelledInput label={t("knowledge.crud.nameLabel")} value={name} onChange={setName} inputRef={nameRef} maxLength={NAME_MAX} />
      {attempted && name.trim() === "" && <ValidationLine message={t("knowledge.crud.nameRequired")} />}
      <LabelledSelect label={t("knowledge.crud.typeLabel")} value={type} onChange={setType}>
        {Object.keys(TYPE_KEYS).map((key) => (
          <option key={key} value={key}>
            {entityTypeLabel(t, key)}
          </option>
        ))}
      </LabelledSelect>
      <LabelledTextarea label={t("knowledge.crud.descriptionLabel")} value={content} onChange={setContent} />
      {error && <ErrorLine message={t("knowledge.crud.error")} onRetry={save} />}
      <FormFooter busy={busy} onClose={onClose} onSave={save} />
    </Modal>
  );
}

// --- The entity delete -----------------------------------------------------

export function DeleteEntityDialog({
  entity,
  relationCount,
  openerId,
  onClose,
  onDeleted,
}: {
  entity: Entity;
  relationCount: number;
  openerId: string;
  onClose: () => void;
  /** The write landed: the home folds the dossier before the dialog closes. */
  onDeleted?: () => void;
}) {
  const t = useTranslation();
  const [error, setError] = useState(false);
  const remove = useDeleteEntity(entity.novel_id);
  const busy = remove.isPending;

  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const bodyId = useId();

  function confirm() {
    setError(false);
    remove.mutate(entity.id, {
      onSuccess: () => {
        onDeleted?.();
        onClose();
      },
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
        if (!busy) onClose();
      }}
      scrimDismiss={false}
      focusRef={cancelRef}
      panelClassName={CONFIRM_PANEL}
    >
      <ConfirmBadge icon="trash" />
      <div>
        <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
          {t("knowledge.crud.deleteEntityTitle")}
        </h2>
        <p id={bodyId} className="mt-0.5 text-meta leading-snug text-muted">
          {t("knowledge.crud.deleteEntityBody", { name: entity.name, count: relationCount })}
        </p>
      </div>
      {error && <ErrorLine message={t("knowledge.crud.deleteError")} onRetry={confirm} />}
      <ConfirmFooter
        busy={busy}
        confirmTitle={t("knowledge.crud.deleteEntityNote")}
        busyLabel={t("knowledge.crud.deleteBusy")}
        confirmLabel={t("knowledge.crud.deleteConfirm")}
        onCancel={onClose}
        onConfirm={confirm}
        cancelRef={cancelRef}
      />
    </Modal>
  );
}

// --- The relation create ---------------------------------------------------

export function CreateRelationDialog({
  novelId,
  entities,
  from,
  openerId,
  onClose,
}: {
  novelId: string;
  entities: readonly Entity[];
  /** The fixed start when a dossier opens the box; null offers a from select. */
  from: Entity | null;
  openerId: string;
  onClose: () => void;
}) {
  const t = useTranslation();
  const initialFrom = from?.id ?? "";
  const [fromId, setFromId] = useState(initialFrom);
  const [toId, setToId] = useState("");
  const [typeInput, setTypeInput] = useState("");
  const [note, setNote] = useState("");
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState(false);
  const [duplicate, setDuplicate] = useState(false);
  const add = useAddRelation();
  const busy = add.isPending;
  const dirty = fromId !== initialFrom || toId !== "" || typeInput !== "" || note !== "";

  const fromRef = useRef<HTMLSelectElement | null>(null);
  const toRef = useRef<HTMLSelectElement | null>(null);
  const headingId = useId();
  const listId = useId();
  const resolvedType = resolveRelationType(t, typeInput);

  function save() {
    setError(false);
    setDuplicate(false);
    setAttempted(true);
    if (fromId === "" || toId === "" || resolvedType === "") return;
    add.mutate(
      {
        entityId: fromId,
        toEntityId: toId,
        relationType: resolvedType,
        note: note.trim() === "" ? null : note.trim(),
      },
      {
        onSuccess: onClose,
        onError: (err) => {
          setError(true);
          setDuplicate((err as { status?: number }).status === 409);
        },
      },
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
      focusRef={from === null ? fromRef : toRef}
      panelClassName={FORM_PANEL}
    >
      <FormHeader headingId={headingId} title={t("knowledge.crud.addRelationTitle")} busy={busy} dirty={dirty} onClose={onClose} />
      {from === null ? (
        <LabelledSelect label={t("knowledge.crud.fromLabel")} value={fromId} onChange={setFromId} selectRef={fromRef}>
          <EntityOptions entities={entities} />
        </LabelledSelect>
      ) : (
        <div>
          <span className="mb-1 block text-meta font-medium text-foreground">{t("knowledge.crud.fromLabel")}</span>
          <p className="rounded border border-rule bg-surface-container-low px-2.5 py-1.5 text-body text-foreground">{from.name}</p>
        </div>
      )}
      {attempted && fromId === "" && <ValidationLine message={t("knowledge.crud.fromRequired")} />}
      <LabelledSelect label={t("knowledge.crud.toLabel")} value={toId} onChange={setToId} selectRef={toRef}>
        <EntityOptions entities={entities} />
      </LabelledSelect>
      {attempted && toId === "" && <ValidationLine message={t("knowledge.crud.toRequired")} />}
      <LabelledInput
        label={t("knowledge.crud.relationTypeLabel")}
        value={typeInput}
        onChange={setTypeInput}
        maxLength={RELATION_TYPE_MAX}
        list={listId}
      />
      <datalist id={listId}>
        {relationTypeOptions(t).map((option) => (
          <option key={option.key} value={option.label} />
        ))}
      </datalist>
      <p className="text-[11px] leading-snug text-muted">{t("knowledge.crud.relationTypeHint")}</p>
      {attempted && resolvedType === "" && <ValidationLine message={t("knowledge.crud.relationTypeRequired")} />}
      <LabelledTextarea label={t("knowledge.crud.noteLabel")} value={note} onChange={setNote} />
      {error && (
        <ErrorLine message={duplicate ? t("knowledge.crud.relationExists") : t("knowledge.crud.error")} onRetry={save} />
      )}
      <FormFooter busy={busy} onClose={onClose} onSave={save} />
    </Modal>
  );
}

// --- The relation edit -----------------------------------------------------

export function EditRelationDialog({
  relation,
  entities,
  openerId,
  onClose,
}: {
  relation: Relation;
  entities: readonly Entity[];
  openerId: string;
  onClose: () => void;
}) {
  const t = useTranslation();
  const nameById = new Map(entities.map((row) => [row.id, row.name]));
  const fromName = nameById.get(relation.from_entity_id) ?? relation.from_entity_id;
  const toName = nameById.get(relation.to_entity_id) ?? relation.to_entity_id;
  const initialType = relationTypeLabel(t, relation.relation_type);
  const initialNote = relation.note ?? "";
  const [typeInput, setTypeInput] = useState(initialType);
  const [note, setNote] = useState(initialNote);
  const [attempted, setAttempted] = useState(false);
  const [error, setError] = useState(false);
  const [duplicate, setDuplicate] = useState(false);
  const update = useUpdateRelation();
  const busy = update.isPending;
  const dirty = typeInput !== initialType || note !== initialNote;

  const typeRef = useRef<HTMLInputElement | null>(null);
  const headingId = useId();
  const listId = useId();
  const resolvedType = resolveRelationType(t, typeInput);

  function save() {
    setError(false);
    setDuplicate(false);
    setAttempted(true);
    if (resolvedType === "") return;
    update.mutate(
      {
        relationId: relation.id,
        relationType: resolvedType,
        note: note.trim() === "" ? null : note.trim(),
      },
      {
        onSuccess: onClose,
        onError: (err) => {
          setError(true);
          setDuplicate((err as { status?: number }).status === 409);
        },
      },
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
      focusRef={typeRef}
      panelClassName={FORM_PANEL}
    >
      <FormHeader headingId={headingId} title={t("knowledge.crud.editRelationTitle")} busy={busy} dirty={dirty} onClose={onClose} />
      <p className="text-meta font-semibold text-foreground">
        {fromName} → {toName}
      </p>
      <p className="text-[11px] leading-snug text-muted">{t("knowledge.crud.editRelationHint")}</p>
      <LabelledInput
        label={t("knowledge.crud.relationTypeLabel")}
        value={typeInput}
        onChange={setTypeInput}
        inputRef={typeRef}
        maxLength={RELATION_TYPE_MAX}
        list={listId}
      />
      <datalist id={listId}>
        {relationTypeOptions(t).map((option) => (
          <option key={option.key} value={option.label} />
        ))}
      </datalist>
      {attempted && resolvedType === "" && <ValidationLine message={t("knowledge.crud.relationTypeRequired")} />}
      <LabelledTextarea label={t("knowledge.crud.noteLabel")} value={note} onChange={setNote} />
      {error && (
        <ErrorLine message={duplicate ? t("knowledge.crud.relationExists") : t("knowledge.crud.error")} onRetry={save} />
      )}
      <FormFooter busy={busy} onClose={onClose} onSave={save} />
    </Modal>
  );
}

// --- The relation delete ---------------------------------------------------

export function DeleteRelationDialog({
  relation,
  entities,
  openerId,
  onClose,
}: {
  relation: Relation;
  entities: readonly Entity[];
  openerId: string;
  onClose: () => void;
}) {
  const t = useTranslation();
  const nameById = new Map(entities.map((row) => [row.id, row.name]));
  const fromName = nameById.get(relation.from_entity_id) ?? relation.from_entity_id;
  const toName = nameById.get(relation.to_entity_id) ?? relation.to_entity_id;
  const [error, setError] = useState(false);
  const remove = useDeleteRelation();
  const busy = remove.isPending;

  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const bodyId = useId();

  function confirm() {
    setError(false);
    remove.mutate(
      { relationId: relation.id },
      { onSuccess: onClose, onError: () => setError(true) },
    );
  }

  return (
    <Modal
      openerId={openerId}
      role="alertdialog"
      headingId={headingId}
      bodyId={bodyId}
      onDismiss={() => {
        if (!busy) onClose();
      }}
      scrimDismiss={false}
      focusRef={cancelRef}
      panelClassName={CONFIRM_PANEL}
    >
      <ConfirmBadge icon="trash" />
      <div>
        <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
          {t("knowledge.crud.deleteRelationTitle")}
        </h2>
        <p id={bodyId} className="mt-0.5 text-meta leading-snug text-muted">
          {t("knowledge.crud.deleteRelationBody", {
            from: fromName,
            to: toName,
            type: relationTypeLabel(t, relation.relation_type),
          })}
        </p>
      </div>
      {error && <ErrorLine message={t("knowledge.crud.deleteError")} onRetry={confirm} />}
      <ConfirmFooter
        busy={busy}
        confirmTitle={t("knowledge.crud.deleteRelationNote")}
        busyLabel={t("knowledge.crud.deleteBusy")}
        confirmLabel={t("knowledge.crud.deleteConfirm")}
        onCancel={onClose}
        onConfirm={confirm}
        cancelRef={cancelRef}
      />
    </Modal>
  );
}

// --- The merge -------------------------------------------------------------

export function MergeDialog({
  novelId,
  entities,
  source,
  openerId,
  onClose,
  onMerged,
}: {
  novelId: string;
  entities: readonly Entity[];
  /** The fixed source when a dossier opens the box; null offers a source select. */
  source: Entity | null;
  openerId: string;
  onClose: () => void;
  /** The write landed: the home moves the selection to the survivor. */
  onMerged?: (targetId: string) => void;
}) {
  const t = useTranslation();
  const [sourceId, setSourceId] = useState(source?.id ?? "");
  const [targetId, setTargetId] = useState("");
  const [error, setError] = useState(false);
  const merge = useMergeEntities(novelId);
  const busy = merge.isPending;

  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const headingId = useId();
  const bodyId = useId();

  const sourceName = entities.find((row) => row.id === sourceId)?.name ?? "";
  const targetName = entities.find((row) => row.id === targetId)?.name ?? "";
  const ready = sourceId !== "" && targetId !== "" && sourceId !== targetId;

  function confirm() {
    setError(false);
    if (!ready) return;
    merge.mutate(
      { sourceId, targetId },
      {
        onSuccess: (target) => {
          onMerged?.(target.id);
          onClose();
        },
        onError: () => setError(true),
      },
    );
  }

  return (
    <Modal
      openerId={openerId}
      role="alertdialog"
      headingId={headingId}
      bodyId={bodyId}
      onDismiss={() => {
        if (!busy) onClose();
      }}
      scrimDismiss={false}
      focusRef={cancelRef}
      panelClassName={CONFIRM_PANEL}
    >
      <ConfirmBadge icon="copy" />
      <div>
        <h2 id={headingId} className={`${SERIF} text-body font-semibold text-foreground`}>
          {t("knowledge.crud.mergeTitle")}
        </h2>
        <p id={bodyId} className="mt-0.5 text-meta leading-snug text-muted">
          {ready
            ? t("knowledge.crud.mergeBody", { source: sourceName, target: targetName })
            : t("knowledge.crud.mergeTargetRequired")}
        </p>
      </div>
      {source === null ? (
        <LabelledSelect label={t("knowledge.crud.mergeSourceLabel")} value={sourceId} onChange={setSourceId}>
          <EntityOptions entities={entities} />
        </LabelledSelect>
      ) : (
        <div className="text-left">
          <span className="mb-1 block text-meta font-medium text-foreground">{t("knowledge.crud.mergeSourceLabel")}</span>
          <p className="rounded border border-rule bg-surface-container-low px-2.5 py-1.5 text-body text-foreground">{source.name}</p>
        </div>
      )}
      <LabelledSelect label={t("knowledge.crud.mergeTargetLabel")} value={targetId} onChange={setTargetId}>
        <EntityOptions entities={entities} exclude={sourceId} />
      </LabelledSelect>
      <p className="text-[11px] leading-snug text-danger">{t("knowledge.crud.mergeNote")}</p>
      {error && <ErrorLine message={t("knowledge.crud.mergeError")} onRetry={confirm} />}
      <ConfirmFooter
        busy={busy}
        confirmDisabled={!ready}
        confirmTitle={t("knowledge.crud.mergeNote")}
        busyLabel={t("knowledge.crud.mergeBusy")}
        confirmLabel={t("knowledge.crud.mergeConfirm")}
        onCancel={onClose}
        onConfirm={confirm}
        cancelRef={cancelRef}
      />
    </Modal>
  );
}
