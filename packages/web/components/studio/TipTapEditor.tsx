"use client";

import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import StarterKit from "@tiptap/starter-kit";
import { Check, Loader2, Plus, RotateCcw, Sparkles, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type RewriteAlternative,
  type RewriteConfig,
  streamRewrite,
  writingApi,
} from "@/lib/api/generation";
import { createSseSuggestionFetcher } from "@/lib/api/suggest";
import { useRecordFeedback } from "@/lib/hooks/useMemory";
import { useEditorStore } from "@/lib/stores/editorStore";
import { markdownToHtml } from "@/lib/utils";
import type { FeedbackRequest } from "@/types";
import { BlockControls } from "./BlockControls";
import { AIAnnotationActions } from "./editor/AIAnnotationActions";
import {
  AIAnnotationExtension,
  AIAnnotationMark,
  insertAIContentAt,
  replaceSelectionWithAIContent,
} from "./editor/extensions/AIAnnotation";
import { Autosave } from "./editor/extensions/Autosave";
import { DialogueMark } from "./editor/extensions/DialogueMark";
import { GhostText, simulateSuggestion } from "./editor/extensions/GhostText";
import { NarrareDocument } from "./editor/extensions/NarrareDocument";
import { SceneBreak } from "./editor/extensions/SceneBreak";
import { GhostTextOnboarding, useGhostTextOnboarding } from "./editor/GhostTextOnboarding";
import { InlineDiff } from "./editor/InlineDiff";
import { RewriteModeSelector } from "./editor/RewriteModeSelector";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TipTapEditorProps {
  content: string;
  onChange: (content: string) => void;
  onAutosave?: (content: string) => Promise<void>;
  autosaveInterval?: number;
  /** Chapter ID for backend suggestion API calls */
  chapterId?: string;
  /** Novel/project ID for feedback recording */
  novelId?: string;
}

interface AISuggestion {
  original: string;
  suggestions: string[];
  labels: string[];
  position: { from: number; to: number };
}

/** Rewrite phase state machine. */
type RewritePhase = "idle" | "selecting-mode" | "streaming" | "showing-alternatives";

// Minimum/maximum selection length for rewrite (characters)
const MIN_SELECTION_LENGTH = 50;
const MAX_SELECTION_LENGTH = 2000;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TipTapEditor({
  content,
  onChange,
  onAutosave,
  autosaveInterval,
  chapterId,
  novelId,
}: TipTapEditorProps) {
  const t = useTranslations("studio");
  const locale = useLocale();

  // AI suggestion modal state
  const [aiSuggestion, setAiSuggestion] = useState<AISuggestion | null>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectionInput, setShowRejectionInput] = useState(false);

  // Rewrite flow state
  const [rewritePhase, setRewritePhase] = useState<RewritePhase>("idle");
  const [rewriteSelection, setRewriteSelection] = useState<{
    text: string;
    from: number;
    to: number;
    contextBefore: string;
    contextAfter: string;
  } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Ghost Text onboarding — show once on first ghost text appearance
  const { shouldShow: showOnboarding, dismiss: dismissOnboarding } = useGhostTextOnboarding();
  const [onboardingAnchor, setOnboardingAnchor] = useState<HTMLElement | null>(null);

  // Feedback hook for implicit accept on autosave
  const recordFeedback = useRecordFeedback(novelId ?? "");

  // Ref always holds the current saveFn — avoids stale closure in Autosave extension
  const saveFnRef = useRef(onAutosave ?? (async () => {}));

  useEffect(() => {
    saveFnRef.current = onAutosave ?? (async () => {});
  }, [onAutosave]);

  // Stable config: reads from refs at call time
  // eslint-disable-next-line react-hooks/exhaustive-deps
  // biome-ignore lint/correctness/useExhaustiveDependencies: ref-based pattern — onAutosave changes are synced via saveFnRef, not via useMemo recomputation
  const autosaveConfig = useMemo(
    () => ({
      interval: autosaveInterval ?? 30_000,
      saveFn: (content: string) => saveFnRef.current(content),
      enabled: !!onAutosave,
      onImplicitAccept: novelId
        ? (data: {
            requestId: string;
            source: string;
            originalText: string;
            action: "accept" | "modify";
            currentText?: string;
          }) => {
            const feedbackData: FeedbackRequest = {
              action: data.action,
              suggestion_id: data.requestId,
              intent: data.source,
              suggestion_text: data.originalText,
              modification: data.currentText ?? null,
              project_id: novelId,
              chapter_id: chapterId ?? null,
              mode: data.source,
            };
            recordFeedback.mutate(feedbackData, {
              onError: () => {
                /* Non-blocking */
              },
            });

            writingApi.acceptDraft(data.requestId, data.currentText).catch(() => {
              /* Non-blocking */
            });
          }
        : undefined,
    }),
    [autosaveInterval, novelId, chapterId, recordFeedback],
  );

  // ── GhostText fetchSuggestion ref ──
  const fetchSuggestionRef = useRef<
    | ((params: { textBefore: string; textAfter: string; signal: AbortSignal }) => Promise<string>)
    | undefined
  >(undefined);

  useEffect(() => {
    fetchSuggestionRef.current = chapterId
      ? createSseSuggestionFetcher(chapterId, locale)
      : undefined;
  }, [chapterId, locale]);

  // Stable config object
  const ghostTextConfig = useMemo(
    () =>
      ({
        fetchSuggestion: (params: {
          textBefore: string;
          textAfter: string;
          signal: AbortSignal;
        }) => {
          return fetchSuggestionRef.current?.(params) ?? simulateSuggestion(params);
        },
        enabled: true,
        minChars: 5,
        suggestionDelay: 800,
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }) satisfies Partial<import("./editor/extensions/GhostText").GhostTextOptions>,
    [],
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
      AIAnnotationMark,
      AIAnnotationExtension,
      Autosave.configure(autosaveConfig),
      GhostText.configure(ghostTextConfig),
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
      const htmlContent = content.trim().startsWith("<") ? content : markdownToHtml(content);
      editor.commands.setContent(htmlContent);
    }
  }, [content, editor]);

  // Sync editor instance to global store
  useEffect(() => {
    if (editor) {
      useEditorStore.getState().setEditor(editor);
      if (typeof window !== "undefined") {
        (window as unknown as Window & { __narrareEditor: unknown }).__narrareEditor = editor;
      }
    }
  }, [editor]);

  // Ghost Text onboarding: detect first ghost text element and show hint
  useEffect(() => {
    if (!showOnboarding || !editor) return;

    const checkForGhostText = () => {
      const ghostEl = document.querySelector(".ghost-text-suggestion");
      if (ghostEl && showOnboarding) {
        setOnboardingAnchor(ghostEl as HTMLElement);
      }
    };

    // Observe editor DOM for ghost text decorations
    const observer = new MutationObserver(checkForGhostText);
    const editorDom = editor.view.dom;
    observer.observe(editorDom, { childList: true, subtree: true });

    // Also check on editor updates
    const handler = () => {
      setTimeout(checkForGhostText, 50);
    };
    editor.on("update", handler);
    editor.on("transaction", handler);

    return () => {
      observer.disconnect();
      editor.off("update", handler);
      editor.off("transaction", handler);
    };
  }, [editor, showOnboarding]);

  /** Get context around a selection (200 tokens ~= ~800 chars on each side). */
  const getSelectionContext = useCallback(
    (from: number, to: number) => {
      if (!editor) return { contextBefore: "", contextAfter: "" };
      const contextRadius = 800;
      const contextBefore = editor.state.doc.textBetween(
        Math.max(0, from - contextRadius),
        from,
        " ",
      );
      const contextAfter = editor.state.doc.textBetween(
        to,
        Math.min(editor.state.doc.content.size, to + contextRadius),
        " ",
      );
      return { contextBefore, contextAfter };
    },
    [editor],
  );

  /** Step 1: User clicks "AI Rewrite" in BubbleMenu → show mode selector. */
  const handleAIRewrite = useCallback(() => {
    if (!editor) return;

    const { from, to } = editor.state.selection;
    const selectedText = editor.state.doc.textBetween(from, to, " ");
    const trimmedLength = selectedText.trim().length;

    if (trimmedLength < MIN_SELECTION_LENGTH || trimmedLength > MAX_SELECTION_LENGTH) {
      return;
    }

    const { contextBefore, contextAfter } = getSelectionContext(from, to);

    setRewriteSelection({
      text: selectedText,
      from,
      to,
      contextBefore,
      contextAfter,
    });
    setRewritePhase("selecting-mode");
  }, [editor, getSelectionContext]);

  /** Step 2: User selects mode + options → start streaming. */
  const handleRewriteGenerate = useCallback(
    (config: RewriteConfig) => {
      if (!editor || !rewriteSelection || !chapterId || !novelId) return;

      setRewritePhase("streaming");
      const controller = new AbortController();
      abortRef.current = controller;

      const alternatives: RewriteAlternative[] = [];

      streamRewrite(
        chapterId,
        novelId,
        {
          selection_text: rewriteSelection.text,
          context_before: rewriteSelection.contextBefore,
          context_after: rewriteSelection.contextAfter,
          mode: config.mode,
          options: config.mode !== "custom" ? { option: config.option } : undefined,
          count: config.count,
          custom_instructions: config.customInstructions,
          language: locale,
        },
        {
          onRequestInfo: () => {
            // Request ID received
          },
          onAlternative: (label, text) => {
            alternatives.push({ label, text });
            // Show modal after first alternative arrives
            if (alternatives.length === 1) {
              setAiSuggestion({
                original: rewriteSelection.text,
                suggestions: alternatives.map((a) => a.text),
                labels: alternatives.map((a) => a.label),
                position: { from: rewriteSelection.from, to: rewriteSelection.to },
              });
              setSelectedSuggestion(0);
            } else {
              // Update with additional alternatives
              setAiSuggestion((prev) =>
                prev
                  ? {
                      ...prev,
                      suggestions: alternatives.map((a) => a.text),
                      labels: alternatives.map((a) => a.label),
                    }
                  : prev,
              );
            }
            setRewritePhase("showing-alternatives");
          },
          onAlternativeFinal: () => {
            abortRef.current = null;
          },
          onError: () => {
            setRewritePhase("idle");
            abortRef.current = null;
          },
        },
        controller.signal,
      );
    },
    [editor, rewriteSelection, chapterId, novelId, locale],
  );

  const handleRewriteCancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setRewritePhase("idle");
    setRewriteSelection(null);
  }, []);

  // ---------------------------------------------------------------------------
  // Accept/Reject actions for modal
  // ---------------------------------------------------------------------------

  /** Replace the original selection with the selected alternative (Rewrite: Replace). */
  const acceptSuggestion = useCallback(() => {
    if (!editor || !aiSuggestion) return;

    const selectedText = aiSuggestion.suggestions[selectedSuggestion];
    const rid = `rewrite-${Date.now()}`;

    replaceSelectionWithAIContent(
      editor,
      rid,
      "rewrite",
      selectedText,
      aiSuggestion.position.from,
      aiSuggestion.position.to,
    );

    setAiSuggestion(null);
    setRewritePhase("idle");
    setRewriteSelection(null);
    setShowRejectionInput(false);
    setRejectionReason("");
  }, [editor, aiSuggestion, selectedSuggestion]);

  /** Insert the selected alternative after the original selection (Insert as new). */
  const insertAsNew = useCallback(() => {
    if (!editor || !aiSuggestion) return;

    const selectedText = aiSuggestion.suggestions[selectedSuggestion];
    const requestId = `rewrite-${Date.now()}`;

    insertAIContentAt(editor, requestId, "rewrite", selectedText, aiSuggestion.position.to);

    setAiSuggestion(null);
    setRewritePhase("idle");
    setRewriteSelection(null);
    setShowRejectionInput(false);
    setRejectionReason("");
  }, [editor, aiSuggestion, selectedSuggestion]);

  const rejectSuggestion = useCallback(() => {
    if (rejectionReason.trim()) {
      setAiSuggestion(null);
      setShowRejectionInput(false);
      setRejectionReason("");
      setRewritePhase("idle");
      setRewriteSelection(null);
    } else {
      setShowRejectionInput(true);
    }
  }, [rejectionReason]);

  // ---------------------------------------------------------------------------
  // Selection validation for BubbleMenu rewrite button
  // ---------------------------------------------------------------------------

  const getSelectionLength = useCallback(() => {
    if (!editor) return 0;
    const { from, to } = editor.state.selection;
    if (from === to) return 0;
    return editor.state.doc.textBetween(from, to, " ").trim().length;
  }, [editor]);

  const selectionLength = getSelectionLength();
  const isRewriteEnabled =
    selectionLength >= MIN_SELECTION_LENGTH && selectionLength <= MAX_SELECTION_LENGTH;

  if (!editor) {
    return null;
  }

  const isRewriteStreaming = rewritePhase === "streaming";

  return (
    <div className="relative flex-1">
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
            disabled={!isRewriteEnabled}
            title={
              !isRewriteEnabled && selectionLength > 0
                ? selectionLength < MIN_SELECTION_LENGTH
                  ? t("rewrite.selectionTooShort", { min: MIN_SELECTION_LENGTH })
                  : t("rewrite.selectionTooLong", { max: MAX_SELECTION_LENGTH })
                : undefined
            }
            className={`px-3 py-2 hover:bg-accent transition-colors flex items-center gap-1.5 text-sm text-primary ${
              !isRewriteEnabled ? "opacity-40 cursor-not-allowed" : ""
            }`}
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

      <EditorContent editor={editor} className="h-full" />
      <BlockControls editor={editor} />

      {/* AI Annotation floating actions */}
      {editor && novelId && (
        <AIAnnotationActions editor={editor} projectId={novelId} chapterId={chapterId} />
      )}

      {/* Ghost Text onboarding hint — shown once */}
      {showOnboarding && onboardingAnchor && (
        <GhostTextOnboarding anchorElement={onboardingAnchor} onDismiss={dismissOnboarding} />
      )}

      {/* Rewrite Mode Selector (shown before streaming starts) */}
      {rewritePhase === "selecting-mode" && rewriteSelection && (
        <RewriteModeSelector
          selectionLength={rewriteSelection.text.trim().length}
          onGenerate={handleRewriteGenerate}
          onCancel={handleRewriteCancel}
        />
      )}

      {/* AI Suggestion Modal (reused for rewrite alternatives) */}
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

            {/* Suggestion list with inline diffs */}
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
                    {/* Label header */}
                    {aiSuggestion.labels[index] && (
                      <p className="text-xs font-medium text-muted-foreground mb-2">
                        {aiSuggestion.labels[index]}
                      </p>
                    )}
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <InlineDiff original={aiSuggestion.original} alternative={suggestion} />
                      </div>
                      {selectedSuggestion === index && (
                        <Check className="w-5 h-5 text-primary flex-shrink-0" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
              {isRewriteStreaming && (
                <div className="flex items-center gap-2 mt-4 text-sm text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{t("aiActions.generating")}</span>
                </div>
              )}
            </div>

            {/* Rejection reason input */}
            {showRejectionInput && (
              <div className="p-6 border-t border-border bg-muted/30">
                <label htmlFor="rejection-reason" className="block text-sm mb-2">
                  {t("aiActions.rejectReason")}
                </label>
                <textarea
                  id="rejection-reason"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-lg text-sm"
                  rows={3}
                  placeholder={t("aiActions.rejectReasonPlaceholder")}
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
                {t("aiActions.reject")}
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={insertAsNew}
                  className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-accent transition-colors"
                  title={t("aiActions.insertAsNew")}
                >
                  <Plus className="w-4 h-4" />
                  {t("aiActions.insertAsNew")}
                </button>
                <button
                  type="button"
                  onClick={handleAIRewrite}
                  className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-accent transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  {t("aiActions.newSuggestions")}
                </button>
                <button
                  type="button"
                  onClick={acceptSuggestion}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
                >
                  <Check className="w-4 h-4" />
                  {t("aiActions.replace")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
