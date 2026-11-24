/**
 * The create dialog's pure seam (W9): resolving a typed relation target
 * against the novel's roster, spotting a name that already exists, and
 * turning the form into the POST body.
 *
 * A row's target is a name or an alias, trimmed and case-insensitive. Zero
 * matches or several are both unresolved: the dialog says so and the row is
 * left out — a guessed edge would be worse than none. Duplicate names are
 * allowed by the API; the dialog only warns.
 */
import type { Entity, EntityCreate } from "@shell/lib/api/client";

/** The POST body the create hook carries; the generated contract is the truth. */
export type EntityCreateBody = EntityCreate;

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
 * The POST body: every row the roster resolves to exactly one entity and
 * that carries a relation label. The rest are left out — the dialog counts
 * them and says they will not be created.
 */
export function buildEntityCreateBody(form: EntityCreateForm): EntityCreateBody {
  const relations = [];
  for (const row of form.relations) {
    const resolution = resolveRelationTarget(row.target, form.entities);
    if (resolution.kind !== "one") continue;
    const relationType = row.relationType.trim();
    if (relationType === "") continue;
    relations.push({
      to_entity_id: resolution.entity.id,
      relation_type: relationType,
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
