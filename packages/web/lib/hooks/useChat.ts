"use client";

/**
 * React hook for the free-form chat (ChatPanel) — §16 AI-Interaction Standards.
 *
 * Wraps SSE streaming via useAIOperation for lifecycle management
 * (no manual AbortController, connection-loss detection, retry support).
 *
 * @module useChat
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import { chatApi } from "@/lib/api/client";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation.types";
import type { ChatDoneEvent, ChatMetaEvent } from "@/types";
import { type ChatMessage, createMessageId, type UseChatReturn } from "@/types/chat";

/**
 * @param projectId - Project (novel) scope, or null for project-less chat
 *   (NOTES-001 global notes).
 * @param noteId - Optional scratchpad note attached as runtime context.
 */
export function useChat(projectId: string | null, noteId?: string | null): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<AIErrorResponse | null>(null);

  const messageRef = useRef("");
  const accumulatedRef = useRef("");
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const conversationIdRef = useRef(conversationId);
  conversationIdRef.current = conversationId;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  const aiOp = useAIOperation<string | null>({
    execute: async (signal) => {
      const msg = messageRef.current;
      if (!msg) return null;
      let content = "";
      accumulatedRef.current = "";
      await chatApi.streamChat(
        {
          project_id: projectId,
          message: msg,
          conversation_id: conversationIdRef.current,
          note_id: noteId ?? null,
        },
        {
          onMeta: (meta: ChatMetaEvent) => {
            setConversationId(meta.conversation_id);
            aiOp.notifyData();
          },
          onToken: (text: string) => {
            content += text;
            accumulatedRef.current = content;
            aiOp.notifyData();
          },
          onDone: (_done: ChatDoneEvent) => {
            /* content accumulated */
          },
          onError: (err: Error) => {
            throw err;
          },
        },
        signal,
      );
      return content || null;
    },
    errorMapper: (error) => {
      if (
        (error instanceof DOMException && error.name === "AbortError") ||
        (error instanceof Error && error.name === "AbortError")
      )
        return null;
      return mapSSEError(error);
    },
    onSuccess: (content) => {
      if (content) {
        setMessages((prev) => [...prev, { id: createMessageId(), role: "assistant", content }]);
      }
      accumulatedRef.current = "";
      setError(null);
    },
    onError: (errResponse) => {
      const partial = accumulatedRef.current;
      if (partial) {
        setMessages((prev) => [
          ...prev,
          { id: createMessageId(), role: "assistant", content: partial },
        ]);
      }
      accumulatedRef.current = "";
      setError(errResponse);
    },
    connectionLossTimeout: 15_000,
  });

  const sendMessage = useCallback(
    async (text: string): Promise<void> => {
      const trimmed = text.trim();
      if (!trimmed || aiOp.isLoading || aiOp.isStreaming) return;
      setError(null);
      setMessages((prev) => [...prev, { id: createMessageId(), role: "user", content: trimmed }]);
      messageRef.current = trimmed;
      aiOp.start();
    },
    [aiOp],
  );

  const clearConversation = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setError(null);
    aiOp.cancel();
    accumulatedRef.current = "";
    messageRef.current = "";
  }, [aiOp]);

  const cancelStream = useCallback(() => {
    aiOp.cancel();
    accumulatedRef.current = "";
  }, [aiOp]);

  return {
    messages,
    isStreaming: aiOp.isLoading || aiOp.isStreaming,
    conversationId,
    error,
    isError: aiOp.isError,
    sendMessage,
    clearConversation,
    cancelStream,
    retry: aiOp.retry,
    chatEndRef,
  };
}
