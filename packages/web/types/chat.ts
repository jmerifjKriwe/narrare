// Chat SSE types (ADR-024 Free-Form Chat)

import type { TokenUsage } from "./settings";

export interface ChatMetaEvent {
  conversation_id: string;
  request_id: string;
}

export interface ChatDoneEvent {
  type: "done";
  usage: TokenUsage;
}
