import type { MessageKey } from "@shell/lib/i18n";

/**
 * The suggested relation vocabulary (Fahrplan §4.2), verbatim. It is a UI
 * suggestion, not an API constraint (D7): the add and edit boxes
 * autocomplete these and accept any free text beside them, and whatever
 * the box carries is stored as the raw `relation_type` string.
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
 *  the free text itself when the stored type is no vocabulary entry. */
export function relationTypeLabel(
  t: (key: MessageKey) => string,
  relationType: string,
): string {
  const key = RELATION_KEYS[relationType as (typeof RELATION_TYPES)[number]];
  return key !== undefined ? t(key) : relationType;
}

/**
 * The box's text resolved back to what the edge stores: a vocabulary
 * entry when the text is one of its labels, otherwise the text itself —
 * free text is a first-class answer, not a refusal. An empty box carries
 * no type at all.
 */
export function resolveRelationType(
  items: { id: string; text: string }[],
  text: string,
): string {
  const trimmed = text.trim();
  const picked = items.find((item) => item.text === trimmed);
  return picked !== undefined ? picked.id : trimmed;
}
