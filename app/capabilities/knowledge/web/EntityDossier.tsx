/**
 * The entity dossier (W5 Tasks 3/5) — the shared detail component with two
 * homes: the graph's inline panel and the dossiers page's detail column.
 * One component, two homes: it reads the REAL EntityRead fields (name, type,
 * the Markdown body as the description, aliases, tags) and the entity's real
 * relations, and renders the draft's invented fields as honest disabled
 * areas with their gap notes — never fake content:
 *
 * - The status line („Aktiv • …" in the draft) is invented: no per-entity
 *   status exists on any model, so it stands as a neutral gap row.
 * - Manuscript excerpts: no mention tracking exists — a disabled area with
 *   its gap note, never an invented quotation.
 * - Bookmark / export: no endpoint serves them — disabled with their notes.
 * - Edit / delete / quick-add relation and each relation card's edit/delete
 *   (W5 Task 4): the real CRUD dialogs (`crudDialogs.tsx`) — the disabled
 *   placeholders retired. The mutations refetch the server's truth.
 * - Jump to manuscript: no mention tracking — disabled with its gap note.
 *
 * The panel imports no other capability (rule 1); it speaks through the
 * shell's tokens and the capability's own type/relation vocabulary.
 *
 * The optional `children` slot (Task 5) is the home's own addition to the
 * detail's flow — the dossiers page injects the draft's two profile gap
 * areas (psychological, linguistic) between the excerpts gap and the action
 * footer. The graph passes nothing: its render is unchanged.
 */
import { useState, type ReactNode } from "react";

import type { Entity, Relation } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { CARD_EYEBROW, FOCUS, NeutralRow } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import {
  CreateRelationDialog,
  DeleteEntityDialog,
  DeleteRelationDialog,
  EditEntityDialog,
  EditRelationDialog,
} from "./crudDialogs";
import { entityTypeLabel, typeTheme } from "./entityTypes";
import { relationTypeLabel } from "./relations";

/** Which CRUD dialog the dossier has open — one at a time, the relation
 *  kinds carrying the edge they act on. */
type DossierDialog =
  | { kind: "edit" }
  | { kind: "delete" }
  | { kind: "addRelation" }
  | { kind: "editRelation"; relation: Relation }
  | { kind: "deleteRelation"; relation: Relation };

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The first letter of the name, the avatar's monogram — or a neutral mark. */
function monogram(name: string): string {
  return Array.from(name.trim())[0]?.toUpperCase() ?? "?";
}

/** A disabled action with its honest gap note as the tooltip — the draft's
 *  button geometry, no dead promise. */
function GapButton({
  label,
  note,
  icon,
  primary = false,
}: {
  label: string;
  note: string;
  icon: Parameters<typeof Icon>[0]["name"];
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      disabled
      title={`${label} (${note})`}
      aria-label={`${label} (${note})`}
      className={`flex w-full items-center justify-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-meta font-medium opacity-60 cursor-not-allowed ${
        primary
          ? "bg-primary text-primary-foreground"
          : "bg-surface-container-high text-foreground"
      }`}
    >
      <Icon name={icon} size={14} />
      <span>{label}</span>
    </button>
  );
}

export function EntityDossier({
  entity,
  relations,
  entities,
  onClose,
  onSelectEntity,
  focusFallbackId,
  children,
}: {
  entity: Entity;
  relations: readonly Relation[];
  entities: readonly Entity[];
  onClose: () => void;
  onSelectEntity: (id: string) => void;
  /** The home's surviving container, for focus when a delete folds this
   *  dossier — each home passes its focusable page root (the graph
   *  `graph-page`, the dossiers page `dossiers-page`). */
  focusFallbackId?: string;
  /** The home's own gap areas, rendered in the detail's flow after the
   *  excerpts gap (the dossiers page's profile areas; the graph passes none). */
  children?: ReactNode;
}) {
  const t = useTranslation();
  const theme = typeTheme(entity.type);
  const nameById = new Map(entities.map((row) => [row.id, row]));
  const [dialog, setDialog] = useState<DossierDialog | null>(null);
  const closeDialog = () => setDialog(null);

  return (
    <>
    <aside
      id="entity-dossier"
      data-testid="entity-dossier"
      tabIndex={-1}
      aria-label={t("knowledge.dossier.title")}
      className="flex h-full w-full flex-col overflow-y-auto border-l border-border bg-panel focus:outline-none"
    >
      <div className="flex flex-col gap-5 p-5">
        {/* The panel header — the eyebrow left, the invented bookmark/export
            doors disabled with their notes, and the close that folds it. */}
        <div className="flex items-center justify-between border-b border-rule pb-3">
          <span className={CARD_EYEBROW}>{t("knowledge.dossier.title")}</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled
              title={`${t("knowledge.dossier.bookmark")} (${t("knowledge.dossier.bookmarkNote")})`}
              aria-label={`${t("knowledge.dossier.bookmark")} (${t("knowledge.dossier.bookmarkNote")})`}
              className="flex h-7 w-7 cursor-not-allowed items-center justify-center rounded text-muted opacity-60"
            >
              <Icon name="bookmarkCollection" size={15} />
            </button>
            <button
              type="button"
              disabled
              title={`${t("knowledge.dossier.export")} (${t("knowledge.dossier.exportNote")})`}
              aria-label={`${t("knowledge.dossier.export")} (${t("knowledge.dossier.exportNote")})`}
              className="flex h-7 w-7 cursor-not-allowed items-center justify-center rounded text-muted opacity-60"
            >
              <Icon name="export" size={15} />
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("knowledge.dossier.close")}
              className={`flex h-7 w-7 items-center justify-center rounded text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
            >
              <Icon name="cross" size={15} />
            </button>
          </div>
        </div>

        {/* The bio card — the avatar in the type's tint, the name, the type
            badge (the colour is the dot; the words stay neutral for AA), and
            the invented status as a neutral gap row. */}
        <div className="flex items-start gap-3.5">
          <div
            className={`${SERIF} flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--radius-surface)] text-title font-bold italic ${theme.tint}`}
            style={{ color: theme.var }}
            aria-hidden="true"
          >
            {monogram(entity.name)}
          </div>
          <div className="min-w-0 flex-1">
            <h2 className={`${SERIF} truncate text-title font-bold text-foreground`}>{entity.name}</h2>
            <div className="mt-1 flex items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-foreground ${theme.tint}`}>
                <span aria-hidden="true" className={`h-2 w-2 rounded-full ${theme.dot}`} />
                {entityTypeLabel(t, entity.type)}
              </span>
            </div>
          </div>
        </div>

        {/* The invented status — no model carries it, so the neutral gap row
            stands in the draft's place, never a fake „Aktiv". */}
        <NeutralRow label={t("knowledge.dossier.status")} />

        {/* The description — the entity's real Markdown body, shown as the
            plain source the storage keeps; an empty body reads as empty. */}
        <div className="rounded-[var(--radius-surface)] border border-rule bg-surface-container-low p-3.5">
          <span className={`${CARD_EYEBROW} mb-1 block`}>{t("knowledge.dossier.description")}</span>
          {entity.content.trim() !== "" ? (
            <p className="whitespace-pre-wrap text-body leading-relaxed text-foreground">{entity.content}</p>
          ) : (
            <p className="text-body italic text-muted">{t("knowledge.dossier.noDescription")}</p>
          )}
        </div>

        {/* Aliases and tags — real fields, shown only when the row carries
            them; an empty list invents no block. */}
        {entity.aliases.length > 0 && (
          <div className="space-y-1.5">
            <span className={CARD_EYEBROW}>{t("knowledge.dossier.aliases")}</span>
            <div className="flex flex-wrap gap-1.5">
              {entity.aliases.map((alias) => (
                <span key={alias} className="rounded-full bg-surface-container-high px-2 py-0.5 text-meta text-foreground">
                  {alias}
                </span>
              ))}
            </div>
          </div>
        )}
        {entity.tags.length > 0 && (
          <div className="space-y-1.5">
            <span className={CARD_EYEBROW}>{t("knowledge.dossier.tags")}</span>
            <div className="flex flex-wrap gap-1.5">
              {entity.tags.map((tag) => (
                <span key={tag} className="rounded-full bg-surface-container-high px-2 py-0.5 text-meta text-muted">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* The relations — the entity's real edges, both directions. Each
            card names the other end (a door that selects it), the type's
            wording and the note. The quick-add is Task 4's, disabled. */}
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <h3 className={CARD_EYEBROW}>
              {t("knowledge.dossier.relations")} ({relations.length})
            </h3>
            <button
              type="button"
              id="dossier-add-relation"
              onClick={() => setDialog({ kind: "addRelation" })}
              className={`flex items-center gap-0.5 rounded text-meta text-primary transition-colors hover:text-foreground ${FOCUS}`}
            >
              <Icon name="plus" size={13} /> {t("knowledge.dossier.addRelation")}
            </button>
          </div>
          {relations.length === 0 ? (
            <p className="text-meta italic text-muted">{t("knowledge.dossier.noRelations")}</p>
          ) : (
            <ul
              id="dossier-relations"
              tabIndex={-1}
              aria-label={t("knowledge.dossier.relations")}
              className="flex flex-col gap-2 focus:outline-none"
            >
              {relations.map((relation) => {
                const outgoing = relation.from_entity_id === entity.id;
                const otherId = outgoing ? relation.to_entity_id : relation.from_entity_id;
                const other = nameById.get(otherId);
                const otherTheme = typeTheme(other?.type ?? "generic");
                return (
                  <li
                    key={relation.id}
                    className="rounded-[var(--radius-control)] border border-rule bg-surface-container-low transition-colors hover:bg-surface-container"
                  >
                    <div className="flex items-start gap-1 p-2.5">
                      <button
                        type="button"
                        onClick={() => onSelectEntity(otherId)}
                        className={`min-w-0 flex-1 rounded text-left ${FOCUS}`}
                      >
                        <span className="flex items-center justify-between gap-2">
                          <span className="flex min-w-0 items-center gap-1.5">
                            <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${otherTheme.dot}`} />
                            <span className="truncate text-meta font-semibold text-foreground">
                              {other?.name ?? otherId}
                            </span>
                            <span aria-hidden="true" className="shrink-0 text-muted">
                              {outgoing ? "→" : "←"}
                            </span>
                          </span>
                          <span className="shrink-0 text-[11px] text-primary">
                            {relationTypeLabel(t, relation.relation_type)}
                          </span>
                        </span>
                        {relation.note !== null && relation.note.trim() !== "" && (
                          <span className="mt-1 block text-meta leading-relaxed text-muted">{relation.note}</span>
                        )}
                      </button>
                      {/* The edge's own edit/delete doors — beside the select
                          door, never nested in it (valid HTML). */}
                      <span className="flex shrink-0 items-center gap-0.5">
                        <button
                          type="button"
                          id={`dossier-relation-edit-${relation.id}`}
                          onClick={() => setDialog({ kind: "editRelation", relation })}
                          aria-label={`${t("knowledge.crud.editRelationTitle")}: ${other?.name ?? otherId}`}
                          title={`${t("knowledge.crud.editRelationTitle")}: ${other?.name ?? otherId}`}
                          className={`flex h-6 w-6 items-center justify-center rounded text-muted transition-colors hover:bg-surface-container-high hover:text-foreground ${FOCUS}`}
                        >
                          <Icon name="editNote" size={13} />
                        </button>
                        <button
                          type="button"
                          id={`dossier-relation-delete-${relation.id}`}
                          onClick={() => setDialog({ kind: "deleteRelation", relation })}
                          aria-label={`${t("knowledge.crud.deleteRelationTitle")}: ${other?.name ?? otherId}`}
                          title={`${t("knowledge.crud.deleteRelationTitle")}: ${other?.name ?? otherId}`}
                          className={`flex h-6 w-6 items-center justify-center rounded text-muted transition-colors hover:bg-danger/10 hover:text-danger ${FOCUS}`}
                        >
                          <Icon name="trash" size={13} />
                        </button>
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Manuscript excerpts — invented: no mention tracking exists. The
            area stands disabled with its gap note, never a fake quotation. */}
        <div className="flex flex-col gap-2">
          <h3 className={CARD_EYEBROW}>{t("knowledge.dossier.excerpts")}</h3>
          <div
            aria-disabled="true"
            className="rounded-[var(--radius-control)] border border-dashed border-border bg-surface-container-low/50 p-3 opacity-70"
          >
            <p className="text-meta italic text-muted">{t("knowledge.dossier.excerptsGap")}</p>
          </div>
        </div>

        {/* The home's own gap areas (the dossiers page's profile areas). */}
        {children}
      </div>

      {/* The action footer — edit and delete open the real CRUD dialogs
          (Task 4); jump needs mention tracking and stays an honest gap. */}
      <div className="mt-auto flex flex-col gap-2 border-t border-rule bg-surface-container-low p-5">
        <button
          type="button"
          id="dossier-edit"
          onClick={() => setDialog({ kind: "edit" })}
          className={`flex w-full items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground shadow-sm transition-all hover:opacity-95 ${FOCUS}`}
        >
          <Icon name="editNote" size={14} />
          <span>{t("knowledge.dossier.edit")}</span>
        </button>
        <button
          type="button"
          id="dossier-delete"
          onClick={() => setDialog({ kind: "delete" })}
          className={`flex w-full items-center justify-center gap-1.5 rounded-[var(--radius-control)] border border-danger/40 px-3 py-1.5 text-meta font-medium text-danger transition-colors hover:bg-danger/10 ${FOCUS}`}
        >
          <Icon name="trash" size={14} />
          <span>{t("knowledge.dossier.delete")}</span>
        </button>
        <GapButton label={t("knowledge.dossier.jump")} note={t("knowledge.dossier.jumpNote")} icon="menuBook" />
      </div>
    </aside>

    {/* The CRUD dialogs — one at a time, each returning focus to its opener.
        A delete folds the dossier (onClose) once the write lands; the graph
        and the dossiers refetch the server's truth through the mutations. */}
    {dialog?.kind === "edit" && (
      <EditEntityDialog entity={entity} openerId="dossier-edit" onClose={closeDialog} />
    )}
    {dialog?.kind === "delete" && (
      <DeleteEntityDialog
        entity={entity}
        relationCount={relations.length}
        openerId="dossier-delete"
        onClose={closeDialog}
        onDeleted={onClose}
        fallbackFocusId={focusFallbackId ?? "entity-dossier"}
      />
    )}
    {dialog?.kind === "addRelation" && (
      <CreateRelationDialog
        novelId={entity.novel_id}
        entities={entities}
        from={entity}
        openerId="dossier-add-relation"
        onClose={closeDialog}
      />
    )}
    {dialog?.kind === "editRelation" && (
      <EditRelationDialog
        relation={dialog.relation}
        entities={entities}
        openerId={`dossier-relation-edit-${dialog.relation.id}`}
        onClose={closeDialog}
      />
    )}
    {dialog?.kind === "deleteRelation" && (
      <DeleteRelationDialog
        relation={dialog.relation}
        entities={entities}
        openerId={`dossier-relation-delete-${dialog.relation.id}`}
        onClose={closeDialog}
        // The survivor chain (#910): the relations list while other edges
        // keep it mounted; the dossier aside when this delete empties the
        // list — the invalidation unmounts the focused <ul> otherwise, and
        // removing the active element drops focus to the body.
        fallbackFocusId={relations.length <= 1 ? "entity-dossier" : "dossier-relations"}
      />
    )}
    </>
  );
}
