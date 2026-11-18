import type { MessageKey } from "@shell/lib/i18n";
import type { IconName } from "@shell/ui/icons";

/**
 * The extraction contract's types (kernel contracts' ENTITY_TYPES), as
 * catalog keys. A type the contract later adds falls back to "generic"
 * rather than crashing the render; the list is the contract's, so it
 * lives beside its first consumer and the review queue imports it from
 * here. Restored from the pre-W0 archive (W5 Task 2) — the dock's chips
 * and the suggestion cards speak the same vocabulary.
 */
export const TYPE_KEYS = {
  character: "knowledge.type.character",
  location: "knowledge.type.location",
  faction: "knowledge.type.faction",
  object: "knowledge.type.object",
  system: "knowledge.type.system",
  timeline: "knowledge.type.timeline",
  event: "knowledge.type.event",
  generic: "knowledge.type.generic",
} as const;

/**
 * The type's glyph — the app's own face for the concept the drafts pin
 * with Material names (person, location_on, token, …). The set has no
 * dedicated drawings for the contract's eight types, so each wears the
 * closest single-stroke metaphor it already carries; an unknown type
 * falls back to the knowledge stack, the generic label's own glyph.
 */
export const TYPE_ICONS: Record<keyof typeof TYPE_KEYS, IconName> = {
  character: "person",
  location: "house",
  faction: "shield",
  object: "archive",
  system: "schema",
  timeline: "clock",
  event: "historyEdu",
  generic: "knowledge",
};

/** An entity type in the user's language — the chips' and the review
 *  queue's shared wording for what a filed row is. The check is an
 *  own-property one: a plain object inherits ``constructor`` and
 *  friends, and a type spelling one of those must fall back to the
 *  generic label, not hand a function to ``t``. */
export function entityTypeLabel(t: (key: MessageKey) => string, type: string): string {
  return Object.hasOwn(TYPE_KEYS, type)
    ? t(TYPE_KEYS[type as keyof typeof TYPE_KEYS])
    : t("knowledge.type.generic");
}

/** The type's glyph name, with the same own-property fallback. */
export function entityTypeIcon(type: string): IconName {
  return Object.hasOwn(TYPE_ICONS, type) ? TYPE_ICONS[type as keyof typeof TYPE_ICONS] : "knowledge";
}
