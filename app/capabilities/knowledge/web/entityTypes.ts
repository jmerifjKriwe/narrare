import type { MessageKey } from "@shell/lib/i18n";

// The extraction contract's types (kernel contracts' ENTITY_TYPES), as
// catalog keys. A type the contract later adds falls back to "generic" rather
// than crashing the render; the list is the contract's, so it lives beside
// its first consumer and the review queue imports it from here.
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

/** An entity type in the user's language — the list's and the review
 *  queue's shared wording for what a filed row is. */
export function entityTypeLabel(t: (key: MessageKey) => string, type: string): string {
  return type in TYPE_KEYS
    ? t(TYPE_KEYS[type as keyof typeof TYPE_KEYS])
    : t("knowledge.type.generic");
}
