"use client";

/**
 * SessionPanel — Writing session with AI co-author.
 *
 * WebSocket-based real-time session with streaming AI responses.
 * Interview mode shows local greetings and supports draft generation.
 * §16 compliance: Stop Generation aborts current stream only (not session).
 */

import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuthStore } from "@/lib/stores/authStore";
import { SaveNotification } from "./SaveNotification";
import { SessionActions } from "./SessionActions";
import { SessionHeader } from "./SessionHeader";
import { SessionMessageList } from "./SessionMessageList";
import { SessionReconnectBanner } from "./SessionReconnectBanner";
import { StreamingBubble } from "./StreamingBubble";
import { useSessionPanelActions } from "./useSessionPanelActions";
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
  const [preservedProse, setPreservedProse] = useState("");
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set());
  const chatEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    setMessages,
    streamingText,
    streamingTextRef,
    sessionIdRef,
    isConnected,
    isStreaming,
    setIsStreaming,
    setStreamingText,
    saveNotification,
    recoveryState,
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
    generationStoppedLabel: t("sessionPanel.generationStopped"),
    recoveryFailedLabel: t("sessionPanel.recoveryFailed"),
  });

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (recoveryState === "reconnecting" && streamingTextRef.current) {
      setPreservedProse(streamingTextRef.current);
    }
  }, [recoveryState, streamingTextRef]);

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

  const {
    handleAddToDraft,
    handleEndSession,
    handleGenerateDraft,
    handleRecoverSession,
    handleSaveToChapter,
    handleSend,
    handleStopGeneration,
  } = useSessionPanelActions({
    input,
    proseBuffer,
    sendMessage,
    closeSocket,
    onClose,
    setInput,
    setMessages,
    setAddedIds,
    setProseBuffer,
    setStreamingText,
    setIsStreaming,
    streamingTextRef,
    sessionIdRef,
    serverStopFailedLabel: t("sessionPanel.serverStopFailed"),
  });

  // Escape-Cancel Handler (KEYBOARD-001)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isStreaming) {
        e.preventDefault();
        handleStopGeneration();
      }
      if (e.key === "Escape" && !isStreaming) {
        e.preventDefault();
        handleEndSession();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isStreaming, handleStopGeneration, handleEndSession]);

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
        <SessionReconnectBanner
          recoveryState={recoveryState}
          reconnectingLabel={t("sessionPanel.reconnecting")}
          recoveredLabel={t("sessionPanel.recovered")}
          recoveryFailedLabel={t("sessionPanel.recoveryFailed")}
          connectionLostLabel={t("sessionPanel.connectionLost")}
          preserveLocalCopyLabel={t("sessionPanel.preserveLocalCopy")}
          retryLabel={t("aiActions.connectionLostRetry")}
          localProse={preservedProse}
          onRetry={handleRecoverSession}
        />
        <SessionMessageList
          messages={messages}
          addedIds={addedIds}
          onAddToDraft={handleAddToDraft}
          aiDraftBadge={aiDraftBadge}
          addToDraftLabel={addToDraftLabel}
          addedToDraftLabel={addedToDraftLabel}
        />
        {isStreaming && streamingText && <StreamingBubble streamingText={streamingText} />}
        <div ref={chatEndRef} />
      </div>
      {saveNotification && <SaveNotification message={saveNotification} />}
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
