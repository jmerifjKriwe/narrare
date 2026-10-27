import { useEffect, useState, type FormEvent } from "react";

import type { Entity, Relation } from "@shell/lib/api/client";
import { announce } from "@shell/lib/announce";
import { useTranslation } from "@shell/lib/i18n";
import {
  useAddRelation,
  useDeleteRelation,
  useEntityRelationsQuery,
  useUpdateRelation,
  type RelationChanges,
} from "@shell/lib/query";
import { ComboBox } from "@shell/ui/ComboBox";
import { TextField } from "@shell/ui/TextField";

import { PRIMARY_BUTTON, QUIET_BUTTON } from "./buttons";
import { relationTypeLabel, RELATION_TYPES, resolveRelationType } from "./relations";

/**
 * The edit dialog's relations: both directions of every edge as rows with
 * an inline edit and delete, and one add row — the target from the
 * novel's other entries, the type from the suggested vocabulary with free
 * text welcome, the note optional. The ends of an edge never move
 * (D7): retyping is what the edit offers; moving is delete plus add.
 */
export function EntityRelationsSection(
  { entity, rows, onRowEditorChange }: {
    entity: Entity;
    rows: Entity[];
    /** Every open/close of a row editor reports upward: the dialog's own
     *  Save stands down while typed relation work is on the table, so it
     *  can no longer close over it and silently discard the row's type
     *  and note. */
    onRowEditorChange?: (open: boolean) => void;
  },
) {
  const t = useTranslation();
  const relations = useEntityRelationsQuery(entity.id);
  const add = useAddRelation();
  const update = useUpdateRelation();
  const remove = useDeleteRelation();

  const others = rows.filter((row) => row.id !== entity.id);
  const nameOf = (id: string) => rows.find((row) => row.id === id)?.name ?? id;

  const typeItems = RELATION_TYPES.map((type) => ({
    id: type,
    text: relationTypeLabel(t, type),
  }));

  // The add row: the picked id must still be what the box says — typing
  // a different name after a pick is a new question, not a stale answer.
  const [targetText, setTargetText] = useState("");
  const [targetId, setTargetId] = useState<string | null>(null);
  const [typeText, setTypeText] = useState("");
  const [note, setNote] = useState("");
  const [triedAdd, setTriedAdd] = useState(false);

  // The inline edit: one row at a time, prefilled with what the edge holds.
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTypeText, setEditTypeText] = useState("");
  const [editNote, setEditNote] = useState("");
  const [triedEdit, setTriedEdit] = useState(false);

  /** The one writer of the editor's id: the open state rides along, so the
   *  dialog hears of every change — including the unmount's, where a
   *  closed dialog must not keep a stale "editor open" standing. */
  function changeEditingId(next: string | null) {
    setEditingId(next);
    onRowEditorChange?.(next !== null);
  }
  useEffect(() => () => onRowEditorChange?.(false), [onRowEditorChange]);

  // The refusals are shared: the section names the failed change, and the
  // next attempt clears the words.
  const [failed, setFailed] = useState(false);

  const target = others.find((row) => row.id === targetId) ?? null;
  const targetInvalid = triedAdd && (target === null || target.name !== targetText.trim());
  const addType = resolveRelationType(typeItems, typeText);
  const addTypeInvalid = triedAdd && addType === "";
  const editType = resolveRelationType(typeItems, editTypeText);
  const editTypeInvalid = triedEdit && editType === "";

  /** Add the edge the add row describes; clear the row on success. */
  async function addEdge(event: FormEvent) {
    event.preventDefault();
    setTriedAdd(true);
    setFailed(false);
    if (target === null || target.name !== targetText.trim() || addType === "") return;
    try {
      await add.mutateAsync({
        entityId: entity.id,
        toEntityId: target.id,
        relationType: addType,
        // The untouched box is the no-note state, said explicitly — the
        // same normalization the edit's save applies, so an untouched
        // editor never sees a change where the writer typed none.
        note: note.trim() === "" ? null : note,
      });
    } catch {
      setFailed(true);
      return;
    }
    announce(t("knowledge.relationAdded"));
    setTargetText("");
    setTargetId(null);
    setTypeText("");
    setNote("");
    setTriedAdd(false);
  }

  /** Open the row's inline editor, prefilled with the edge's own words. */
  function startEdit(relation: Relation) {
    changeEditingId(relation.id);
    setEditTypeText(relationTypeLabel(t, relation.relation_type));
    setEditNote(relation.note ?? "");
    setTriedEdit(false);
    setFailed(false);
  }

  /** Save the edit's changed fields; an untouched editor just closes. */
  async function saveEdit(relation: Relation, event: FormEvent) {
    event.preventDefault();
    setTriedEdit(true);
    setFailed(false);
    if (editType === "") return;
    const changes: RelationChanges = {};
    if (editType !== relation.relation_type) changes.relationType = editType;
    const nextNote = editNote.trim() === "" ? null : editNote;
    if (nextNote !== relation.note) changes.note = nextNote;
    if (changes.relationType === undefined && changes.note === undefined) {
      changeEditingId(null);
      return;
    }
    try {
      await update.mutateAsync({ relationId: relation.id, ...changes });
    } catch {
      setFailed(true);
      return;
    }
    announce(t("knowledge.relationUpdated"));
    changeEditingId(null);
  }

  /** Delete exactly this edge; keep the section's other rows standing. */
  async function deleteEdge(relation: Relation) {
    setFailed(false);
    try {
      await remove.mutateAsync({ relationId: relation.id });
    } catch {
      setFailed(true);
      return;
    }
    if (editingId === relation.id) changeEditingId(null);
    announce(t("knowledge.relationDeleted"));
  }

  return (
    <section className="mt-1 flex flex-col gap-2">
      <p className="text-sm font-medium">{t("knowledge.relationsHeading")}</p>
      {relations.isPending ? (
        <p className="text-sm text-muted">{t("knowledge.loading")}</p>
      ) : relations.isError ? (
        <p role="alert" className="text-sm text-danger">
          {t("knowledge.errorRelations")}
        </p>
      ) : (relations.data ?? []).length === 0 ? (
        <p className="text-sm text-muted">{t("knowledge.noRelations")}</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {(relations.data ?? []).map((relation) => {
            const self = relation.from_entity_id === relation.to_entity_id;
            const outgoing = relation.from_entity_id === entity.id;
            const label = relationTypeLabel(t, relation.relation_type);
            const editing = editingId === relation.id;
            return (
              <li key={relation.id} className="rounded-md border border-border px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm">
                    {self ? "↻" : outgoing ? "→" : "←"}{" "}
                    {self
                      ? `${label} · ${t("knowledge.relationSelf")}`
                      : `${nameOf(outgoing ? relation.to_entity_id : relation.from_entity_id)} · ${label}`}
                    {relation.note ? ` · ${relation.note}` : ""}
                  </span>
                  {!editing ? (
                    <span className="flex shrink-0 gap-1">
                      <button
                        type="button"
                        onClick={() => startEdit(relation)}
                        className="rounded-md border border-border px-2 py-1 text-xs font-medium hover:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                      >
                        {t("knowledge.relationEdit")}
                      </button>
                      <button
                        type="button"
                        onClick={() => void deleteEdge(relation)}
                        className="rounded-md border border-danger px-2 py-1 text-xs font-medium text-danger hover:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                      >
                        {t("knowledge.relationDelete")}
                      </button>
                    </span>
                  ) : null}
                </div>
                {editing ? (
                  <form
                    onSubmit={(event) => void saveEdit(relation, event)}
                    className="mt-2 flex flex-col gap-2"
                  >
                    <ComboBox
                      label={t("knowledge.relationTypeLabel")}
                      value={editTypeText}
                      onChange={setEditTypeText}
                      onPick={(id) => {
                        const picked = typeItems.find((item) => item.id === id);
                        if (picked) setEditTypeText(picked.text);
                      }}
                      items={typeItems.filter((item) =>
                        item.text.toLowerCase().includes(editTypeText.trim().toLowerCase()),
                      )}
                    />
                    {editTypeInvalid ? (
                      <p className="text-sm text-danger">{t("knowledge.relationTypeRequired")}</p>
                    ) : null}
                    <TextField
                      label={t("knowledge.relationNoteLabel")}
                      value={editNote}
                      onChange={setEditNote}
                    />
                    <div className="flex gap-2">
                      <button type="submit" className={PRIMARY_BUTTON}>
                        {t("knowledge.entitySave")}
                      </button>
                      <button
                        type="button"
                        onClick={() => changeEditingId(null)}
                        className={QUIET_BUTTON}
                      >
                        {t("knowledge.entityCancel")}
                      </button>
                    </div>
                  </form>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
      <form onSubmit={(event) => void addEdge(event)} className="flex flex-col gap-2 border-t border-border pt-3">
        <ComboBox
          label={t("knowledge.relationTargetLabel")}
          value={targetText}
          onChange={setTargetText}
          onPick={(id) => {
            setTargetId(id);
            const picked = others.find((row) => row.id === id);
            if (picked) setTargetText(picked.name);
          }}
          items={others
            .filter((row) => row.name.toLowerCase().includes(targetText.trim().toLowerCase()))
            .map((row) => ({ id: row.id, text: row.name }))}
        />
        {targetInvalid ? (
          <p className="text-sm text-danger">{t("knowledge.relationTargetRequired")}</p>
        ) : null}
        <ComboBox
          label={t("knowledge.relationTypeLabel")}
          value={typeText}
          onChange={setTypeText}
          onPick={(id) => {
            const picked = typeItems.find((item) => item.id === id);
            if (picked) setTypeText(picked.text);
          }}
          items={typeItems.filter((item) =>
            item.text.toLowerCase().includes(typeText.trim().toLowerCase()),
          )}
        />
        {addTypeInvalid ? (
          <p className="text-sm text-danger">{t("knowledge.relationTypeRequired")}</p>
        ) : null}
        <TextField label={t("knowledge.relationNoteLabel")} value={note} onChange={setNote} />
        <button type="submit" className={PRIMARY_BUTTON}>
          {t("knowledge.relationAdd")}
        </button>
      </form>
      {failed ? (
        <p role="alert" className="text-sm text-danger">
          {t("knowledge.entityFailed")}
        </p>
      ) : null}
    </section>
  );
}
