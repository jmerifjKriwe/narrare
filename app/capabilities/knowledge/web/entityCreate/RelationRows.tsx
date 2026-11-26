/**
 * The create dialog's relation rows (moved from crudDialogs, W9 Task 11): one
 * row per edge the save will place — the target, its label, an optional note —
 * with the marks that say why a filled row will not land. The notes are the
 * dialog's own (`unresolvedNoteId`, `duplicateNoteId`, the refusal alert), so a
 * marked field describes the sentence that explains it.
 */
import { useId } from "react";

import type { Entity } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { RELATION_TYPE_MAX, INPUT } from "../crudDialogs";
import type { EntityCreateRelationRow, EntityRelationRow } from "../entityCreate";
import { relationRowOutcome, resolveRowTarget } from "../entityCreate";
import { entityTypeLabel } from "../entityTypes";

/** The ids that describe a field, joined for `aria-describedby`; absent
 *  parts drop out, so one reason is one id and two are two, space-separated. */
function describedBy(...ids: (string | false | undefined)[]): string | undefined {
  const kept = ids.filter((id): id is string => typeof id === "string");
  return kept.length === 0 ? undefined : kept.join(" ");
}

export function RelationRows({
  rows,
  entities,
  entityListId,
  labelListId,
  rosterSettled,
  duplicateRows,
  refusedRow,
  unresolvedNoteId,
  duplicateNoteId,
  failureId,
  dropped,
  onUpdate,
  onRemove,
  onChoose,
}: {
  rows: readonly EntityCreateRelationRow[];
  entities: readonly Entity[];
  entityListId: string;
  labelListId: string;
  /** Whether the roster has loaded; until then a row has no outcome to show. */
  rosterSettled: boolean;
  duplicateRows: readonly number[];
  refusedRow: number | null;
  unresolvedNoteId: string;
  duplicateNoteId: string;
  failureId: string;
  dropped: number;
  onUpdate: (index: number, patch: Partial<EntityRelationRow>) => void;
  onRemove: (index: number) => void;
  /** The writer picked one of several matches: the row's target becomes the
   *  chosen entity's own name, so save-time resolution is silent again. */
  onChoose: (index: number, entity: Entity) => void;
}) {
  const t = useTranslation();
  // The choices panel's own id, per row: the target field names it while the
  // writer can pick from it.
  const choicesBaseId = useId();

  if (rows.length === 0) {
    return (
      <p className="rounded border border-rule bg-surface-container-low px-4 py-6 text-center text-meta text-muted">
        {t("knowledge.create.noRelations")}
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map((row, index) => {
        // Until the roster settles a row has no outcome: resolving against
        // the empty list would call every proposal «Kein Treffer» and count
        // it as dropped. The save waits for the same fact.
        const outcome = rosterSettled ? relationRowOutcome(row, entities) : null;
        const missingLabel = outcome === "missing-label";
        const unresolvedTarget = outcome === "unresolved-target";
        const duplicated = duplicateRows.includes(index);
        const refused = refusedRow === index;
        const targetInvalid = unresolvedTarget || duplicated || refused;
        const labelInvalid = missingLabel || duplicated || refused;
        const hasTarget = row.target.trim() !== "";
        const resolution = rosterSettled ? resolveRowTarget(row, entities) : null;
        const many = resolution?.kind === "many";
        const noMatch = resolution?.kind === "none";
        const choicesId = `${choicesBaseId}-${index}`;
        const noMatchNoteId = `${choicesBaseId}-no-match-${index}`;
        const missingLabelNoteId = `${choicesBaseId}-missing-label-${index}`;
        const targetDescribedBy = describedBy(
          unresolvedTarget && unresolvedNoteId,
          hasTarget && noMatch && noMatchNoteId,
          duplicated && duplicateNoteId,
          many && choicesId,
          refused && failureId,
        );
        const labelDescribedBy = describedBy(
          missingLabel && missingLabelNoteId,
          duplicated && duplicateNoteId,
          refused && failureId,
        );
        return (
          <div key={row.key} data-refused={refused ? "true" : undefined} className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="grid min-w-0 flex-1 grid-cols-3 gap-2">
                <div className="flex min-w-0 items-center gap-1">
                  {row.suggested && (
                    <span
                      data-testid={`entity-create-relation-${index}-suggested`}
                      className="shrink-0 text-warning"
                    >
                      <span aria-hidden="true">
                        <Icon name="spark" size={13} />
                      </span>
                      <span className="sr-only">{t("knowledge.interview.suggested")}</span>
                    </span>
                  )}
                  <input
                    data-testid={`entity-create-relation-${index}-entity`}
                    type="text"
                    list={entityListId}
                    value={row.target}
                    aria-label={t("knowledge.create.entityLabel")}
                    aria-invalid={targetInvalid || undefined}
                    aria-describedby={targetDescribedBy}
                    placeholder={t("knowledge.create.entityLabel")}
                    onChange={(event) => onUpdate(index, { target: event.target.value })}
                    className={`${INPUT} ${FOCUS} ${targetInvalid ? "ring-1 ring-danger" : ""}`}
                  />
                </div>
                <input
                  data-testid={`entity-create-relation-${index}-label`}
                  type="text"
                  list={labelListId}
                  value={row.relationType}
                  aria-label={t("knowledge.create.relationLabelLabel")}
                  aria-invalid={labelInvalid || undefined}
                  aria-describedby={labelDescribedBy}
                  placeholder={t("knowledge.create.relationLabelPlaceholder")}
                  maxLength={RELATION_TYPE_MAX}
                  onChange={(event) => onUpdate(index, { relationType: event.target.value })}
                  className={`${INPUT} ${FOCUS} ${labelInvalid ? "ring-1 ring-danger" : ""}`}
                />
                <input
                  data-testid={`entity-create-relation-${index}-note`}
                  type="text"
                  value={row.note}
                  aria-label={t("knowledge.crud.noteLabel")}
                  placeholder={t("knowledge.crud.noteLabel")}
                  onChange={(event) => onUpdate(index, { note: event.target.value })}
                  className={`${INPUT} ${FOCUS}`}
                />
              </div>
              <button
                type="button"
                aria-label={t("knowledge.create.removeRelation")}
                onClick={() => onRemove(index)}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded text-muted transition-colors hover:text-danger ${FOCUS}`}
              >
                <Icon name="trash" size={15} />
              </button>
            </div>
            {hasTarget && resolution !== null && resolution.kind === "many" && (
              <div
                id={choicesId}
                data-testid={`entity-create-relation-${index}-many`}
                className="rounded border border-warning/40 bg-surface-container px-2 py-1.5"
              >
                <p className="text-[11px] font-medium text-foreground">
                  {t("knowledge.create.multipleMatches")}
                </p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {resolution.entities.map((entity) => (
                    <button
                      key={entity.id}
                      type="button"
                      data-testid={`entity-create-relation-${index}-choice-${entity.id}`}
                      onClick={() => onChoose(index, entity)}
                      className={`inline-flex items-center gap-1.5 rounded border border-rule bg-card px-2 py-1 text-[11px] text-foreground transition-colors hover:bg-surface-container-low ${FOCUS}`}
                    >
                      {entity.name}
                      <span className="text-[10px] text-muted">
                        {entityTypeLabel(t, entity.type)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {hasTarget && resolution !== null && resolution.kind === "none" && (
              <p
                id={noMatchNoteId}
                data-testid={`entity-create-relation-${index}-no-match`}
                className="text-[11px] leading-snug text-foreground"
              >
                {t("knowledge.create.noMatch")}
              </p>
            )}
            {missingLabel && (
              <p
                id={missingLabelNoteId}
                data-testid={`entity-create-relation-${index}-missing-label`}
                className="text-[11px] leading-snug text-foreground"
              >
                {t("knowledge.create.missingLabelNote")}
              </p>
            )}
          </div>
        );
      })}
      {dropped > 0 && (
        <p
          id={unresolvedNoteId}
          data-testid="entity-create-unresolved-note"
          className="text-[11px] leading-snug text-muted"
        >
          {t("knowledge.create.unresolvedNote")}
        </p>
      )}
      {duplicateRows.length > 0 && (
        <p
          id={duplicateNoteId}
          data-testid="entity-create-relation-duplicate-note"
          className="text-[11px] leading-snug text-danger"
        >
          {t("knowledge.create.relationDuplicate")}
        </p>
      )}
    </div>
  );
}
