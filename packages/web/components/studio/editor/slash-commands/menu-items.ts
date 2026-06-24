/**
 * Pure slash-command menu helpers (CR-AUFG-07-20).
 *
 * Extracted from the React hook so the filtering + availability logic is
 * unit-testable without a TipTap editor. Locale-dependent label tokens are
 * resolved here via the translator passed by the host.
 */
import type { AISlashCommandDefinition, SlashCommandAvailabilityInput } from "./contracts";
import { filterCommands, type SlashTokenized } from "./parser";
import type { SlashCommandMenuItem } from "./SlashCommandMenu";

/** Wraps `index` into the `[0, length)` range (empty list → 0). */
export function clampActiveIndex(index: number, length: number): number {
  if (length <= 0) return 0;
  return ((index % length) + length) % length;
}

type Translator = (key: string, params?: Record<string, unknown>) => string;

/** Lowercased matchable tokens for a command: id, aliases, label words. */
function tokensOf(cmd: AISlashCommandDefinition, t: Translator): readonly string[] {
  const labelWords = t(cmd.labelKey).split(/\s+/).filter(Boolean);
  return [cmd.id, ...cmd.aliases, ...labelWords].map((tok) => tok.toLowerCase());
}

/**
 * Build the filtered, availability-resolved menu items.
 *
 * @param commands  The full registry.
 * @param query     Current filter query (text after the `/`).
 * @param t         next-intl translator (scoped to `studio`).
 * @param hasSelection Whether the editor currently has a selection.
 * @param wiredOps  operation_ids the host surface wired handlers for.
 */
export function buildMenuItems(
  commands: readonly AISlashCommandDefinition[],
  query: string,
  t: Translator,
  hasSelection: boolean,
  wiredOps: ReadonlySet<string>,
): SlashCommandMenuItem[] {
  const tokenized: (AISlashCommandDefinition & SlashTokenized)[] = commands.map((cmd) => ({
    ...cmd,
    tokens: tokensOf(cmd, t),
  }));
  const filtered = filterCommands(tokenized, query);
  return filtered.map((cmd) => {
    const input: SlashCommandAvailabilityInput = {
      hasSelection,
      wired: wiredOps.has(cmd.operationId),
    };
    return {
      id: cmd.id,
      labelKey: cmd.labelKey,
      descriptionKey: cmd.descriptionKey,
      availability: cmd.availability(input),
    };
  });
}
