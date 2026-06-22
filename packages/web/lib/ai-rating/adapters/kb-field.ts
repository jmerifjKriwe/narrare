/** CR-AUFG-07-24 — KB field suggestion → AIRatingViewModel. */

import type { KBCreationField } from "@/lib/api/kb-sessions";
import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface KBFieldSuggestRatingAdapterInput {
  readonly field: KBCreationField;
  readonly projectId: string;
  readonly action: FeedbackAction;
}

export function kbFieldSuggestRatingAdapter(
  input: KBFieldSuggestRatingAdapterInput,
): AIRatingViewModel | null {
  const sourceId = input.field.field_key.trim();
  const suggestionText = input.field.ai_suggested_value?.trim() ?? "";
  if (!sourceId || !suggestionText) return null;

  return {
    sourceType: "kb_field_suggest",
    sourceId,
    projectId: input.projectId,
    intent: "kb_field_suggest",
    suggestionText,
    action: input.action,
    chapterId: null,
    genre: null,
    mode: null,
  };
}
