/** CR-AUFG-07-24 — KB improve suggestion → AIRatingViewModel. */

import type { ImproveSuggestion } from "@/lib/api/kb-improve";
import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface KBImproveRatingAdapterInput {
  readonly suggestion: ImproveSuggestion;
  readonly projectId: string;
  readonly action: FeedbackAction;
}

export function kbImproveRatingAdapter(
  input: KBImproveRatingAdapterInput,
): AIRatingViewModel | null {
  const sourceId = String(input.suggestion.suggestion_id).trim();
  const suggestionText = input.suggestion.description.trim();
  if (!sourceId || !suggestionText) return null;

  return {
    sourceType: "kb_improve_suggestion",
    sourceId,
    projectId: input.projectId,
    intent: "kb_improve",
    suggestionText,
    action: input.action,
    chapterId: null,
    genre: null,
    mode: null,
  };
}
