"use client";

/**
 * ChatInputArea — Input controls for ChatPanel.
 *
 * Extracted from ChatPanel for RULE-04 file size compliance.
 * Handles the text input, send/cancel buttons, and clear conversation action.
 */

import { Send, Trash2, X } from "lucide-react";
import { useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

interface ChatInputAreaProps {
  readonly inputRef: React.RefObject<HTMLInputElement | null>;
  readonly input: string;
  readonly onInputChange: (value: string) => void;
  readonly onKeyDown: (e: React.KeyboardEvent) => void;
  readonly isStreaming: boolean;
  readonly onSend: () => void;
  readonly onCancelStream: () => void;
  readonly onClearConversation: () => void;
  readonly hasMessages: boolean;
  readonly t: (key: string) => string;
}

export function ChatInputArea({
  inputRef,
  input,
  onInputChange,
  onKeyDown,
  isStreaming,
  onSend,
  onCancelStream,
  onClearConversation,
  hasMessages,
  t,
}: ChatInputAreaProps) {
  // Clearing the conversation is destructive — guard it with a confirmation
  // dialog so a stray click does not wipe the whole chat.
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);

  return (
    <>
      <div className="border-t border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t("chatPanel.inputPlaceholder")}
            disabled={isStreaming}
            className="flex-1 px-3 py-2 border border-border rounded-lg bg-background text-foreground text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20 disabled:opacity-50"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={onCancelStream}
              className="p-2 rounded-lg bg-destructive text-destructive-foreground hover:opacity-90 transition-opacity"
              aria-label={t("sessionPanel.close")}
            >
              <X className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onSend}
              disabled={!input.trim()}
              className="p-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label={t("chatPanel.send")}
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1.5 text-center">
          {t("chatPanel.sendHint")}
        </p>
      </div>

      {hasMessages && (
        <div className="border-t border-border px-4 py-2 flex justify-center">
          <button
            type="button"
            onClick={() => setClearConfirmOpen(true)}
            disabled={isStreaming}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
          >
            <Trash2 className="w-3 h-3" />
            <span>{t("chatPanel.clearConversation")}</span>
          </button>
        </div>
      )}

      <ConfirmDialog
        open={clearConfirmOpen}
        onOpenChange={setClearConfirmOpen}
        title={t("chatPanel.clearConversation")}
        description={t("chatPanel.clearConversationConfirm")}
        confirmLabel={t("chatPanel.clearConversation")}
        variant="destructive"
        onConfirm={() => {
          onClearConversation();
          setClearConfirmOpen(false);
        }}
      />
    </>
  );
}
