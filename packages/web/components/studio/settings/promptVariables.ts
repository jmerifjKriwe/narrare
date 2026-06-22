/**
 * Pure helpers for deriving PROMPT-003 preview/live-test request variables
 * from a prompt id.
 *
 * The settings UI does not have access to the full project context (KB,
 * storyboard, …). It must not fabricate values for those variables — the
 * backend surfaces them as ``missing_variable`` diagnostics, which is the
 * intended behaviour for a provider-free settings preview (see
 * PROMPT-003 spec). Only well-known *system* variables that can be derived
 * from the prompt id itself are populated here.
 */

import type { PromptPreviewLanguage } from "@/types";

/** Result of parsing a ``{category}/{language}/{mode}`` prompt id. */
export interface ParsedPromptId {
  readonly category: string;
  readonly language: string;
  readonly mode: string;
}

/** Canonical fallback returned when the id does not match the 3-segment layout. */
const PARSE_FALLBACK: ParsedPromptId = { category: "", language: "en", mode: "" };

/**
 * Parse a ``{category}/{language}/{mode}`` prompt id (e.g.
 * ``"writing/en/new_chapter"``) into its three segments.
 *
 * Returns a safe fallback (``language: "en"`` matches the hook default) when
 * the id is malformed so callers never throw on an unexpected shape.
 *
 * Pure: no I/O, no side effects — trivially unit-testable.
 */
export function parsePromptId(promptId: string): ParsedPromptId {
  const segments = promptId.split("/");
  if (segments.length !== 3 || segments.some((segment) => segment.length === 0)) {
    return PARSE_FALLBACK;
  }
  const [category, language, mode] = segments;
  return { category, language, mode };
}

/**
 * Build the system-variable map for a preview or live-test request.
 *
 * Populates only system variables derivable from the prompt id and the
 * caller's UI language:
 *   - ``language`` — always sent (matches the request body's ``language``).
 *   - ``mode``     — sent when the prompt id carries a non-empty mode segment.
 *
 * Project-context variables (KB, storyboard, profile, …) are intentionally
 * absent: the settings UI has no project scope and MUST NOT fabricate
 * values. The backend lists them as ``missing_variable`` diagnostics.
 */
export function buildSystemVariables(
  promptId: string,
  language: PromptPreviewLanguage,
): Record<string, string> {
  const { mode } = parsePromptId(promptId);
  const variables: Record<string, string> = { language };
  if (mode) {
    variables.mode = mode;
  }
  return variables;
}
