/**
 * The create dialog's pure seam (W9): resolving a typed relation target
 * against the novel's roster, spotting a name that already exists, and
 * turning the form into the POST body.
 *
 * A row's target is a name or an alias, trimmed and case-insensitive. Zero
 * matches or several are both unresolved: the dialog says so and the row is
 * left out — a guessed edge would be worse than none. A resolved row with no
 * label is left out the same way, and the dialog counts it too: no edge
 * disappears without the writer hearing about it. Duplicate names are
 * allowed by the API; the dialog only warns.
 */
import type { Entity, EntityCreate } from "@shell/lib/api/client";

/** The POST body the create hook carries; the generated contract is the truth. */
export type EntityCreateBody = EntityCreate;

/** The server's own bound (the spec's «at most 12 relations»), mirrored so
 *  the dialog disables its add control before the refusal can be met. */
export const MAX_RELATIONS = 12;

/** One relation row while the dialog edits it: the typed target, its label,
 *  an optional note. The target resolves at save time, never on keystroke. */
export type EntityRelationRow = {
  target: string;
  relationType: string;
  note: string;
};

/** The dialog's whole form, roster included so the body builder can resolve
 *  every row without the caller passing a second list. */
export type EntityCreateForm = {
  novelId: string;
  name: string;
  type: string;
  aliases: string[];
  tags: string[];
  content: string;
  relations: readonly EntityRelationRow[];
  entities: readonly Entity[];
};

export type RelationResolution =
  | { kind: "none" }
  | { kind: "one"; entity: Entity }
  | { kind: "many"; entities: Entity[] };

/** What the save will do with one edited row. Only a row with every field
 *  blank is an untouched add-row and says nothing; the two dropped kinds are
 *  what the dialog's notice counts, so a row the writer filled — even just
 *  its label or its note, with the target still to come — is never silent. */
export type RelationRowOutcome = "kept" | "unresolved-target" | "missing-label" | "empty";

const fold = (value: string): string => value.trim().toLowerCase();

/**
 * Resolve a typed name or alias to the novel's entities. The map keyed by
 * id folds the name and every alias into one match set, so two aliases of
 * the same row are still one entity, and two rows sharing a word are many.
 */
export function resolveRelationTarget(
  target: string,
  entities: readonly Entity[],
): RelationResolution {
  const key = fold(target);
  if (key === "") return { kind: "none" };
  const matches = new Map<string, Entity>();
  for (const entity of entities) {
    if (fold(entity.name) === key) matches.set(entity.id, entity);
    for (const alias of entity.aliases) {
      if (fold(alias) === key) matches.set(entity.id, entity);
    }
  }
  const found = [...matches.values()];
  if (found.length === 0) return { kind: "none" };
  if (found.length === 1) return { kind: "one", entity: found[0] };
  return { kind: "many", entities: found };
}

/** The row whose name already exists, or null. Names only — an alias is a
 *  different identity the merge path owns; the notice names the duplicate. */
export function findDuplicateName(name: string, entities: readonly Entity[]): Entity | null {
  const key = fold(name);
  if (key === "") return null;
  return entities.find((entity) => fold(entity.name) === key) ?? null;
}

/**
 * Whether the save keeps one row: a target that resolves to exactly one
 * entity and a label. Only a row whose every field is blank is an add-row
 * leftover; a row with a blank target but a typed label or note is a filled
 * row whose target is still missing, so it is dropped and counted like an
 * unresolvable target — the writer hears about it instead of losing the
 * label silently.
 */
export function relationRowOutcome(
  row: EntityRelationRow,
  entities: readonly Entity[],
): RelationRowOutcome {
  const hasTarget = row.target.trim() !== "";
  const hasLabel = row.relationType.trim() !== "";
  const hasNote = row.note.trim() !== "";
  if (!hasTarget && !hasLabel && !hasNote) return "empty";
  if (!hasTarget || resolveRelationTarget(row.target, entities).kind !== "one") {
    return "unresolved-target";
  }
  if (!hasLabel) return "missing-label";
  return "kept";
}

/**
 * The visible indices of the rows the save sends, in order — the body
 * builder's own kept list, exposed so a refusal's sent-list index can be
 * mapped back to the row on screen instead of printing the number.
 */
export function keptRelationRows(
  rows: readonly EntityRelationRow[],
  entities: readonly Entity[],
): number[] {
  const kept: number[] = [];
  rows.forEach((row, index) => {
    if (relationRowOutcome(row, entities) === "kept") kept.push(index);
  });
  return kept;
}

/**
 * The visible row a refusal's sent-list index names, or null when the
 * index lies outside the sent list (a server answer about a row the client
 * no longer holds).
 */
export function visibleRowForSentIndex(
  kept: readonly number[],
  sentIndex: number,
): number | null {
  return kept[sentIndex] ?? null;
}

/**
 * The visible rows whose normalized (target, label) pair equals an earlier
 * sent row's — the dialog's pre-save duplicate flag. The label has already
 * passed through `resolveRelationType`, so a localized wording beside its
 * canonical key counts as the same relation; the note is not part of the
 * server's identity and is ignored. Only rows the save sends can duplicate.
 */
export function duplicateRelationRows(
  rows: readonly EntityRelationRow[],
  entities: readonly Entity[],
): number[] {
  const firstByPair = new Map<string, number>();
  const duplicates = new Set<number>();
  for (const index of keptRelationRows(rows, entities)) {
    const row = rows[index];
    const resolution = resolveRelationTarget(row.target, entities);
    if (resolution.kind !== "one") continue;
    const pair = `${resolution.entity.id}\u0000${row.relationType.trim()}`;
    const first = firstByPair.get(pair);
    if (first === undefined) {
      firstByPair.set(pair, index);
    } else {
      duplicates.add(first);
      duplicates.add(index);
    }
  }
  return [...duplicates].sort((left, right) => left - right);
}

/** The closed set of refusal codes the create endpoint speaks. */
export const REFUSAL_CODES = [
  "not-found",
  "entity-invalid",
  "relation-target-invalid",
  "relation-duplicate",
  "relation-limit",
] as const;

export type RefusalCode = (typeof REFUSAL_CODES)[number];

/**
 * The catalog sentence for a wire refusal, keyed by its closed-set code.
 * A synthetic code (`transport`) or an unknown one maps to null: the face
 * falls back to the generic catalog sentence and never renders the wire's
 * English detail.
 */
export function refusalCatalogKey(
  code: string | undefined,
): `knowledge.create.refused.${RefusalCode}` | null {
  if (code === undefined || !REFUSAL_CODES.some((candidate) => candidate === code)) return null;
  return `knowledge.create.refused.${code as RefusalCode}`;
}

/**
 * The POST body: every row the roster resolves to exactly one entity and
 * that carries a relation label. The rest are left out — the dialog counts
 * them and says they will not be created.
 */
export function buildEntityCreateBody(form: EntityCreateForm): EntityCreateBody {
  const relations = [];
  for (const index of keptRelationRows(form.relations, form.entities)) {
    const row = form.relations[index];
    const resolution = resolveRelationTarget(row.target, form.entities);
    if (resolution.kind !== "one") continue;
    relations.push({
      to_entity_id: resolution.entity.id,
      relation_type: row.relationType.trim(),
      note: row.note.trim() === "" ? null : row.note.trim(),
    });
  }
  return {
    novel_id: form.novelId,
    name: form.name.trim(),
    type: form.type,
    aliases: form.aliases,
    tags: form.tags,
    content: form.content,
    relations,
  };
}
