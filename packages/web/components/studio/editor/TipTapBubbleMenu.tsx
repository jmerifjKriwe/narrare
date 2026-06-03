"use client";

import type { Editor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import { Loader2, Sparkles } from "lucide-react";
import type { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";
import { MAX_SELECTION_LENGTH, MIN_SELECTION_LENGTH } from "./TipTapEditorController";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface TipTapBubbleMenuProps {
  editor: Editor;
  isRewriteEnabled: boolean;
  isRewriteStreaming: boolean;
  selectionLength: number;
  onAIRewrite: () => void;
  t: StudioTranslator;
}

export function TipTapBubbleMenu({
  editor,
  isRewriteEnabled,
  isRewriteStreaming,
  selectionLength,
  onAIRewrite,
  t,
}: TipTapBubbleMenuProps) {
  return (
    <BubbleMenu
      editor={editor}
      className="bubble-menu bg-popover border border-border rounded-lg shadow-lg overflow-hidden"
      shouldShow={({ state }) => {
        if (useEditorStore.getState().isDragging) return false;
        const { from, to } = state.selection;
        return from !== to;
      }}
    >
      <div className="flex items-center divide-x divide-border">
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBold().run()}
          className={`px-3 py-2 hover:bg-accent transition-colors text-sm ${editor.isActive("bold") ? "bg-accent font-bold" : ""}`}
        >
          {t("bubble.bold")}
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleItalic().run()}
          className={`px-3 py-2 hover:bg-accent transition-colors text-sm ${editor.isActive("italic") ? "bg-accent italic" : ""}`}
        >
          {t("bubble.italic")}
        </button>
        <button
          type="button"
          onClick={onAIRewrite}
          disabled={!isRewriteEnabled}
          title={getRewriteTitle({ isRewriteEnabled, selectionLength, t })}
          className={`px-3 py-2 hover:bg-accent transition-colors flex items-center gap-1.5 text-sm text-primary ${!isRewriteEnabled ? "opacity-40 cursor-not-allowed" : ""}`}
        >
          {isRewriteStreaming ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Sparkles className="w-3.5 h-3.5" />
          )}
          <span>{t("bubble.aiRewrite")}</span>
        </button>
      </div>
    </BubbleMenu>
  );
}

function getRewriteTitle({
  isRewriteEnabled,
  selectionLength,
  t,
}: Pick<TipTapBubbleMenuProps, "isRewriteEnabled" | "selectionLength" | "t">): string | undefined {
  if (isRewriteEnabled || selectionLength === 0) return undefined;
  return selectionLength < MIN_SELECTION_LENGTH
    ? t("rewrite.selectionTooShort", { min: MIN_SELECTION_LENGTH })
    : t("rewrite.selectionTooLong", { max: MAX_SELECTION_LENGTH });
}
