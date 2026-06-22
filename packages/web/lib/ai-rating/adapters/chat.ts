/** CR-AUFG-07-24 — Chat assistant message → AIRatingViewModel. */

import type { FeedbackAction } from "@/types";
import type { AIRatingViewModel } from "../contracts";

export interface ChatRatingAdapterInput {
  readonly messageId: string;
  readonly prose: string;
  readonly projectId: string;
  readonly action: FeedbackAction;
}

export function chatRatingAdapter(input: ChatRatingAdapterInput): AIRatingViewModel | null {
  const sourceId = input.messageId.trim();
  const suggestionText = input.prose.trim();
  if (!sourceId || !suggestionText) return null;

  return {
    sourceType: "chat_message",
    sourceId,
    projectId: input.projectId,
    intent: "chat_assistant",
    suggestionText,
    action: input.action,
    chapterId: null,
    genre: null,
    mode: null,
  };
}
