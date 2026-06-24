/**
 * Slash-commands public surface (CR-AUFG-07-20).
 *
 * Hosts (e.g. TipTapEditor) import from here. The registry/parser/menu/hook
 * internals stay in their own modules (RULE-06 — one responsibility per file).
 */
export type {
  AISlashCommandDefinition,
  SlashCommandAvailability,
  SlashCommandAvailabilityInput,
  SlashCommandDispatchContext,
  SlashCommandDispatchFn,
} from "./contracts";
export { buildMenuItems, clampActiveIndex } from "./menu-items";
export { filterCommands, parseSlashInput } from "./parser";
export { AI_SLASH_COMMANDS, defaultAvailability, KNOWN_OPERATION_IDS } from "./registry";
export type { SlashCommandMenuItem } from "./SlashCommandMenu";
export { SlashCommandMenu } from "./SlashCommandMenu";
export type { SlashCommandState, UseSlashCommandStateParams } from "./useSlashCommandState";
export { useSlashCommandState } from "./useSlashCommandState";

/**
 * Host-facing handler map for the operations the editor does not own itself.
 *
 * `rewrite` is always wired from the editor controller; the remaining five are
 * supplied by the host (panel-open callbacks / navigation). Any handler omitted
 * renders its command unavailable with actionable guidance.
 */
export interface SlashCommandHandlers {
  readonly onContinue: () => void;
  readonly onGenerate: () => void;
  readonly onCoAuthor: () => void;
  readonly onAskChat: (prefilledQuestion?: string) => void;
  readonly onExplainSelection: () => void;
}
