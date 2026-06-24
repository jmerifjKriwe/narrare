/**
 * Slash-command parser (CR-AUFG-07-20).
 *
 * Pure, locale-independent detection + filtering for the editor slash menu.
 * The hook layer ({@link useSlashCommandState}) feeds this parser the text of
 * the current textblock up to the caret and adds locale-specific label tokens
 * via {@link filterCommands}.
 *
 * Design notes:
 * - Detection requires the `/` to be the first non-whitespace character of the
 *   paragraph ("empty paragraph" per spec §38). A space or second slash after
 *   the query cancels activation so the `/` stays as normal prose (spec §43).
 * - The parser never mutates the document; deletion of the `/query` happens in
 *   the hook only after a command is explicitly selected.
 */

/** Result of inspecting the textblock text before the caret. */
export interface SlashParseResult {
  /** Whether the slash menu should be open. */
  readonly active: boolean;
  /** The text typed after the leading `/`. */
  readonly query: string;
  /** Document offset of the `/` character (used to delete it on select). */
  readonly slashPos: number;
}

/**
 * Pattern for an activating slash input.
 *
 * - `^` paragraph start
 * - `(\s*)` optional leading whitespace (still counts as an empty paragraph)
 * - `/` the activating slash
 * - `([^\s/]*)` the query: no spaces, no second slash
 * - `$` end of the inspected text
 *
 * A trailing space or slash breaks the match → caller treats the `/` as prose.
 */
const ACTIVATING_PATTERN = /^(\s*)\/([^\s/]*)$/;

/**
 * Inspect textblock text (from paragraph start up to the caret) and decide
 * whether the slash menu should be open.
 *
 * @param textBeforeCaret The text content of the current textblock from its
 *   start up to (but not including) the caret.
 * @param textBlockStart Document offset where this textblock begins.
 * @returns The parse result when active, or `null` when the input is prose.
 */
export function parseSlashInput(
  textBeforeCaret: string,
  textBlockStart: number,
): SlashParseResult | null {
  const match = ACTIVATING_PATTERN.exec(textBeforeCaret);
  if (!match) return null;
  const leadingWhitespace = match[1];
  const query = match[2];
  return {
    active: true,
    query,
    slashPos: textBlockStart + leadingWhitespace.length,
  };
}

/** A command reduced to its matchable tokens (for locale-independent filtering). */
export interface SlashTokenized {
  readonly id: string;
  /** Lowercased tokens used for matching (id, aliases, optional label words). */
  readonly tokens: readonly string[];
}

/**
 * Filter commands by a (possibly empty) query against their tokens.
 *
 * Empty query returns every command. Otherwise a command matches when any token
 * contains the query substring (case-insensitive), which lets aliases such as
 * `co-author` match the query `co-aut`.
 *
 * @typeParam C The command shape; must at least expose {@link SlashTokenized}.
 */
export function filterCommands<C extends SlashTokenized>(
  commands: readonly C[],
  query: string,
): C[] {
  const q = query.toLowerCase();
  if (!q) return [...commands];
  return commands.filter((cmd) => cmd.tokens.some((tok) => tok.toLowerCase().includes(q)));
}
