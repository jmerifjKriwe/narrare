/**
 * Curated display order for the prompt-category filter pills.
 *
 * SINGLE SOURCE OF TRUTH — keep in sync when adding a bundled prompt
 * category:
 *   - sub-directories of ``packages/core/narrare_core/prompts/_bundled/``
 *     (the 7 feature categories: ai_assist, analysis, generation, kb,
 *     planning, wiki, writing — ``meta``/``universal`` are ADR-026
 *     Capabilities, not feature categories)
 *   - ``INTENT_TO_CATEGORY`` in
 *     ``packages/core/narrare_core/prompts/route_table.py``
 *
 * There is no shared TS/Python enum for prompt categories today (the
 * ``PromptInfo.category`` wire field is a free-form ``string``), so this
 * constant is the frontend's curated mirror. Drift is mitigated by
 * ``mergeFilterCategories`` which appends any categories the API
 * actually returns.
 *
 * Drift history: ``ai_assist``, ``planning`` and ``wiki`` were missing
 * here for several releases even though their i18n labels existed —
 * users could see the prompts in the "All" view but could not filter
 * to them.
 */
export const PROMPT_CATEGORIES = [
  "generation",
  "writing",
  "analysis",
  "kb",
  "ai_assist",
  "planning",
  "wiki",
] as const;

export type PromptCategory = (typeof PROMPT_CATEGORIES)[number];

/**
 * Build the filter-pill order: curated categories first, then any
 * unexpected categories the API returned (defensive — keeps the UI
 * usable if a new category is added to ``prompts/_bundled/`` before
 * ``PROMPT_CATEGORIES`` is updated).
 *
 * @param presentCategories - categories the API actually returned
 *   (e.g. ``Object.keys(groupedPrompts)``).
 */
export function mergeFilterCategories(presentCategories: readonly string[]): readonly string[] {
  const curated = PROMPT_CATEGORIES as readonly string[];
  const extra = presentCategories.filter((c) => !curated.includes(c)).sort();
  return [...curated, ...extra];
}
