import { useParams } from "@tanstack/react-router";
import { useId, useState } from "react";

import { announce } from "@shell/lib/announce";
import type { Entity } from "@shell/lib/api/client";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import {
  useDeleteEntity,
  useEntitiesQuery,
  useMergeEntities,
  usePassageSearch,
  useUpdateEntity,
  type EntityChanges,
} from "@shell/lib/query";
import { ComboBox } from "@shell/ui/ComboBox";
import { Dialog } from "@shell/ui/Dialog";
import { GridList } from "@shell/ui/GridList";
import { TextField } from "@shell/ui/TextField";

// The extraction contract's kinds (knowledge's prompt vocabulary), as
// catalog keys. A kind the contract later adds falls back to "thing" rather
// than crashing the render; the list is the contract's, so it lives beside
// its first consumer and the review queue imports it from here.
const KIND_KEYS = {
  character: "knowledge.kind.character",
  place: "knowledge.kind.place",
  thing: "knowledge.kind.thing",
} as const;

/** An entity kind in the user's language — the list's and the review
 *  queue's shared wording for what a filed row is. */
export function entityKindLabel(t: (key: MessageKey) => string, kind: string): string {
  return kind in KIND_KEYS ? t(KIND_KEYS[kind as keyof typeof KIND_KEYS]) : t("knowledge.kind.thing");
}

// The button paints the shell already knows: the primary action, the
// quiet second choice, and the one a confirm dialog owes its danger to.
const PRIMARY_BUTTON =
  "rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
const QUIET_BUTTON =
  "rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
const DANGER_BUTTON =
  "rounded-md border border-danger px-3 py-2 text-sm font-medium text-danger hover:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

/** The novel's entities: searched with the combo box, listed, and opened
 *  into a detail view on selection. */
export function EntitiesPanel() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  const entities = useEntitiesQuery(novelId);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const headingId = useId();
  const passagesId = useId();

  const rows = entities.data ?? [];
  // The search reaches the names, case-insensitively: the box and the list
  // share one filter, so what the box narrows is what the list shows.
  const needle = query.trim().toLowerCase();
  const filtered = rows.filter((entity) => entity.name.toLowerCase().includes(needle));
  // The detail follows the selection, not the filter: picking an entity and
  // then narrowing the search must not close what was opened.
  const selected = rows.find((entity) => entity.id === selectedId) ?? null;

  // The box's second tier: the same words, asked of the semantic search
  // (debounced, in the hook) while they are in the box at all.
  const passages = usePassageSearch(query);
  const searching = query.trim() !== "";

  return (
    <section aria-labelledby={headingId} className="mt-6">
      <h3 id={headingId} className="text-sm font-semibold">
        {t("knowledge.entitiesHeading")}
      </h3>
      <div className="mt-2">
        <ComboBox
          label={t("knowledge.entitySearchLabel")}
          value={query}
          onChange={setQuery}
          onPick={setSelectedId}
          items={filtered.map((entity) => ({ id: entity.id, text: entity.name }))}
        />
      </div>
      {entities.isPending ? (
        // The answer has not arrived yet: the panel asks rather than
        // claims — not the list, and not its empty state either, since no
        // answer is not the fact "no entities".
        <p className="mt-2 text-sm text-muted">{t("knowledge.loading")}</p>
      ) : entities.isError ? (
        // An unreachable service names itself here, never as an empty
        // list (the outage test stops the real API and reloads — the
        // empty state would be the mask of a missing answer).
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("knowledge.errorLoad")}
        </p>
      ) : rows.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("knowledge.noEntities")}</p>
      ) : filtered.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("knowledge.noResults")}</p>
      ) : (
        <div className="mt-2">
          <GridList
            label={t("knowledge.entitiesHeading")}
            items={filtered}
            getId={(entity) => entity.id}
            selectedId={selectedId}
            onSelect={setSelectedId}
            render={(entity) => entity.name}
          />
        </div>
      )}
      {searching ? (
        /* The box's second tier renders under the list it shares the words
            with: the corpus's passages, each with its document's title. Its
            error names itself in this tier's own words (errorPassages, not
            the standalone page's errorSearch) because the dock can show it
            beside the entity list's and the queue's outages — three
            failures at once must stay nameable apart. */
        <section aria-labelledby={passagesId} className="mt-4">
          <h4 id={passagesId} className="text-sm font-semibold">
            {t("knowledge.passagesHeading")}
          </h4>
          {passages.isPending ? (
            // The ask is debounced, so the block asks while the words
            // settle and the answer flies — the same patience the entity
            // list's own loading state has.
            <p className="mt-2 text-sm text-muted">{t("knowledge.loading")}</p>
          ) : passages.isError ? (
            <p role="alert" className="mt-2 text-sm text-danger">
              {t("knowledge.errorPassages")}
            </p>
          ) : (passages.data ?? []).length === 0 ? (
            <p className="mt-2 text-sm text-muted">{t("knowledge.noPassages")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {(passages.data ?? []).map((hit) => (
                <li key={hit.chunk_id} className="rounded-lg border border-border bg-card p-3">
                  <strong className="text-sm font-semibold">{hit.document_title}</strong>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{hit.text}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
      {selected ? (
        /* The detail is keyed by the row: selecting another entity remounts
            it with that row's values, and the corrections' own state (the
            form fields, the picked merge target) never crosses rows. */
        <EntityDetail
          key={selected.id}
          entity={selected}
          others={rows.filter((row) => row.id !== selected.id)}
          novelId={novelId}
          onSelect={setSelectedId}
        />
      ) : null}
    </section>
  );
}

/** The selected entity's detail: what review filed, and the three ways to
 *  correct it. Every correction is a dialog, so the focus contract — the
 *  trap inside, Escape, the restore to the trigger — is the shell's, and
 *  every outcome is announced: the dialog closes on success, and the list
 *  changing under it is the only visible trace without the announcement. */
function EntityDetail({
  entity,
  others,
  novelId,
  onSelect,
}: {
  entity: Entity;
  others: Entity[];
  novelId: string;
  onSelect: (id: string | null) => void;
}) {
  const t = useTranslation();
  const detailId = useId();

  return (
    <section
      aria-labelledby={detailId}
      className="mt-3 rounded-lg border border-border bg-card p-4"
    >
      <h4 id={detailId} className="text-sm font-semibold">
        {entity.name}
      </h4>
      <p className="mt-1 text-sm text-muted">{entityKindLabel(t, entity.kind)}</p>
      {entity.description ? (
        <p className="mt-2 text-sm leading-relaxed">{entity.description}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <EditEntityDialog entity={entity} novelId={novelId} />
        <MergeEntityDialog
          entity={entity}
          others={others}
          novelId={novelId}
          onSelect={onSelect}
        />
        <DeleteEntityDialog entity={entity} novelId={novelId} onSelect={onSelect} />
      </div>
    </section>
  );
}

/** Rename, rekind, redescription: the form carries only what changed. */
function EditEntityDialog({ entity, novelId }: { entity: Entity; novelId: string }) {
  const t = useTranslation();
  const update = useUpdateEntity(novelId);
  const [name, setName] = useState(entity.name);
  const [kindText, setKindText] = useState(entityKindLabel(t, entity.kind));
  const [description, setDescription] = useState(entity.description ?? "");
  // The refusals are derived, not stored: once a save was tried, the words
  // stand exactly as long as the field does not answer them.
  const [triedSave, setTriedSave] = useState(false);
  const [failed, setFailed] = useState(false);

  const kindItems = (Object.keys(KIND_KEYS) as (keyof typeof KIND_KEYS)[]).map((kind) => ({
    id: kind,
    text: t(KIND_KEYS[kind]),
  }));
  const nameInvalid = triedSave && name.trim() === "";
  // The box is the source of truth: its text resolves back to a kind on
  // save, the way the search box's text is what the list filters by.
  const resolvedKind = kindItems.find((item) => item.text === kindText.trim())?.id ?? null;
  const kindInvalid = triedSave && resolvedKind === null;

  /** Save changed fields, clearing a blank description; keep the dialog open on refusal. */
  async function save(event: React.FormEvent, close: () => void) {
    event.preventDefault();
    setTriedSave(true);
    setFailed(false);
    const trimmedName = name.trim();
    if (trimmedName === "" || resolvedKind === null) return;
    const nextDescription = description.trim() === "" ? null : description;
    const changes: EntityChanges = {};
    if (trimmedName !== entity.name) changes.name = trimmedName;
    if (resolvedKind !== entity.kind) changes.kind = resolvedKind;
    if (nextDescription !== (entity.description ?? null)) changes.description = nextDescription;
    try {
      await update.mutateAsync({ entityId: entity.id, changes });
    } catch {
      // The dialog stays open: the typed values are the user's work, and
      // the failure is this save's own — named inside the dialog, where
      // the retry is one press away.
      setFailed(true);
      return;
    }
    announce(t("knowledge.entitySaved", { name: trimmedName }));
    close();
  }

  return (
    <Dialog title={t("knowledge.entityEditTitle")} triggerLabel={t("knowledge.entityEdit")}>
      {(close) => (
        <form onSubmit={(event) => void save(event, close)} className="mt-4 flex flex-col gap-3">
          <TextField
            label={t("knowledge.entityNameLabel")}
            value={name}
            onChange={setName}
            isInvalid={nameInvalid}
            validationMessage={nameInvalid ? t("knowledge.entityNameRequired") : undefined}
          />
          <ComboBox
            label={t("knowledge.entityKindLabel")}
            value={kindText}
            onChange={setKindText}
            onPick={(id) => {
              const picked = kindItems.find((item) => item.id === id);
              if (picked) setKindText(picked.text);
            }}
            items={kindItems.filter((item) =>
              item.text.toLowerCase().includes(kindText.trim().toLowerCase()),
            )}
          />
          {kindInvalid ? (
            <p className="text-sm text-danger">{t("knowledge.entityKindRequired")}</p>
          ) : null}
          <TextField
            label={t("knowledge.entityDescriptionLabel")}
            value={description}
            onChange={setDescription}
            multiline
          />
          {failed ? (
            <p role="alert" className="text-sm text-danger">
              {t("knowledge.entityFailed")}
            </p>
          ) : null}
          <div className="flex gap-2">
            <button type="submit" className={PRIMARY_BUTTON}>
              {t("knowledge.entitySave")}
            </button>
            <button type="button" onClick={close} className={QUIET_BUTTON}>
              {t("knowledge.entityCancel")}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

/** The confirm the delete owes its blast radius: the dialog names the row
 *  it will take before it takes it. */
function DeleteEntityDialog({
  entity,
  novelId,
  onSelect,
}: {
  entity: Entity;
  novelId: string;
  onSelect: (id: string | null) => void;
}) {
  const t = useTranslation();
  const remove = useDeleteEntity(novelId);
  const [failed, setFailed] = useState(false);

  /** Delete and clear the selection on success; keep the dialog open on failure. */
  async function destroy(close: () => void) {
    setFailed(false);
    try {
      await remove.mutateAsync(entity.id);
    } catch {
      setFailed(true);
      return;
    }
    // The row is gone: the selection must not point at what no longer
    // exists, and the detail unmounts with the answer.
    onSelect(null);
    announce(t("knowledge.entityDeleted", { name: entity.name }));
    close();
  }

  return (
    <Dialog title={t("knowledge.entityDeleteTitle")} triggerLabel={t("knowledge.entityDelete")}>
      {(close) => (
        <div className="mt-4 flex flex-col gap-3">
          <p className="text-sm">{t("knowledge.entityDeleteText", { name: entity.name })}</p>
          {failed ? (
            <p role="alert" className="text-sm text-danger">
              {t("knowledge.entityFailed")}
            </p>
          ) : null}
          <div className="flex gap-2">
            <button type="button" onClick={() => void destroy(close)} className={DANGER_BUTTON}>
              {t("knowledge.entityDeleteConfirm")}
            </button>
            <button type="button" onClick={close} className={QUIET_BUTTON}>
              {t("knowledge.entityCancel")}
            </button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

/** Two entries for the same thing fold into one: the picker offers the
 *  novel's other entities, the target survives, the source is deleted. */
function MergeEntityDialog({
  entity,
  others,
  novelId,
  onSelect,
}: {
  entity: Entity;
  others: Entity[];
  novelId: string;
  onSelect: (id: string | null) => void;
}) {
  const t = useTranslation();
  const merge = useMergeEntities(novelId);
  const [targetText, setTargetText] = useState("");
  const [targetId, setTargetId] = useState<string | null>(null);
  const [triedSave, setTriedSave] = useState(false);
  const [failed, setFailed] = useState(false);

  // The picked id must still be what the box says: typing a different name
  // after a pick is a new question, not a stale answer.
  const target = others.find((row) => row.id === targetId) ?? null;
  const targetInvalid = triedSave && (target === null || target.name !== targetText.trim());

  /** Merge into the still-matching picked target and select the survivor; expose failures. */
  async function mergeThem(close: () => void) {
    setTriedSave(true);
    setFailed(false);
    if (target === null || target.name !== targetText.trim()) return;
    try {
      const survivor = await merge.mutateAsync({ sourceId: entity.id, targetId: target.id });
      // The detail follows the surviving row: the source is deleted, and
      // the merge's answer is what remains to be seen.
      onSelect(survivor.id);
      announce(
        t("knowledge.entityMerged", { name: entity.name, target: survivor.name }),
      );
      close();
    } catch {
      setFailed(true);
    }
  }

  return (
    <Dialog title={t("knowledge.entityMergeTitle")} triggerLabel={t("knowledge.entityMerge")}>
      {(close) => (
        <div className="mt-4 flex flex-col gap-3">
          <p className="text-sm">{t("knowledge.entityMergeText", { name: entity.name })}</p>
          <ComboBox
            label={t("knowledge.entityMergeTargetLabel")}
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
            <p className="text-sm text-danger">{t("knowledge.entityMergeTargetRequired")}</p>
          ) : null}
          {failed ? (
            <p role="alert" className="text-sm text-danger">
              {t("knowledge.entityFailed")}
            </p>
          ) : null}
          <div className="flex gap-2">
            <button type="button" onClick={() => void mergeThem(close)} className={PRIMARY_BUTTON}>
              {t("knowledge.entityMergeConfirm")}
            </button>
            <button type="button" onClick={close} className={QUIET_BUTTON}>
              {t("knowledge.entityCancel")}
            </button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
