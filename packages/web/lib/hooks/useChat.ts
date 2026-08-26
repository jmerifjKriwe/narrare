"use client";

/**
 * React hook for the free-form chat (ChatPanel) — §16 AI-Interaction Standards.
 *
 * Public contract only: the streaming conversation state machine (transcript
 * state, SSE turn wiring via useAIOperation, sendMessage / clearConversation /
 * cancelStream) lives in the private useChatStream module, extracted for
 * RULE-04 file-size headroom. This hook composes it with the one UI concern
 * that belongs to the consumer-facing API — the autoscroll chatEndRef — and
 * shapes the UseChatReturn contract.
 *
 * @module useChat
 */

import { useEffect, useRef } from "react";
import { useChatStream } from "@/lib/hooks/useChatStream";
import type { UseChatReturn } from "@/types/chat";

/**
 * @param projectId - Project (novel) scope, or null for project-less chat
 *   (NOTES-001 global notes).
 * @param noteId - Optional scratchpad note attached as runtime context
 *   (NOTES-001 §6b).
 */
export function useChat(projectId: string | null, noteId?: string | null): UseChatReturn {
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const stream = useChatStream(projectId, noteId);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  return { ...stream, chatEndRef };
}
