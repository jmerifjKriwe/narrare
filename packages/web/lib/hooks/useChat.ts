"use client";

/**
 * React hook for the free-form chat (ChatPanel).
 *
 * Wraps SSE streaming from POST /api/v1/chat with:
 * - Message history (local state)
 * - Streaming text accumulation
 * - AbortController for cancellation
 * - Auto-scroll via ref
 * - Conversation ID management (auto-start new, reuse existing)
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { chatApi } from "@/lib/api/client";
import type { ChatDoneEvent, ChatMetaEvent } from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  readonly id: string;
  readonly role: "user" | "assistant" | "system";
  readonly content: string;
}

interface UseChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  conversationId: string | null;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  clearConversation: () => void;
  cancelStream: () => void;
  chatEndRef: React.RefObject<HTMLDivElement | null>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let messageCounter = 0;

function createMessageId(): string {
  messageCounter += 1;
  return `chat-msg-${messageCounter}`;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useChat(projectId: string): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll after any render with new content (cheap no-op if already at bottom)
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      setError(null);

      // Add user message
      const userMsg: ChatMessage = {
        id: createMessageId(),
        role: "user",
        content: trimmed,
      };
      setMessages((prev) => [...prev, userMsg]);

      // Create abort controller
      const controller = new AbortController();
      abortRef.current = controller;

      setIsStreaming(true);

      let assistantContent = "";

      await chatApi.streamChat(
        {
          project_id: projectId,
          message: trimmed,
          conversation_id: conversationId,
        },
        {
          onMeta: (meta: ChatMetaEvent) => {
            setConversationId(meta.conversation_id);
          },
          onToken: (text: string) => {
            assistantContent += text;
          },
          onDone: (_done: ChatDoneEvent) => {
            setMessages((prev) => [
              ...prev,
              {
                id: createMessageId(),
                role: "assistant",
                content: assistantContent,
              },
            ]);
            setIsStreaming(false);
            assistantContent = "";
          },
          onError: (err: Error) => {
            // If we have partial content, still show it
            if (assistantContent) {
              setMessages((prev) => [
                ...prev,
                {
                  id: createMessageId(),
                  role: "assistant",
                  content: assistantContent,
                },
              ]);
              assistantContent = "";
            }
            setError(err.message);
            setIsStreaming(false);
          },
        },
        controller.signal,
      );
    },
    [projectId, conversationId, isStreaming],
  );

  const clearConversation = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setError(null);
    setIsStreaming(false);
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, []);

  return {
    messages,
    isStreaming,
    conversationId,
    error,
    sendMessage,
    clearConversation,
    cancelStream,
    chatEndRef,
  };
}
