import type { RefObject } from "react";

export interface ChatMessage {
  readonly id: string;
  readonly role: "user" | "assistant" | "system";
  readonly content: string;
}

export interface ChatMetaEvent {
  readonly conversation_id: string;
  readonly request_id: string;
}

export interface ChatUsage {
  readonly prompt_tokens: number;
  readonly completion_tokens: number;
  readonly total_tokens: number;
}

export interface ChatDoneEvent {
  readonly type: "done";
  readonly usage: ChatUsage;
}

export interface UseChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  conversationId: string | null;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  clearConversation: () => void;
  cancelStream: () => void;
  chatEndRef: RefObject<HTMLDivElement | null>;
}

let messageCounter = 0;

export function createMessageId(): string {
  messageCounter += 1;
  return `chat-msg-${messageCounter}`;
}
