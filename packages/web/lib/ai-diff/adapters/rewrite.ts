import type { AIDiffViewModel } from "../contracts";
import { segmentize } from "../segmentize";

/**
 * Build a text-mode {@link AIDiffViewModel} for a single Rewrite alternative.
 *
 * Takes primitives only (no component import) so `lib/ai-diff` never depends on
 * `components/` (RULE-07 direction: components -> lib, never lib -> components).
 */
export function rewriteAdapter(
  original: string,
  suggestion: string,
  label: string | null,
  provisional: boolean,
): AIDiffViewModel {
  return {
    id: `rewrite-${suggestion.slice(0, 32)}`,
    mode: "text",
    segments: segmentize(original, suggestion),
    originalFull: original,
    suggestedFull: suggestion,
    label,
    provisional,
  };
}
