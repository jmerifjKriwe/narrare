import { useParams } from "@tanstack/react-router";
import { useId, useState } from "react";

import { announce } from "@shell/lib/announce";
import type { Entity, Relation } from "@shell/lib/api/client";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import {
  useDebouncedValue,
  useDeleteEntity,
  useEntitiesQuery,
  useEntityRelationsQuery,
  useMergeEntities,
  usePassageSearch,
  useUpdateEntity,
  type EntityChanges,
} from "@shell/lib/query";
import { ComboBox } from "@shell/ui/ComboBox";
import { Dialog } from "@shell/ui/Dialog";
import { GridList } from "@shell/ui/GridList";
import { MarkdownEditor } from "@shell/ui/markdown-editor";
import { TextField } from "@shell/ui/TextField";

import { DANGER_BUTTON, PRIMARY_BUTTON, QUIET_BUTTON } from "./buttons";
import { EntityRelationsSection } from "./EntityRelationsSection";
import { previewText } from "./preview";
import { relationTypeLabel } from "./relations";

// The extraction contract's types (kernel contracts' ENTITY_TYPES), as
// catalog keys. A type the contract later adds falls back to "generic" rather
// than crashing the render; the list is the contract's, so it lives beside
// its first consumer and the review queue imports it from here.
const TYPE_KEYS = {
  character: "knowledge.type.character",
  location: "knowledge.type.location",
  faction: "knowledge.type.faction",
  object: "knowledge.type.object",
  system: "knowledge.type.system",
  timeline: "knowledge.type.timeline",
  event: "knowledge.type.event",
  generic: "knowledge.type.generic",
} as const;

/** An entity type in the user's language — the list's and the review
 *  queue's shared wording for what a filed row is. */
export function entityTypeLabel(t: (key: MessageKey) => string, type: string): string {
  return type in TYPE_KEYS
    ? t(TYPE_KEYS[type as keyof typeof TYPE_KEYS])
    : t("knowledge.type.generic");
}

// The card previews the body as the source it is (D2: WP3 brings the
// editor), cut where a glance ends and the detail dialog begins.
const PREVIEW_LENGTH = 140;

/** The novel's entities: searched and filtered against the server,
 *  listed, and opened into a detail view on selection. */
export function EntitiesPanel() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  // Two views of one list: the unfiltered ask feeds the filters' options,
  // the detail and the pickers; the narrowed ask is what the rows show.
  // While no filter is set both are the same question — and share the
  // cache entry, so the options cost nothing extra until they are used.
  const all = useEntitiesQuery(novelId);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const headingId = useId();
  const typeFilterId = useId();
  const tagFilterId = useId();
  const passagesId = useId();

  // The box's words reach the server once the typing pauses; the filters
  // answer at once. An empty box is no `q`, an "all" option is no filter.
  const debouncedQuery = useDebouncedValue(query, 300);
  const narrowed = useEntitiesQuery(novelId, {
    type: typeFilter || undefined,
    tag: tagFilter || undefined,
    q: debouncedQuery.trim() || undefined,
  });

  const rows = all.data ?? [];
  const shown = narrowed.data ?? [];

  // The filters offer what the novel's rows actually carry — the types in
  // the contract's order, the tags alphabetically.
  const typeOrder = Object.keys(TYPE_KEYS);
  const typeOptions = [...new Set(rows.map((row) => row.type))].sort((a, b) => {
    const rank = (type: string) => {
      const index = typeOrder.indexOf(type);
      return index === -1 ? typeOrder.length : index;
    };
    return rank(a) - rank(b) || a.localeCompare(b);
  });
  const tagOptions = [...new Set(rows.flatMap((row) => row.tags))].sort((a, b) =>
    a.localeCompare(b),
  );

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
          items={shown.map((entity) => ({ id: entity.id, text: entity.name }))}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <div className="flex flex-col gap-1">
          <label htmlFor={typeFilterId} className="text-sm font-medium">
            {t("knowledge.typeFilterLabel")}
          </label>
          <select
            id={typeFilterId}
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
            className="rounded-md border border-border bg-card px-2 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <option value="">{t("knowledge.filterAllTypes")}</option>
            {typeOptions.map((type) => (
              <option key={type} value={type}>
                {entityTypeLabel(t, type)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={tagFilterId} className="text-sm font-medium">
            {t("knowledge.tagFilterLabel")}
          </label>
          <select
            id={tagFilterId}
            value={tagFilter}
            onChange={(event) => setTagFilter(event.target.value)}
            className="rounded-md border border-border bg-card px-2 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <option value="">{t("knowledge.filterAllTags")}</option>
            {tagOptions.map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </select>
        </div>
      </div>
      {all.isPending || (narrowed.isPending && narrowed.data === undefined) ? (
        // The answer has not arrived yet: the panel asks rather than
        // claims — not the list, and not its empty state either, since no
        // answer is not the fact "no entities". A narrowed ask in flight
        // keeps its previous answer on screen (the hook's own patience),
        // so this state is the first load's alone.
        <p className="mt-2 text-sm text-muted">{t("knowledge.loading")}</p>
      ) : all.isError || narrowed.isError ? (
        // An unreachable service names itself here, never as an empty
        // list (the outage test stops the real API and reloads — the
        // empty state would be the mask of a missing answer).
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("knowledge.errorLoad")}
        </p>
      ) : rows.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("knowledge.noEntities")}</p>
      ) : shown.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("knowledge.noResults")}</p>
      ) : (
        <div className="mt-2">
          <GridList
            label={t("knowledge.entitiesHeading")}
            items={shown}
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
            form fields, the picked merge target) never crosses rows. The
            whole unfiltered list rides along: the card reads the other
            ends' names from it, and the pickers offer it. */
        <EntityDetail
          key={selected.id}
          entity={selected}
          rows={rows}
          novelId={novelId}
          onSelect={setSelectedId}
        />
      ) : null}
    </section>
  );
}

/** The selected entity's detail, kept compact (D9): what review filed —
 *  name, type, chips, the body's source preview, both directions of every
 *  edge — and the doors to the corrections, which all live in dialogs. */
function EntityDetail({
  entity,
  rows,
  novelId,
  onSelect,
}: {
  entity: Entity;
  rows: Entity[];
  novelId: string;
  onSelect: (id: string | null) => void;
}) {
  const t = useTranslation();
  const detailId = useId();
  const relations = useEntityRelationsQuery(entity.id);
  const edges = relations.data ?? [];
  const nameOf = (id: string) => rows.find((row) => row.id === id)?.name ?? id;

  return (
    <section
      aria-labelledby={detailId}
      className="mt-3 rounded-lg border border-border bg-card p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h4 id={detailId} className="text-sm font-semibold">
          {entity.name}
        </h4>
        <span className="rounded-full border border-border bg-panel px-2 py-0.5 text-xs">
          {entityTypeLabel(t, entity.type)}
        </span>
      </div>
      {entity.aliases.length > 0 ? (
        <ChipRow label={t("knowledge.entityAliasesLabel")} values={entity.aliases} />
      ) : null}
      {entity.tags.length > 0 ? (
        <ChipRow label={t("knowledge.entityTagsLabel")} values={entity.tags} />
      ) : null}
      {entity.content ? (
        // The body as the glance reads it: the stored Markdown's display
        // copy — entities decoded, serializer escapes stripped (preview.ts)
        // — cut for a glance. The store keeps the canonical bytes; the
        // editor, not the preview, is where the document renders.
        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">
          {truncate(previewText(entity.content))}
        </p>
      ) : null}
      {relations.isError ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("knowledge.errorRelations")}
        </p>
      ) : edges.length > 0 ? (
        <div className="mt-2">
          <p className="text-sm font-medium">{t("knowledge.relationsHeading")}</p>
          <ul className="mt-1 flex flex-col gap-0.5">
            {edges.map((relation) => (
              <li key={relation.id} className="text-sm text-muted">
                {edgeText(relation, entity.id, nameOf, t)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <EditEntityDialog entity={entity} rows={rows} novelId={novelId} />
        <MergeEntityDialog
          entity={entity}
          others={rows.filter((row) => row.id !== entity.id)}
          novelId={novelId}
          onSelect={onSelect}
        />
        <DeleteEntityDialog entity={entity} novelId={novelId} onSelect={onSelect} />
      </div>
    </section>
  );
}

/** One compact edge row's text: the arrow tells the direction, the other
 *  end's name is resolved from the novel's list, and a self-relation —
 *  an edge that only a re-pointing can create — wears its mark. */
function edgeText(
  relation: Relation,
  entityId: string,
  nameOf: (id: string) => string,
  t: (key: MessageKey) => string,
): string {
  const label = relationTypeLabel(t, relation.relation_type);
  if (relation.from_entity_id === relation.to_entity_id) {
    return `↻ ${label} · ${t("knowledge.relationSelf")}`;
  }
  const outgoing = relation.from_entity_id === entityId;
  const other = nameOf(outgoing ? relation.to_entity_id : relation.from_entity_id);
  return `${outgoing ? "→" : "←"} ${other} · ${label}`;
}

/** A labeled row of read-only chips: what the card shows of the aliases
 *  and tags the dialog edits. */
function ChipRow({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1">
      <span className="text-sm text-muted">{label}:</span>
      {values.map((value) => (
        <span
          key={value}
          className="rounded-full border border-border bg-panel px-2 py-0.5 text-xs"
        >
          {value}
        </span>
      ))}
    </div>
  );
}

function truncate(content: string): string {
  return content.length > PREVIEW_LENGTH ? `${content.slice(0, PREVIEW_LENGTH)}…` : content;
}

/** The chips input on top of the shell's text field: Enter or comma files
 *  the text as a chip, and so does leaving the field — the Save click is
 *  such a leaving, so typed work is filed before the save reads the chips
 *  instead of lost in the box. ✕ removes one, and a case twin is turned
 *  away — the service dedupes too, this is the field's own courtesy. */
function ChipsField({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const t = useTranslation();
  const [text, setText] = useState("");

  function fileText() {
    const value = text.trim().replace(/,+$/, "");
    if (value === "") return;
    setText("");
    if (values.some((existing) => existing.toLowerCase() === value.toLowerCase())) return;
    onChange([...values, value]);
  }

  return (
    <div
      className="flex flex-col gap-1"
      onBlur={fileText}
      onKeyDown={(event) => {
        // The wrapper's keydown serves the text field only: a remove
        // button's Enter is a button press, so any other target is none
        // of this handler's business — swallowing it would kill the
        // chip's keyboard removal.
        if (!(event.target instanceof HTMLInputElement)) return;
        if (event.key === "Enter" || event.key === ",") {
          // Enter must not submit what sits around the field, and the
          // comma must not stay in it: both file the chip instead.
          event.preventDefault();
          fileText();
        }
      }}
    >
      {values.length > 0 ? (
        <ul className="flex flex-wrap gap-1">
          {values.map((value) => (
            <li
              key={value}
              className="flex items-center gap-1 rounded-full border border-border bg-panel px-2 py-0.5 text-xs"
            >
              <span>{value}</span>
              <button
                type="button"
                aria-label={t("knowledge.chipRemove", { value })}
                onClick={() => onChange(values.filter((existing) => existing !== value))}
                className="text-muted hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <TextField label={label} value={text} onChange={setText} />
    </div>
  );
}

/** Order-sensitive list equality: a label field reaches the PATCH body
 *  only when the chips truly differ from what the row holds. */
function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

/** Every field of the row in one dialog (D9): name, type, aliases, tags,
 *  the Markdown body as plain source, and the relations with their add
 *  row. The container is no form — the relations section owns real forms
 *  of its own, and a nested form is no form at all. */
function EditEntityDialog({
  entity,
  rows,
  novelId,
}: {
  entity: Entity;
  rows: Entity[];
  novelId: string;
}) {
  const t = useTranslation();
  const update = useUpdateEntity(novelId);
  const [name, setName] = useState(entity.name);
  const [typeText, setTypeText] = useState(entityTypeLabel(t, entity.type));
  const [aliases, setAliases] = useState<string[]>(entity.aliases);
  const [tags, setTags] = useState<string[]>(entity.tags);
  const [content, setContent] = useState(entity.content);
  // The refusals are derived, not stored: once a save was tried, the words
  // stand exactly as long as the field does not answer them.
  const [triedSave, setTriedSave] = useState(false);
  const [failed, setFailed] = useState(false);
  // A relation row editor holds typed work the entity save knows nothing
  // about — saving and closing now would silently discard it, so the save
  // button stands down while one is open.
  const [rowEditorOpen, setRowEditorOpen] = useState(false);

  const typeItems = (Object.keys(TYPE_KEYS) as (keyof typeof TYPE_KEYS)[]).map((type) => ({
    id: type,
    text: t(TYPE_KEYS[type]),
  }));
  const nameInvalid = triedSave && name.trim() === "";
  // The box is the source of truth: its text resolves back to a type on
  // save, the way the search box's text is what the list filters by.
  const resolvedType = typeItems.find((item) => item.text === typeText.trim())?.id ?? null;
  const typeInvalid = triedSave && resolvedType === null;

  /** Save changed fields, clearing a blank body; keep the dialog open on refusal. */
  async function save(close: () => void) {
    setTriedSave(true);
    setFailed(false);
    const trimmedName = name.trim();
    if (trimmedName === "" || resolvedType === null) return;
    const nextContent = content.trim() === "" ? "" : content;
    const changes: EntityChanges = {};
    if (trimmedName !== entity.name) changes.name = trimmedName;
    if (resolvedType !== entity.type) changes.type = resolvedType;
    if (!sameList(aliases, entity.aliases)) changes.aliases = aliases;
    if (!sameList(tags, entity.tags)) changes.tags = tags;
    if (nextContent !== entity.content) changes.content = nextContent;
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
        <div className="mt-4 flex flex-col gap-3">
          <TextField
            label={t("knowledge.entityNameLabel")}
            value={name}
            onChange={setName}
            isInvalid={nameInvalid}
            validationMessage={nameInvalid ? t("knowledge.entityNameRequired") : undefined}
          />
          <ComboBox
            label={t("knowledge.entityTypeLabel")}
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
          {typeInvalid ? (
            <p className="text-sm text-danger">{t("knowledge.entityTypeRequired")}</p>
          ) : null}
          <ChipsField
            label={t("knowledge.entityAliasesLabel")}
            values={aliases}
            onChange={setAliases}
          />
          <ChipsField label={t("knowledge.entityTagsLabel")} values={tags} onChange={setTags} />
          {/* F-26: the body is prose, edited as rich text and stored as
              Markdown — the same shared editor the chapters use. A blank
              editor still saves as a cleared body. */}
          <MarkdownEditor
            label={t("knowledge.entityBodyLabel")}
            value={content}
            onChange={setContent}
          />
          <EntityRelationsSection
            entity={entity}
            rows={rows}
            onRowEditorChange={setRowEditorOpen}
          />
          {failed ? (
            <p role="alert" className="text-sm text-danger">
              {t("knowledge.entityFailed")}
            </p>
          ) : null}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void save(close)}
              disabled={rowEditorOpen}
              className={`${PRIMARY_BUTTON} disabled:cursor-not-allowed disabled:opacity-50`}
            >
              {t("knowledge.entitySave")}
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
