import type { PromptRevisionCompareResponse } from "@/types";
import type { AIDiffViewModel } from "../contracts";
import { segmentize } from "../segmentize";

/**
 * Build a text-mode {@link AIDiffViewModel} from a prompt-history compare
 * response (CR-AUFG-07-19).
 *
 * The compare endpoint returns two whole prompt contents (``from_content`` →
 * ``to_content``). We project them onto the shared diff vocabulary so the
 * existing :component:`AIDiffView` renders the revision diff without any
 * prompt-history-specific knowledge (RULE-07: components → lib).
 *
 * History is never a streaming operation, so ``provisional`` is always false.
 */
export function promptHistoryDiffAdapter(compare: PromptRevisionCompareResponse): AIDiffViewModel {
  return {
    id: `${compare.from_id}..${compare.to_id}`,
    mode: "text",
    segments: segmentize(compare.from_content, compare.to_content),
    originalFull: compare.from_content,
    suggestedFull: compare.to_content,
    label: `${compare.from_source} → ${compare.to_source}`,
    provisional: false,
  };
}
