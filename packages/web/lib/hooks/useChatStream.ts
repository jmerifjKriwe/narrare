"use client";

/**
 * useChatStream — private stream-engine extraction from useChat (RULE-04:
 * useChat was at the 150-line hook limit). Owns the streaming conversation
 * state machine: transcript state (messages, conversationId, error), the
 * SSE turn wiring via useAIOperation (transport delegated to
 * chat-stream-bridge, mirroring consistency-stream-bridge), and the turn
 * actions (sendMessage, clearConversation, cancelStream). useChat composes
 * this hook plus the autoscroll chatEndRef; the unchanged useChat tests
 * cover the seam through useChat. NOT public API — import useChat instead.
 *
 * @module useChatStream
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import { bridgeChatStream } from "@/lib/hooks/chat-stream-bridge";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation.types";
import { type ChatMessage, createMessageId, type UseChatReturn } from "@/types/chat";

/**
 * The stream-engine slice of the public contract (@/types/chat): everything
 * useChat returns except the UI-plumbing chatEndRef it adds itself.
 */
export type UseChatStreamReturn = Omit<UseChatReturn, "chatEndRef">;

/**
 * @param projectId - Project (novel) scope, or null for project-less chat.
 * @param noteId - Optional note context, read via an effect-synced ref so a
 *   stale execute closure can never silently re-scope a turn.
 */
export function useChatStream(
  projectId: string | null,
  noteId?: string | null,
): UseChatStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<AIErrorResponse | null>(null);

  const messageRef = useRef("");
  const accumulatedRef = useRef("");

  const conversationIdRef = useRef(conversationId);
  conversationIdRef.current = conversationId;

  // P-FE4: effect-synced ref read in execute — always the last committed noteId.
  const noteIdRef = useRef(noteId ?? null);
  useEffect(() => {
    noteIdRef.current = noteId ?? null;
  }, [noteId]);

  const aiOp = useAIOperation<string | null>({
    execute: async (signal) => {
      const msg = messageRef.current;
      if (!msg) return null;
      accumulatedRef.current = "";
      const content = await bridgeChatStream({
        body: {
          project_id: projectId,
          message: msg,
          conversation_id: conversationIdRef.current,
          note_id: noteIdRef.current,
        },
        signal,
        onConversationId: setConversationId,
        onToken: (accumulated) => {
          accumulatedRef.current = accumulated;
        },
        notifyData: () => aiOp.notifyData(),
      });
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
  };
}
