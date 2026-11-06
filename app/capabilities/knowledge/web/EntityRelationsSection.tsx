import { useEffect, useState, type FormEvent, type ReactNode } from "react";

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
import { Button } from "@shell/ui/Button";
import { ComboBox } from "@shell/ui/ComboBox";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Input } from "@shell/ui/field";
import { Icon } from "@shell/ui/icons";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";
import { Table, type TableColumn } from "@shell/ui/Table";

import { relationTypeLabel, RELATION_TYPES, resolveRelationType } from "./relations";

/**
 * One relation table row: the two data columns are plain strings — the
 * type's wording (the self mark and the note ride inside it, both data
 * the row owns), and the other end's name resolved from the novel's
 * list — and the third carries the row's own controls. A node cell is
 * what the table contract allows a display-ready field to be; no render
 * prop was added for these tables.
 */
type RelationRow = {
  id: string;
  typ: string;
  ziel: string;
  controls: ReactNode;
};

/**
 * The edit dialog's relations: both directions as their own table —
 * "Verweist auf" (outgoing) and "Wird verwiesen von" (incoming), columns
 * Typ / Ziel plus the rows' controls — with one add row. There is no
 * chapter column and no mention list: the edge data names no chapter
 * (F30). The target comes from the novel's other entries, the type from
 * the suggested vocabulary with free text welcome, the note optional.
 * A self-relation — an edge that only a re-pointing can create — is
 * both outgoing and incoming, so it stands in both tables under its
 * mark. The ends of an edge never move (D7): retyping is what the edit
 * offers; moving is delete plus add.
 */
export function EntityRelationsSection(
  { entity, rows, onRowEditorChange, onAddDirtyChange }: {
    entity: Entity;
    rows: Entity[];
    /** Every open/close of a row editor reports upward: the dialog's own
     *  Save stands down while typed relation work is on the table, so it
     *  can no longer close over it and silently discard the row's type
     *  and note. */
    onRowEditorChange?: (open: boolean) => void;
    /** The add form's dirt reports upward the same way (R49): a target
     *  or note the user typed must not die under a Save that never read
     *  it — the dialog's Save stands down until the form is spent. */
    onAddDirtyChange?: (dirty: boolean) => void;
  },
) {
  const t = useTranslation();
  const relations = useEntityRelationsQuery(entity.id);
  const add = useAddRelation();
  const update = useUpdateRelation();
  const remove = useDeleteRelation();

  const edges = relations.data ?? [];
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

  const addDirty =
    targetText.trim() !== "" || typeText.trim() !== "" || note.trim() !== "";
  useEffect(() => onAddDirtyChange?.(addDirty), [addDirty, onAddDirtyChange]);

  // The row edit: one at a time, prefilled with what the edge holds. The
  // form stands under the table whose rows it edits, named for its own
  // scope (the dialog holds the add form's words beside it).
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

  // The refusals are per form: the add row and the inline editor each
  // name their own failed change inside the form that owns it, and
  // opening or leaving one must not carry words across — neither the
  // other form's, nor its own stale ones.
  const [addFailed, setAddFailed] = useState(false);
  // The duplicate is named apart from the outage: a 409 is a pair the
  // tables already hold — the user's own input, not a service that died —
  // so it answers in the duplicate's own words, and the next attempt
  // clears it with the rest.
  const [addDuplicate, setAddDuplicate] = useState(false);
  const [editFailed, setEditFailed] = useState(false);
  const [editDuplicate, setEditDuplicate] = useState(false);

  const target = others.find((row) => row.id === targetId) ?? null;
  const targetInvalid = triedAdd && (target === null || target.name !== targetText.trim());
  const addType = resolveRelationType(typeItems, typeText);
  const addTypeInvalid = triedAdd && addType === "";
  const editType = resolveRelationType(typeItems, editTypeText);
  const editTypeInvalid = triedEdit && editType === "";

  /** Add the edge the add row describes; clear the row on success. */
  async function addEdge(event: FormEvent) {
    event.preventDefault();
    // One submit is one request: a click the pending add already owns is
    // no second ask — the double request is what would turn the 409 below
    // into a second user error.
    if (add.isPending) return;
    setTriedAdd(true);
    setAddFailed(false);
    setAddDuplicate(false);
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
    } catch (error) {
      // The refusal names itself in the add form: the 409's duplicate
      // wording, the outage's words for everything else. The status rides
      // the mutation's Error (see the hooks in `@shell/lib/query`).
      if ((error as { status?: number }).status === 409) setAddDuplicate(true);
      else setAddFailed(true);
      return;
    }
    announce(t("knowledge.relationAdded"));
    setTargetText("");
    setTargetId(null);
    setTypeText("");
    setNote("");
    setTriedAdd(false);
    setAddFailed(false);
    setAddDuplicate(false);
  }

  /** Open the row's inline editor, prefilled with the edge's own words. */
  function startEdit(relation: Relation) {
    changeEditingId(relation.id);
    setEditTypeText(relationTypeLabel(t, relation.relation_type));
    setEditNote(relation.note ?? "");
    setTriedEdit(false);
    setEditFailed(false);
    setEditDuplicate(false);
  }

  /** Leave the inline editor: the words it owed — a failure named or a
   *  duplicate standing — go with it, so a later editor opens clean. */
  function closeEdit() {
    setEditFailed(false);
    setEditDuplicate(false);
    changeEditingId(null);
  }

  /** Save the edit's changed fields; an untouched editor just closes. */
  async function saveEdit(relation: Relation, event: FormEvent) {
    event.preventDefault();
    // One submit is one request, the add row's rule again.
    if (update.isPending) return;
    setTriedEdit(true);
    setEditFailed(false);
    setEditDuplicate(false);
    if (editType === "") return;
    const changes: RelationChanges = {};
    // The type changes only when the box's text does. A stored free-text
    // type can carry the same words a vocabulary label spells — the raw
    // "ally of" beside the catalog's "ally_of" — and resolving the
    // prefilled box would then silently retype the edge. What the editor
    // was shown with is the edge's own answer; only a retype is one.
    const originalLabel = relationTypeLabel(t, relation.relation_type).trim();
    if (editTypeText.trim() !== originalLabel && editType !== relation.relation_type) {
      changes.relationType = editType;
    }
    const nextNote = editNote.trim() === "" ? null : editNote;
    if (nextNote !== relation.note) changes.note = nextNote;
    if (changes.relationType === undefined && changes.note === undefined) {
      closeEdit();
      return;
    }
    try {
      await update.mutateAsync({ relationId: relation.id, ...changes });
    } catch (error) {
      // The add form's rule, the editor's own words: the 409's duplicate
      // wording, the outage's words for everything else.
      if ((error as { status?: number }).status === 409) setEditDuplicate(true);
      else setEditFailed(true);
      return;
    }
    announce(t("knowledge.relationUpdated"));
    closeEdit();
  }

  /** The delete asks first (R36): the row's control only names the edge,
   *  the confirm dialog does the taking — both deletes are one keystroke
   *  from data loss, so both wear the dialog's shape. */
  const [pendingDelete, setPendingDelete] = useState<Relation | null>(null);
  const [deleteFailed, setDeleteFailed] = useState(false);

  /** The confirmed delete: exactly this edge; keep the section's other rows standing. */
  async function destroyPending(close: () => void) {
    const relation = pendingDelete;
    if (relation === null) return;
    // One confirm is one request: a second press of the open dialog's
    // button waits for the first to settle.
    if (remove.isPending) return;
    setDeleteFailed(false);
    try {
      await remove.mutateAsync({ relationId: relation.id });
    } catch {
      // The dialog stays open: the failure is this delete's own — named
      // inside it, where the retry is one press away.
      setDeleteFailed(true);
      return;
    }
    if (editingId === relation.id) closeEdit();
    announce(t("knowledge.relationDeleted"));
    close();
    setPendingDelete(null);
  }

  /** The row a table shows for one edge: the words for Typ and Ziel, the
   *  pair of row controls for the third column. */
  function rowFor(relation: Relation, direction: "outgoing" | "incoming"): RelationRow {
    const self = relation.from_entity_id === relation.to_entity_id;
    const otherId = self
      ? relation.from_entity_id
      : direction === "outgoing"
        ? relation.to_entity_id
        : relation.from_entity_id;
    const parts = [relationTypeLabel(t, relation.relation_type)];
    if (self) parts.push(t("knowledge.relationSelf"));
    if (relation.note) parts.push(relation.note);
    return {
      id: relation.id,
      typ: parts.join(" · "),
      ziel: nameOf(otherId),
      controls: (
        <span className="flex gap-1">
          <Button
            variant="icon"
            size="sm"
            icon={<Icon name="write" />}
            label={t("knowledge.relationEdit")}
            onClick={() => startEdit(relation)}
          />
          <Button
            variant="icon"
            size="sm"
            icon={<Icon name="cross" />}
            label={t("knowledge.relationDelete")}
            onClick={() => setPendingDelete(relation)}
          />
        </span>
      ),
    };
  }

  const columns: TableColumn<RelationRow>[] = [
    { key: "typ", label: t("knowledge.entityTypeLabel") },
    { key: "ziel", label: t("knowledge.relationsTarget") },
    { key: "controls", label: t("knowledge.relationActions"), width: "92px" },
  ];

  const outgoing = edges.filter((relation) => relation.from_entity_id === entity.id);
  const incoming = edges.filter((relation) => relation.to_entity_id === entity.id);
  // A loop is both directions at once; its editor stands under the
  // outgoing table, the first one that holds it.
  const editingOutgoing =
    editingId !== null && outgoing.some((relation) => relation.id === editingId);

  const editForm = (
    <form
      aria-label={t("knowledge.relationEditHeading")}
      onSubmit={(event) => {
        const relation = edges.find((row) => row.id === editingId);
        if (relation) void saveEdit(relation, event);
      }}
      className="mt-2 flex flex-col gap-2 border-t border-rule pt-2"
    >
      <h5 className="text-label font-medium">{t("knowledge.relationEditHeading")}</h5>
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
        <Notice tone="danger">{t("knowledge.relationTypeRequired")}</Notice>
      ) : null}
      <Field label={t("knowledge.relationNoteLabel")}>
        <Input value={editNote} onChange={(event) => setEditNote(event.target.value)} />
      </Field>
      {editDuplicate ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.relationExists")}
        </Notice>
      ) : editFailed ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.entityFailed")}
        </Notice>
      ) : null}
      <div className="flex gap-2">
        <Button variant="secondary" type="submit" disabled={update.isPending}>
          {t("knowledge.entitySave")}
        </Button>
        <Button onClick={closeEdit}>{t("knowledge.entityCancel")}</Button>
      </div>
    </form>
  );

  // The name the confirm speaks: the edge's other end — the entity
  // itself for a loop.
  const pendingName =
    pendingDelete === null
      ? ""
      : nameOf(
          pendingDelete.from_entity_id === pendingDelete.to_entity_id
            ? pendingDelete.from_entity_id
            : pendingDelete.from_entity_id === entity.id
              ? pendingDelete.to_entity_id
              : pendingDelete.from_entity_id,
        );

  return (
    <section className="mt-1 flex flex-col gap-2">
      <h3 className="text-label font-medium">{t("knowledge.relationsHeading")}</h3>
      {relations.isPending ? (
        // The ask is in flight: the section asks rather than claims — no
        // tables, and not the empty state either, since no answer is not
        // the fact "no relations".
        <Notice tone="quiet" live="status">
          {t("knowledge.loading")}
        </Notice>
      ) : relations.isError ? (
        <Notice tone="danger" live="alert">
          {t("knowledge.errorRelations")}
        </Notice>
      ) : edges.length === 0 ? (
        <Notice tone="quiet">{t("knowledge.noRelations")}</Notice>
      ) : (
        <>
          <Panel title={t("knowledge.relationsOutgoing")} titleAs="h4" dense>
            <Table
              aria-label={t("knowledge.relationsOutgoing")}
              columns={columns}
              rows={outgoing.map((relation) => rowFor(relation, "outgoing"))}
              rowKey={(row) => row.id}
              dense
            />
            {editingOutgoing ? editForm : null}
          </Panel>
          <Panel title={t("knowledge.relationsIncoming")} titleAs="h4" dense>
            <Table
              aria-label={t("knowledge.relationsIncoming")}
              columns={columns}
              rows={incoming.map((relation) => rowFor(relation, "incoming"))}
              rowKey={(row) => row.id}
              dense
            />
            {editingId !== null && !editingOutgoing ? editForm : null}
          </Panel>
        </>
      )}
      <form
        onSubmit={(event) => void addEdge(event)}
        className="flex flex-col gap-2 border-t border-rule pt-3"
      >
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
          <Notice tone="danger">{t("knowledge.relationTargetRequired")}</Notice>
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
          <Notice tone="danger">{t("knowledge.relationTypeRequired")}</Notice>
        ) : null}
        <Field label={t("knowledge.relationNoteLabel")}>
          <Input value={note} onChange={(event) => setNote(event.target.value)} />
        </Field>
        {addDuplicate ? (
          <Notice tone="danger" live="alert">
            {t("knowledge.relationExists")}
          </Notice>
        ) : addFailed ? (
          <Notice tone="danger" live="alert">
            {t("knowledge.entityFailed")}
          </Notice>
        ) : null}
        <Button variant="secondary" type="submit" disabled={add.isPending}>
          {t("knowledge.relationAdd")}
        </Button>
      </form>
      {/* The confirm the row's delete owes its blast radius: the dialog
          names the edge it will take before it takes it — the entity
          delete's pattern (R36). Stacked over the edit dialog, which
          stays open behind it. */}
      <Dialog
        title={t("knowledge.relationDelete")}
        isOpen={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteFailed(false);
            setPendingDelete(null);
          }
        }}
      >
        {(close) => (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-body">
              {t(
                "knowledge.relationDeleteText",
                { name: pendingName },
              )}
            </p>
            {deleteFailed ? (
              <Notice tone="danger" live="alert">
                {t("knowledge.entityFailed")}
              </Notice>
            ) : null}
            <div className="flex gap-2">
              <Button onClick={() => void destroyPending(close)} disabled={remove.isPending}>
                {t("knowledge.entityDeleteConfirm")}
              </Button>
              <Button onClick={close}>{t("knowledge.entityCancel")}</Button>
            </div>
          </div>
        )}
      </Dialog>
    </section>
  );
}
