"use client";

import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import StarterKit from "@tiptap/starter-kit";
import { Check, RotateCcw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useEditorStore } from "@/lib/stores/editorStore";
import { markdownToHtml } from "@/lib/utils";
import { BlockControls } from "./BlockControls";
import { Autosave } from "./editor/extensions/Autosave";
import { DialogueMark } from "./editor/extensions/DialogueMark";
import { NarrareDocument } from "./editor/extensions/NarrareDocument";
import { SceneBreak } from "./editor/extensions/SceneBreak";

interface TipTapEditorProps {
  content: string;
  onChange: (content: string) => void;
  onAutosave?: (content: string) => Promise<void>;
  autosaveInterval?: number;
}

interface AISuggestion {
  original: string;
  suggestions: string[];
  position: { from: number; to: number };
}

export function TipTapEditor({
  content,
  onChange,
  onAutosave,
  autosaveInterval,
}: TipTapEditorProps) {
  const t = useTranslations("studio");
  const [aiSuggestion, setAiSuggestion] = useState<AISuggestion | null>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectionInput, setShowRejectionInput] = useState(false);

  // Ref always holds the current saveFn — avoids stale closure in Autosave extension
  // (useEditor freezes extensions at mount time, so a direct closure would never update)
  const saveFnRef = useRef(onAutosave ?? (async () => {}));

  // Keep the ref synced whenever onAutosave changes
  useEffect(() => {
    saveFnRef.current = onAutosave ?? (async () => {});
  }, [onAutosave]);

  // Stable config: the wrapper reads from the ref at call time, not closure capture time
  // eslint-disable-next-line react-hooks/exhaustive-deps
  // biome-ignore lint/correctness/useExhaustiveDependencies: ref-based pattern — onAutosave changes are synced via saveFnRef, not via useMemo recomputation
  const autosaveConfig = useMemo(
    () => ({
      interval: autosaveInterval ?? 30_000,
      saveFn: (content: string) => saveFnRef.current(content),
      enabled: !!onAutosave,
    }),
    [autosaveInterval],
  );

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        document: false,
        heading: {
          levels: [1, 2, 3],
        },
      }),
      NarrareDocument,
      SceneBreak,
      DialogueMark,
      Autosave.configure(autosaveConfig),
      Placeholder.configure({
        placeholder: t("editor.placeholder"),
      }),
    ],
    content,
    onUpdate: ({ editor: ed }) => {
      onChange(ed.getHTML());
    },
    editorProps: {
      attributes: {
        class: "max-w-none focus:outline-none min-h-[70vh] py-6 pr-8",
      },
    },
  });

  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      // Safety-net: ensure content is HTML before passing to TipTap
      const htmlContent = content.trim().startsWith("<") ? content : markdownToHtml(content);
      editor.commands.setContent(htmlContent);
    }
  }, [content, editor]);

  // Sync editor instance to global store so EditorView toolbar can use it
  useEffect(() => {
    if (editor) {
      useEditorStore.getState().setEditor(editor);
      // Expose on window for E2E testing — TipTap doesn't attach EditorView
      // to the DOM element, so Playwright cannot access it via el.view
      if (typeof window !== "undefined") {
        (window as unknown as Window & { __narrareEditor: unknown }).__narrareEditor = editor;
      }
    }
  }, [editor]);

  const handleAIRewrite = useCallback(() => {
    if (!editor) return;

    const { from, to } = editor.state.selection;
    const selectedText = editor.state.doc.textBetween(from, to, " ");

    if (selectedText.trim()) {
      const mockSuggestions = [
        selectedText.split("").reverse().join(""),
        selectedText.toUpperCase(),
        `\u2728 ${selectedText} (\u00fcberarbeitet von KI)`,
      ];

      setAiSuggestion({
        original: selectedText,
        suggestions: mockSuggestions,
        position: { from, to },
      });
      setSelectedSuggestion(0);
    }
  }, [editor]);

  const acceptSuggestion = useCallback(() => {
    if (!editor || !aiSuggestion) return;

    editor.commands.setTextSelection(aiSuggestion.position);
    editor.commands.insertContent(aiSuggestion.suggestions[selectedSuggestion]);
    setAiSuggestion(null);
    setShowRejectionInput(false);
    setRejectionReason("");
  }, [editor, aiSuggestion, selectedSuggestion]);

  const rejectSuggestion = useCallback(() => {
    if (rejectionReason.trim()) {
      setAiSuggestion(null);
      setShowRejectionInput(false);
      setRejectionReason("");
    } else {
      setShowRejectionInput(true);
    }
  }, [rejectionReason]);

  if (!editor) {
    return null;
  }

  return (
    <div className="relative flex-1">
      <BubbleMenu
        editor={editor}
        className="bubble-menu bg-popover border border-border rounded-lg shadow-lg overflow-hidden"
        shouldShow={({ state }) => {
          // Don't show during drag operations
          if (useEditorStore.getState().isDragging) return false;
          // Only show when there's an actual text selection
          const { from, to } = state.selection;
          return from !== to;
        }}
      >
        <div className="flex items-center divide-x divide-border">
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={`px-3 py-2 hover:bg-accent transition-colors text-sm ${
              editor.isActive("bold") ? "bg-accent font-bold" : ""
            }`}
          >
            {t("bubble.bold")}
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={`px-3 py-2 hover:bg-accent transition-colors text-sm ${
              editor.isActive("italic") ? "bg-accent italic" : ""
            }`}
          >
            {t("bubble.italic")}
          </button>
          <button
            type="button"
            onClick={handleAIRewrite}
            className="px-3 py-2 hover:bg-accent transition-colors flex items-center gap-1.5 text-sm text-primary"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{t("bubble.aiRewrite")}</span>
          </button>
        </div>
      </BubbleMenu>

      <EditorContent editor={editor} className="h-full" />
      <BlockControls editor={editor} />

      {/* AI Suggestion Modal */}
      {aiSuggestion && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-card border border-border rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
            {/* Modal header */}
            <div className="p-6 border-b border-border">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-5 h-5 text-primary" />
                <h3 className="font-medium">{t("aiModal.title")}</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                {t("aiModal.original", { text: aiSuggestion.original })}
              </p>
            </div>

            {/* Suggestion list */}
            <div className="flex-1 overflow-y-auto p-6">
              <div className="space-y-3">
                {aiSuggestion.suggestions.map((suggestion, index) => (
                  <button
                    type="button"
                    key={`suggestion-${suggestion.slice(0, 32)}`}
                    onClick={() => setSelectedSuggestion(index)}
                    className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                      selectedSuggestion === index
                        ? "border-primary bg-accent"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="flex-1">{suggestion}</p>
                      {selectedSuggestion === index && (
                        <Check className="w-5 h-5 text-primary flex-shrink-0" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Rejection reason input */}
            {showRejectionInput && (
              <div className="p-6 border-t border-border bg-muted/30">
                <label htmlFor="rejection-reason" className="block text-sm mb-2">
                  {t("aiModal.rejectionLabel")}
                </label>
                <textarea
                  id="rejection-reason"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-lg text-sm"
                  rows={3}
                  placeholder={t("aiModal.rejectionPlaceholder")}
                />
              </div>
            )}

            {/* Modal footer */}
            <div className="p-6 border-t border-border flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={rejectSuggestion}
                className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-accent transition-colors"
              >
                <X className="w-4 h-4" />
                {t("aiModal.reject")}
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleAIRewrite}
                  className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-accent transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  {t("aiModal.newSuggestions")}
                </button>
                <button
                  type="button"
                  onClick={acceptSuggestion}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
                >
                  <Check className="w-4 h-4" />
                  {t("aiModal.accept")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
