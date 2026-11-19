import type { MessageKey } from "@shell/lib/i18n";

/**
 * The suggested relation vocabulary (Fahrplan §4.2), verbatim. It is a UI
 * suggestion, not an API constraint (D7): the stored `relation_type` is
 * free text, and whatever the extraction proposed is stored as its raw
 * string. Restored from the pre-W0 archive (W5 Task 2) — the suggestion
 * cards speak the vocabulary's wording; the CRUD boxes (Task 4) ride the
 * autocomplete (`relationTypeOptions`) and the label-to-type resolver
 * (`resolveRelationType`) below.
 */
export const RELATION_TYPES = [
  "ally_of",
  "enemy_of",
  "mentor_of",
  "student_of",
  "family_of",
  "friend_of",
  "rival_of",
  "located_in",
  "controls",
  "owns",
  "inhabits",
  "member_of",
  "leads",
  "founded",
  "created",
  "destroyed",
  "transformed_into",
  "appears_in",
  "mentioned_in",
  "caused",
  "related_to",
] as const;

// The vocabulary as catalog keys. A stored type outside the list is free
// text by design, so the label helper falls back to the raw string rather
// than mistranslating or crashing the render.
const RELATION_KEYS: Record<(typeof RELATION_TYPES)[number], MessageKey> = {
  ally_of: "knowledge.relation.ally_of",
  enemy_of: "knowledge.relation.enemy_of",
  mentor_of: "knowledge.relation.mentor_of",
  student_of: "knowledge.relation.student_of",
  family_of: "knowledge.relation.family_of",
  friend_of: "knowledge.relation.friend_of",
  rival_of: "knowledge.relation.rival_of",
  located_in: "knowledge.relation.located_in",
  controls: "knowledge.relation.controls",
  owns: "knowledge.relation.owns",
  inhabits: "knowledge.relation.inhabits",
  member_of: "knowledge.relation.member_of",
  leads: "knowledge.relation.leads",
  founded: "knowledge.relation.founded",
  created: "knowledge.relation.created",
  destroyed: "knowledge.relation.destroyed",
  transformed_into: "knowledge.relation.transformed_into",
  appears_in: "knowledge.relation.appears_in",
  mentioned_in: "knowledge.relation.mentioned_in",
  caused: "knowledge.relation.caused",
  related_to: "knowledge.relation.related_to",
};

/** A relation type in the user's language: the vocabulary's wording, or
 *  the free text itself when the stored type is no vocabulary entry. The
 *  check is an own-property one: a plain object inherits ``constructor``
 *  and friends, and a free-text type spelling one of those must fall
 *  back to itself, not hand a function to ``t``. */
export function relationTypeLabel(
  t: (key: MessageKey) => string,
  relationType: string,
): string {
  if (!Object.hasOwn(RELATION_KEYS, relationType)) return relationType;
  return t(RELATION_KEYS[relationType as (typeof RELATION_TYPES)[number]]);
}

/** The vocabulary as the CRUD type box's autocomplete suggestions: each
 *  entry's stored key beside its wording in the reader's language (D7 — a
 *  suggestion, not a constraint; the box also takes free text). */
export function relationTypeOptions(
  t: (key: MessageKey) => string,
): { key: (typeof RELATION_TYPES)[number]; label: string }[] {
  return RELATION_TYPES.map((key) => ({ key, label: t(RELATION_KEYS[key]) }));
}

/** The type the box stores: a suggestion picked by its wording resolves back
 *  to the vocabulary key (so the graph re-localizes it), any other trimmed
 *  input rides as the free text it is (D7). The round trip is the label
 *  helper's inverse — `relationTypeLabel` then `resolveRelationType` returns
 *  the key; an unknown string returns itself. */
export function resolveRelationType(
  t: (key: MessageKey) => string,
  value: string,
): string {
  const trimmed = value.trim();
  for (const key of RELATION_TYPES) {
    if (t(RELATION_KEYS[key]) === trimmed) return key;
  }
  return trimmed;
}
