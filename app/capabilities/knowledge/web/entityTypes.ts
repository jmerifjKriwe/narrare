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

/**
 * The type's accent, as shell tokens (W5 Task 3 — the graph's nodes and the
 * dossier's relation dots). The draft pins a hex per concept; the port rides
 * the token ladder instead, one accent per contract type, each a light-dark
 * pair so both themes carry it. The colour is the node's graphics (avatar
 * tint, dot, edge ink — the 3:1 graphic floor); the badge's WORDS stay
 * neutral foreground so small text keeps AA whatever the accent. An unknown
 * type falls back to the generic muted accent, the label helper's own rule.
 */
export interface TypeTheme {
  /** The CSS colour for SVG ink and inline styles. */
  var: string;
  /** The dot's fill utility. */
  dot: string;
  /** The avatar/badge tint utility. */
  tint: string;
}

export const TYPE_THEME: Record<keyof typeof TYPE_KEYS, TypeTheme> = {
  character: { var: "var(--primary)", dot: "bg-primary", tint: "bg-primary/10" },
  location: { var: "var(--area-chat)", dot: "bg-area-chat", tint: "bg-area-chat/10" },
  faction: { var: "var(--area-planning)", dot: "bg-area-planning", tint: "bg-area-planning/10" },
  object: { var: "var(--warning)", dot: "bg-warning", tint: "bg-warning/10" },
  system: { var: "var(--area-settings)", dot: "bg-area-settings", tint: "bg-area-settings/10" },
  timeline: { var: "var(--secondary)", dot: "bg-secondary", tint: "bg-secondary/10" },
  event: { var: "var(--area-knowledge)", dot: "bg-area-knowledge", tint: "bg-area-knowledge/10" },
  generic: { var: "var(--muted)", dot: "bg-muted", tint: "bg-muted/10" },
};

/** The type's accent, with the same own-property fallback as the label. */
export function typeTheme(type: string): TypeTheme {
  return Object.hasOwn(TYPE_THEME, type) ? TYPE_THEME[type as keyof typeof TYPE_THEME] : TYPE_THEME.generic;
}
