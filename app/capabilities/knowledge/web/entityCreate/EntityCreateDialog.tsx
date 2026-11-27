/**
 * The entity create dialog (moved from crudDialogs, W9 Task 11): one dialog for
 * both paths — the hand-made form and, from the interview, a prefilled draft.
 * A name that already exists is a quiet notice that keeps saving possible; a
 * relation row resolves against the roster by name or alias, and the rows the
 * novel cannot resolve are left out and counted below the section.
 */
import { useId, useMemo, useRef, useState } from "react";

import type { Entity } from "@shell/lib/api/client";
import { isNetworkFailure, type ApiError } from "@shell/lib/api/errors";
import { useTranslation } from "@shell/lib/i18n";
import { useCreateEntity } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { FormHeader, INPUT, Modal, NAME_MAX, Spinner } from "../crudDialogs";
import {
  MAX_RELATIONS,
  buildEntityCreateBody,
  createFormState,
  duplicateRelationRows,
  findDuplicateName,
  keptRelationRows,
  refusalCatalogKey,
  refusalNamesRelationRow,
  relationRowOutcome,
  visibleRowForSentIndex,
  type EntityCreateRelationRow,
  type EntityCreateSource,
  type EntityPrefill,
  type EntityRelationRow,
} from "../entityCreate";
import { TYPE_KEYS, entityTypeLabel } from "../entityTypes";
import { relationTypeOptions, resolveRelationType } from "../relations";
import { ChipInput, withChip } from "./ChipInput";
import { RelationRows } from "./RelationRows";
import { SuggestedMark } from "../SuggestedMark";

const CREATE_PANEL =
  "max-h-[calc(100vh-2rem)] w-full max-w-xl space-y-3 overflow-y-auto rounded-lg border border-border bg-panel p-5 shadow-overlay";

/** Whether two chip lists hold the same values in the same order. */
function sameList(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

/** Whether two relation lists are the same draft: the door's starting rows
 *  carry no change of their own. */
function sameRows(
  left: readonly EntityCreateRelationRow[],
  right: readonly EntityCreateRelationRow[],
): boolean {
  return (
    left.length === right.length &&
    left.every((row, index) => {
      const base = right[index];
      return (
        base !== undefined &&
        row.key === base.key &&
        row.target === base.target &&
        row.relationType === base.relationType &&
        row.note === base.note &&
        row.suggested === base.suggested &&
        row.chosenId === base.chosenId
      );
    })
  );
}

export function EntityCreateDialog({
  novelId,
  entities,
  openerId,
  createdFocusId,
  onClose,
  onCreated,
  source = "manual",
  prefill,
  rosterSettled = true,
}: {
  novelId: string;
  entities: readonly Entity[];
  openerId: string;
  /** A create landed: focus this control before closing. The opener is the
   *  dialog's own door, which a handover has just shut; the next action is
   *  named here instead. The modal's cleanup then no-ops on the shut opener. */
  createdFocusId?: string;
  onClose: () => void;
  /** The write landed: the home selects the new row and counts its edges. */
  onCreated?: (entity: Entity, relations: number) => void;
  /** Which door opened the dialog: the hand-made form or the interview. */
  source?: EntityCreateSource;
  /** The interview's draft; absent for the hand-made form. */
  prefill?: EntityPrefill;
  /** Whether the roster the rows resolve against has loaded. Until it has,
   *  a proposed row carries no outcome and the save waits: resolving against
   *  an empty list would read every proposal as «Kein Treffer» and drop it. */
  rosterSettled?: boolean;
}) {
  const t = useTranslation();
  // The starting state is the door's own: the hand-made form empty, the
  // interview's prefill carried with its marks and its locked type.
  const [initial] = useState(() => createFormState({ source, prefill }));
  const [name, setName] = useState(initial.name);
  const [type, setType] = useState(initial.type);
  const [aliases, setAliases] = useState<string[]>(initial.aliases);
  const [tags, setTags] = useState<string[]>(initial.tags);
  const [aliasDraft, setAliasDraft] = useState("");
  const [tagDraft, setTagDraft] = useState("");
  const [content, setContent] = useState(initial.content);
  const [relations, setRelations] = useState<EntityCreateRelationRow[]>(initial.relations);
  const [failure, setFailure] = useState<ApiError | null>(null);
  /** The visible row a relation refusal names; the sent list's index is
   *  mapped back through the rows the body builder kept. */
  const [refusedRow, setRefusedRow] = useState<number | null>(null);
  const create = useCreateEntity();
  const busy = create.isPending;
  const typeLocked = initial.typeLocked;
  const suggested = initial.suggested;
  // Dirty means changed against this door's own starting state: empty by
  // hand, the interview's prefill from the panel. An untouched prefilled
  // dialog closes on Escape like an untouched manual one; the first edit
  // brings the guard back.
  const dirty =
    aliasDraft !== "" ||
    tagDraft !== "" ||
    name !== initial.name ||
    type !== initial.type ||
    !sameList(aliases, initial.aliases) ||
    !sameList(tags, initial.tags) ||
    content !== initial.content ||
    !sameRows(relations, initial.relations);

  const nameRef = useRef<HTMLInputElement | null>(null);
  const relationKey = useRef(initial.relations.length);
  const headingId = useId();
  const entityListId = useId();
  const labelListId = useId();
  // The notes a marked field points at; the alert describes a wire refusal.
  const unresolvedNoteId = `${headingId}-unresolved-note`;
  const relationDuplicateNoteId = `${headingId}-relation-duplicate-note`;
  const relationLimitNoteId = `${headingId}-relation-limit-note`;
  const failureId = `${headingId}-create-failure`;

  const duplicate = findDuplicateName(name, entities);
  // The labels as the save will send them, so the duplicate flag compares
  // the same identity the server's unique constraint does: a localized
  // wording beside its canonical key is one relation.
  const normalizedRelations = relations.map((row) => ({
    ...row,
    relationType: resolveRelationType(t, row.relationType),
  }));
  const duplicateRows = rosterSettled ? duplicateRelationRows(normalizedRelations, entities) : [];
  // Every filled row the save will drop for its target alone — a target that
  // does not resolve (or is still blank) is an unresolved target; a row with
  // a missing label has its own per-row note and is not counted here. Only an
  // untouched add-row stays silent. While the roster is loading there is no
  // outcome yet.
  const dropped = rosterSettled
    ? relations.filter((row) => relationRowOutcome(row, entities) === "unresolved-target").length
    : 0;
  const atLimit = relations.length >= MAX_RELATIONS;
  // The save waits for a settled roster: its body resolves every row there.
  const ready = name.trim() !== "" && type !== "" && rosterSettled;
  // The closed-set code's catalog sentence; a synthetic or unknown code
  // falls back to the generic catalog sentence, never the wire's English.
  const refusalKey = failure === null ? null : refusalCatalogKey(failure.code);
  const entityNames = useMemo(
    () => [...new Set(entities.flatMap((entity) => [entity.name, ...entity.aliases]))],
    [entities],
  );

  function updateRelation(index: number, patch: Partial<EntityRelationRow>) {
    setRefusedRow(null);
    setRelations((rows) =>
      rows.map((row, rowIndex) =>
        rowIndex === index
          ? {
              ...row,
              ...patch,
              // A typed target is a new question: the old pick no longer
              // answers it. An explicit pick carries its id in the patch.
              chosenId: patch.target !== undefined ? patch.chosenId : row.chosenId,
            }
          : row,
      ),
    );
  }

  function addRelationRow() {
    setRefusedRow(null);
    relationKey.current += 1;
    setRelations((rows) => [
      ...rows,
      { key: relationKey.current, target: "", relationType: "", note: "", suggested: false },
    ]);
  }

  function removeRelationRow(index: number) {
    setRefusedRow(null);
    setRelations((rows) => rows.filter((_row, rowIndex) => rowIndex !== index));
  }

  /** A pick from «Mehrere Treffer — wählen»: the row remembers the entity, so
   *  the choice holds even when the name is another row's alias. */
  function chooseRelationTarget(index: number, entity: Entity) {
    updateRelation(index, { target: entity.name, chosenId: entity.id });
  }

  function save() {
    setFailure(null);
    setRefusedRow(null);
    if (!ready) return;
    // A chip the writer typed but never confirmed with Enter still belongs to
    // the save: flush both drafts into the lists, then send the lists.
    const nextAliases = withChip(aliases, aliasDraft);
    const nextTags = withChip(tags, tagDraft);
    setAliases(nextAliases);
    setTags(nextTags);
    setAliasDraft("");
    setTagDraft("");
    const body = buildEntityCreateBody({
      novelId,
      name,
      type,
      aliases: nextAliases,
      tags: nextTags,
      content,
      entities,
      relations: normalizedRelations,
    });
    create.mutate(body, {
      onSuccess: (entity) => {
        onCreated?.(entity, body.relations?.length ?? 0);
        // The next action, placed before the dialog unmounts: the modal's own
        // return lands on the opener, which a handover has just shut.
        if (createdFocusId !== undefined) {
          document.getElementById(createdFocusId)?.focus();
        }
        onClose();
      },
      onError: (error) => {
        setFailure(error);
        // The relation codes carry the refused line's index in the SENT
        // list; the writer sees visible rows, so it is mapped back.
        const row = error.extra.row;
        if (typeof row === "number" && refusalNamesRelationRow(error.code)) {
          setRefusedRow(
            visibleRowForSentIndex(keptRelationRows(normalizedRelations, entities), row),
          );
        }
      },
    });
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
      panelClassName={CREATE_PANEL}
      panelTestId="entity-create-dialog"
    >
      <FormHeader
        headingId={headingId}
        title={t("knowledge.create.title")}
        badge={
          source === "interview"
            ? t("knowledge.create.sourceInterview")
            : t("knowledge.create.manualBadge")
        }
        busy={busy}
        dirty={dirty}
        onClose={onClose}
      />
      <div className="space-y-3">
        <fieldset disabled={busy} className="m-0 min-w-0 space-y-3 border-0 p-0">
          <div>
            <label htmlFor={`${headingId}-name`} className="mb-1 block text-meta font-medium text-foreground">
              {t("knowledge.create.nameLabel")}
            </label>
            <input
              id={`${headingId}-name`}
              ref={nameRef}
              data-testid="entity-create-name"
              type="text"
              value={name}
              maxLength={NAME_MAX}
              placeholder={t("knowledge.create.namePlaceholder")}
              onChange={(event) => setName(event.target.value)}
              className={`${INPUT} ${FOCUS}`}
            />
          </div>
          {duplicate !== null && (
            <div
              data-testid="entity-create-duplicate-note"
              role="status"
              className="flex items-start gap-1.5 rounded border border-rule bg-surface-container-low px-2.5 py-2 text-meta leading-snug text-foreground"
            >
              <span className="mt-0.5 shrink-0 text-primary">
                <Icon name="info" size={13} />
              </span>
              <p>{t("knowledge.create.duplicateNote")}</p>
            </div>
          )}
          <div>
            {typeLocked ? (
              <span
                id={`${headingId}-type-label`}
                className="mb-1 block text-meta font-medium text-foreground"
              >
                {t("knowledge.create.typeLabel")}
              </span>
            ) : (
              <label htmlFor={`${headingId}-type`} className="mb-1 block text-meta font-medium text-foreground">
                {t("knowledge.create.typeLabel")}
              </label>
            )}
            {typeLocked ? (
              <div
                id={`${headingId}-type`}
                role="group"
                aria-labelledby={`${headingId}-type-label`}
                data-testid="entity-create-type-locked"
                className="flex items-center justify-between gap-2 rounded border border-border bg-surface-container-low px-2.5 py-1.5"
              >
                <span className="flex items-center gap-1.5 text-body text-foreground">
                  <Icon name="lock" size={14} />
                  <span className="font-medium">{entityTypeLabel(t, type)}</span>
                </span>
                <span className="rounded bg-surface-container-high px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-foreground">
                  {t("knowledge.create.locked")}
                </span>
              </div>
            ) : (
              <select
                id={`${headingId}-type`}
                data-testid="entity-create-type"
                value={type}
                onChange={(event) => setType(event.target.value)}
                className={`${INPUT} ${FOCUS}`}
              >
                <option value="">{t("knowledge.create.typePlaceholder")}</option>
                {Object.keys(TYPE_KEYS).map((key) => (
                  <option key={key} value={key}>
                    {entityTypeLabel(t, key)}
                  </option>
                ))}
              </select>
            )}
          </div>
          <ChipInput
            testId="entity-create-aliases"
            label={t("knowledge.create.aliasesLabel")}
            hint={t("knowledge.create.addHint")}
            placeholder={t("knowledge.create.aliasPlaceholder")}
            values={aliases}
            draft={aliasDraft}
            onDraftChange={setAliasDraft}
            onChange={setAliases}
            suggestedValues={suggested?.aliases}
          />
          <ChipInput
            testId="entity-create-tags"
            label={t("knowledge.create.tagsLabel")}
            hint={t("knowledge.create.addHint")}
            placeholder={t("knowledge.create.tagPlaceholder")}
            values={tags}
            draft={tagDraft}
            onDraftChange={setTagDraft}
            onChange={setTags}
            suggestedValues={suggested?.tags}
          />
          <div>
            <label htmlFor={`${headingId}-content`} className="mb-1 flex items-center gap-1 text-meta font-medium text-foreground">
              {t("knowledge.create.descriptionLabel")}
              {suggested?.content === true && <SuggestedMark />}
            </label>
            <textarea
              id={`${headingId}-content`}
              data-testid="entity-create-content"
              value={content}
              rows={3}
              placeholder={t("knowledge.create.descriptionPlaceholder")}
              onChange={(event) => setContent(event.target.value)}
              className={`${INPUT} resize-y leading-relaxed ${FOCUS}`}
            />
          </div>
          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between gap-2">
              <span className="text-meta font-semibold text-foreground">
                {t("knowledge.create.relationsLabel")}
              </span>
              <button
                type="button"
                data-testid="entity-create-add-relation"
                disabled={atLimit}
                aria-describedby={atLimit ? relationLimitNoteId : undefined}
                onClick={addRelationRow}
                className={`inline-flex min-h-6 items-center gap-1 text-meta font-medium text-primary transition-colors hover:text-foreground ${FOCUS} ${atLimit ? "cursor-not-allowed opacity-50" : ""}`}
              >
                <Icon name="plus" size={14} /> {t("knowledge.create.addRelation")}
              </button>
            </div>
            {atLimit && (
              <p
                id={relationLimitNoteId}
                data-testid="entity-create-relation-limit-note"
                className="text-[11px] leading-snug text-muted"
              >
                {t("knowledge.create.relationLimit")}
              </p>
            )}
            <RelationRows
              rows={relations}
              entities={entities}
              entityListId={entityListId}
              labelListId={labelListId}
              rosterSettled={rosterSettled}
              duplicateRows={duplicateRows}
              refusedRow={refusedRow}
              unresolvedNoteId={unresolvedNoteId}
              duplicateNoteId={relationDuplicateNoteId}
              failureId={failureId}
              dropped={dropped}
              onUpdate={updateRelation}
              onRemove={removeRelationRow}
              onChoose={chooseRelationTarget}
            />
            <datalist id={entityListId}>
              {entityNames.map((entityName) => (
                <option key={entityName} value={entityName} />
              ))}
            </datalist>
            <datalist id={labelListId}>
              {relationTypeOptions(t).map((option) => (
                <option key={option.key} value={option.label} />
              ))}
            </datalist>
          </div>
        </fieldset>
        {failure !== null && (
          <div
            id={failureId}
            role="alert"
            className="rounded border border-danger/40 bg-danger/10 px-2.5 py-2 text-meta text-foreground"
          >
            <div className="flex items-start gap-1.5">
              <span className="mt-0.5 shrink-0 text-danger">
                <Icon name="warning" size={13} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="leading-snug">
                  {isNetworkFailure(failure)
                    ? t("knowledge.create.failedTransport")
                    : refusalKey !== null
                      ? t(refusalKey)
                      : t("knowledge.create.failedUnexpected")}
                </p>
                {failure.code !== null && (
                  <p
                    data-testid="entity-create-refusal-code"
                    className="mt-0.5 font-mono text-[11px] text-danger"
                  >
                    {failure.code}
                  </p>
                )}
                <button
                  type="button"
                  onClick={save}
                  className={`mt-1 inline-flex items-center gap-1 text-meta font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
                >
                  {t("knowledge.crud.retry")}
                  <Icon name="refresh" size={12} />
                </button>
              </div>
            </div>
          </div>
        )}
        <div className="flex items-center justify-between gap-2 border-t border-rule pt-3">
          <span className="text-meta text-muted">{t("knowledge.create.footerHint")}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="entity-create-cancel"
              disabled={busy}
              onClick={onClose}
              className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS} ${busy ? "cursor-not-allowed opacity-50" : ""}`}
            >
              {t("knowledge.crud.cancel")}
            </button>
            <button
              type="button"
              data-testid="entity-create-save"
              disabled={!ready || busy}
              onClick={save}
              className={`inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS} ${!ready || busy ? "cursor-not-allowed opacity-60" : ""}`}
            >
              {busy && <Spinner />}
              {busy ? t("knowledge.crud.busy") : t("knowledge.create.save")}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
