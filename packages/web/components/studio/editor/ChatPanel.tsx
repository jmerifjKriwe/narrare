"use client";

/**
 * ChatPanel — ChatGPT-style free-form chat sidebar (right panel).
 *
 * Uses SSE streaming (POST /api/v1/chat) for Q&A-style writing craft
 * conversations. Simpler than SessionPanel: no prose/draft features,
 * no "add to chapter" — just send message, receive response.
 *
 * Reuses the existing ChatMessage component for rendering.
 * Auto-manages conversation_id (creates on first message, reuses).
 * Supports AbortController for cancel-in-flight.
 */

import { Bot, Loader2, MessageSquare, Send, Trash2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import { useChat } from "@/lib/hooks/useChat";
import { ChatMessage } from "./ChatMessage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  readonly projectId: string;
  readonly onClose: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChatPanel({ projectId, onClose }: ChatPanelProps) {
  const t = useTranslations("studio");
  const { messages, isStreaming, error, sendMessage, clearConversation, cancelStream, chatEndRef } =
    useChat(projectId);

  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // -------------------------------------------------------------------------
  // Stable i18n strings for memoized child
  // -------------------------------------------------------------------------

  const aiDraftBadge = t("sessionPanel.aiDraftBadge");
  const addToDraftLabel = t("sessionPanel.addToDraft");
  const addedToDraftLabel = t("sessionPanel.addedToDraft");

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isStreaming) return;
    void sendMessage(text);
    setInput("");
  }, [input, isStreaming, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full border-l border-border bg-card w-80">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <MessageSquare className="w-4 h-4 text-primary" />
          <span>{t("chatPanel.title")}</span>
          <span
            className={`w-2 h-2 rounded-full ${isStreaming ? "bg-green-500" : "bg-muted-foreground/40"}`}
            title={isStreaming ? t("chatPanel.connected") : t("chatPanel.disconnected")}
          />
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded-md hover:bg-accent transition-colors"
          aria-label={t("sessionPanel.close")}
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
        {/* Empty state */}
        {messages.length === 0 && !isStreaming && (
          <div className="flex flex-col items-center justify-center flex-1 text-center text-muted-foreground gap-2">
            <MessageSquare className="w-8 h-8 opacity-40" />
            <p className="text-sm">{t("chatPanel.newConversation")}</p>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            isAdded={false}
            onAddToDraft={() => {}}
            aiDraftBadge={aiDraftBadge}
            addToDraftLabel={addToDraftLabel}
            addedToDraftLabel={addedToDraftLabel}
          />
        ))}

        {/* Streaming indicator */}
        {isStreaming && (
          <div className="flex justify-start">
            <div className="flex items-start gap-2">
              <Bot className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
              <div className="px-3 py-2 rounded-lg bg-muted text-sm text-foreground">
                <Loader2 className="inline w-4 h-4 animate-spin text-muted-foreground" />
                <span className="ml-2 text-xs text-muted-foreground">
                  {t("chatPanel.streaming")}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="flex justify-center">
            <span className="px-3 py-1 rounded-full bg-destructive/10 text-xs text-destructive">
              {t("chatPanel.errorConnecting")}
            </span>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("chatPanel.inputPlaceholder")}
            disabled={isStreaming}
            className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20 disabled:opacity-50"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={cancelStream}
              className="p-2 rounded-lg bg-destructive text-destructive-foreground hover:opacity-90 transition-opacity"
              aria-label={t("sessionPanel.close")}
            >
              <X className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label={t("chatPanel.send")}
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Bottom action bar */}
      {messages.length > 0 && (
        <div className="border-t border-border px-4 py-2 flex justify-center">
          <button
            type="button"
            onClick={clearConversation}
            disabled={isStreaming}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
          >
            <Trash2 className="w-3 h-3" />
            <span>{t("chatPanel.clearConversation")}</span>
          </button>
        </div>
      )}
    </div>
  );
}
