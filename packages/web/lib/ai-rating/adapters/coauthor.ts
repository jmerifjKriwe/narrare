/** CR-AUFG-07-24 — Co-Author change → AIRatingViewModel. */

import type { ChangeDetail } from "@/lib/api/coauthor";
import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface CoAuthorRatingAdapterInput {
  readonly change: ChangeDetail;
  readonly projectId: string;
  readonly chapterId: string | null;
  readonly action: FeedbackAction;
}

export function coAuthorRatingAdapter(input: CoAuthorRatingAdapterInput): AIRatingViewModel | null {
  const sourceId = input.change.id.trim();
  const suggestionText = input.change.revised_text.trim();
  if (!sourceId || !suggestionText) return null;

  return {
    sourceType: "co_author_change",
    sourceId,
    projectId: input.projectId,
    intent: "co_author",
    suggestionText,
    action: input.action,
    chapterId: input.chapterId,
    genre: null,
    mode: null,
  };
}
