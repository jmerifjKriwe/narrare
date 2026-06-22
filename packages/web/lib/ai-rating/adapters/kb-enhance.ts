/** CR-AUFG-07-24 — KB enhance field → AIRatingViewModel. */

import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface KBEnhanceRatingAdapterInput {
  readonly enhancement: KBEnhancementResult;
  readonly projectId: string;
  readonly fieldLabel: string;
  readonly action: FeedbackAction;
}

export function kbEnhanceRatingAdapter(
  input: KBEnhanceRatingAdapterInput,
): AIRatingViewModel | null {
  const sourceId = input.enhancement.field_key.trim();
  const suggestionText = input.enhancement.suggested.trim();
  if (!sourceId || !suggestionText) return null;

  return {
    sourceType: "kb_enhance_field",
    sourceId,
    projectId: input.projectId,
    intent: "kb_enhance",
    suggestionText,
    action: input.action,
    chapterId: null,
    genre: null,
    mode: null,
  };
}
