"use client";

/**
 * SessionPanel — Writing session with AI co-author.
 *
 * WebSocket-based real-time session with streaming AI responses.
 * Interview mode shows local greetings and supports draft generation.
 * §16 compliance: Stop Generation aborts current stream only (not session).
 */

import { Bot, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuthStore } from "@/lib/stores/authStore";
import type { Message } from "./ChatMessage";
import { ChatMessage } from "./ChatMessage";
import { SessionActions } from "./SessionActions";
import { SessionHeader } from "./SessionHeader";
import { useSessionSocket } from "./useSessionSocket";

interface SessionPanelProps {
  readonly chapterId: string;
  readonly novelId: string;
  readonly mode: "interactive_session" | "interview_assisted";
  readonly onClose: () => void;
}

export function SessionPanel({ chapterId, novelId, mode, onClose }: SessionPanelProps) {
  const t = useTranslations("studio");
  const currentUser = useAuthStore((s) => s.user);
  const [input, setInput] = useState("");
  const [proseBuffer, setProseBuffer] = useState("");
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set());
  const chatEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    setMessages,
    streamingText,
    streamingTextRef,
    isConnected,
    isStreaming,
    setIsStreaming,
    setStreamingText,
    saveNotification,
    sendMessage,
    closeSocket,
  } = useSessionSocket({
    chapterId,
    novelId,
    mode,
    userId: currentUser?.id,
    sessionEndedLabel: t("sessionPanel.sessionEnded"),
    errorConnectingLabel: t("sessionPanel.errorConnecting"),
    savedLabel: t("sessionPanel.saved"),
  });

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Interview greetings
  const greetings: string[] = t.raw("sessionPanel.interviewGreetings");
  const greetingIndex = useMemo(
    () => Math.floor(Math.random() * greetings.length),
    [greetings.length],
  );
  useEffect(() => {
    if (mode === "interview_assisted" && messages.length === 0 && greetings.length > 0) {
      setMessages([
        { id: `greeting-${greetingIndex}`, role: "assistant", content: greetings[greetingIndex] },
      ]);
    }
  }, [mode, greetings, greetingIndex, messages.length, setMessages]);

  // --- Actions ---

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text) return;
    setMessages((prev: Message[]) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", content: text },
    ]);
    sendMessage("user_direction", text);
    setInput("");
  }, [input, sendMessage, setMessages]);

  const handleAddToDraft = useCallback((msgId: string, prose: string) => {
    setAddedIds((prev) => new Set(prev).add(msgId));
    setProseBuffer((prev) => (prev ? `${prev}\n\n${prose}` : prose));
  }, []);

  const handleSaveToChapter = useCallback(() => {
    if (!proseBuffer) return;
    sendMessage("save_to_chapter", proseBuffer);
  }, [proseBuffer, sendMessage]);

  const handleGenerateDraft = useCallback(() => {
    sendMessage("generate_draft");
  }, [sendMessage]);

  /** Stop Generation — aborts only current AI stream, session stays active. */
  const handleStopGeneration = useCallback(() => {
    const prose = streamingTextRef.current;
    streamingTextRef.current = "";
    setStreamingText("");
    setIsStreaming(false);
    if (prose) {
      setMessages((prev: Message[]) => [
        ...prev,
        { id: `stop-${Date.now()}`, role: "assistant", content: "", prose },
      ]);
    }
  }, [streamingTextRef, setStreamingText, setIsStreaming, setMessages]);

  const handleEndSession = useCallback(() => {
    closeSocket();
    onClose();
  }, [closeSocket, onClose]);

  const hasAddedAny = useMemo(() => addedIds.size > 0, [addedIds]);
  const aiDraftBadge = t("sessionPanel.aiDraftBadge");
  const addToDraftLabel = t("aiActions.addToDraft");
  const addedToDraftLabel = t("sessionPanel.addedToDraft");

  return (
    <div className="flex flex-col h-full border-l border-border bg-card w-80">
      <SessionHeader
        title={
          mode === "interview_assisted" ? t("sessionPanel.interviewTitle") : t("sessionPanel.title")
        }
        isConnected={isConnected}
        connectedLabel={t("sessionPanel.connected")}
        disconnectedLabel={t("sessionPanel.disconnected")}
        closeLabel={t("sessionPanel.close")}
        onClose={handleEndSession}
      />
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            isAdded={addedIds.has(msg.id)}
            onAddToDraft={(prose) => handleAddToDraft(msg.id, prose)}
            aiDraftBadge={aiDraftBadge}
            addToDraftLabel={addToDraftLabel}
            addedToDraftLabel={addedToDraftLabel}
          />
        ))}
        {isStreaming && streamingText && (
          <div className="flex justify-start">
            <div className="max-w-[85%] flex items-start gap-2">
              <Bot className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
              <div className="px-3 py-2 rounded-lg bg-muted text-sm text-foreground whitespace-pre-wrap">
                {streamingText}
                <Loader2 className="inline w-3 h-3 ml-1 animate-spin text-muted-foreground" />
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>
      {saveNotification && (
        <div className="mx-4 mb-2 px-3 py-2 rounded-lg bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs font-medium text-center">
          {saveNotification}
        </div>
      )}
      <SessionActions
        mode={mode}
        isConnected={isConnected}
        isStreaming={isStreaming}
        hasAddedAny={hasAddedAny}
        messageCount={messages.length}
        input={input}
        onInputChange={setInput}
        onSend={handleSend}
        onStopGeneration={handleStopGeneration}
        onGenerateDraft={handleGenerateDraft}
        onSaveToChapter={handleSaveToChapter}
        onEndSession={handleEndSession}
      />
    </div>
  );
}
