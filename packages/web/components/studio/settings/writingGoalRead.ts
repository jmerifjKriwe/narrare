/**
 * Writing-goal read-side helpers (STATS-001) — pure narrowing/parsing, no
 * React. Extracted from WritingGoalsTab (RULE-04): the defensive-read and
 * strict-draft contracts are the unit-tested core of the goal field.
 *
 * READ side is defensive by contract: the GET returns the JSONB value as a
 * LOOSE `unknown` (a corrupt stored row must degrade, never fail the
 * render), so `parseTargetWords` narrows before any `target_words` access —
 * the FE mirror of the API's `settings.writing_goals.parse_target_words`.
 */

/**
 * Typed accessor for the v1 goal shape — FE mirror of the API's
 * `settings.writing_goals.parse_target_words`. Returns the stored target
 * int, or null (no goal) for a NULL column, an explicit null target, or ANY
 * corrupt/non-object value (scalars, arrays, booleans, wrong-typed target —
 * bool ⊂ int is excluded by the typeof check). Corruption degrades to
 * "unset", never a crash.
 */
export function parseTargetWords(data: unknown): number | null {
  if (typeof data !== "object" || data === null) return null;
  const target = (data as Record<string, unknown>).target_words;
  if (typeof target !== "number" || !Number.isInteger(target)) return null;
  return target;
}

/**
 * Strict draft parsing for the goal input: "" = clear (null = unset);
 * otherwise only a non-negative integer is a valid target. Everything else
 * (negative, fractional, garbage) is rejected so it can never reach the
 * strict PATCH (which would answer 422).
 */
export function parseGoalDraft(draft: string): number | null | "invalid" {
  const trimmed = draft.trim();
  if (trimmed === "") return null;
  if (!/^\d+$/.test(trimmed)) return "invalid";
  return Number(trimmed);
}
