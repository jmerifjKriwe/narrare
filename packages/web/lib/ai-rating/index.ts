/**
 * CR-AUFG-07-24 — shared AI rating vocabulary. Public surface.
 *
 * Task 5 scope: contracts + payload builder only. Per-surface adapters
 * (Co-Author, KB field/enhance/improve, Chat) are added in Tasks 8–12 and
 * their exports appended here as they land.
 */

export type { ChatRatingAdapterInput } from "./adapters/chat";
export { chatRatingAdapter } from "./adapters/chat";
export type { CoAuthorRatingAdapterInput } from "./adapters/coauthor";
export { coAuthorRatingAdapter } from "./adapters/coauthor";
export type { KBEnhanceRatingAdapterInput } from "./adapters/kb-enhance";
export { kbEnhanceRatingAdapter } from "./adapters/kb-enhance";
export type { KBFieldSuggestRatingAdapterInput } from "./adapters/kb-field";
export { kbFieldSuggestRatingAdapter } from "./adapters/kb-field";
export type { KBImproveRatingAdapterInput } from "./adapters/kb-improve";
export { kbImproveRatingAdapter } from "./adapters/kb-improve";
export { buildFeedbackRequest } from "./build-feedback";
export type {
  AIRatingInput,
  AIRatingScale,
  AIRatingState,
  AIRatingViewModel,
} from "./contracts";
