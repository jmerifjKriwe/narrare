/**
 * Shared keyboard shortcut predicates for AI output actions.
 *
 * Keeps §16 AI action shortcuts consistent across review surfaces without
 * coupling components to each other.
 */

export function isApplyShortcut(event: KeyboardEvent): boolean {
  return (event.ctrlKey || event.metaKey) && event.key === "Enter";
}

export function isEscapeShortcut(event: KeyboardEvent): boolean {
  return event.key === "Escape";
}

export const AI_APPLY_ARIA_SHORTCUT = "Control+Enter Meta+Enter";
export const AI_ESCAPE_ARIA_SHORTCUT = "Escape";
