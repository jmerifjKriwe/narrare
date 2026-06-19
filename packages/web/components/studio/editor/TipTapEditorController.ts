import Placeholder from "@tiptap/extension-placeholder";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import type { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { mapSSEError } from "@/lib/api/ai-error-mapping";
import {
  type RewriteAlternative,
  type RewriteConfig,
  streamRewrite,
  writingApi,
} from "@/lib/api/generation";
import { createSseSuggestionFetcher } from "@/lib/api/suggest";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { useAIOperation } from "@/lib/hooks/use-ai-operation";
import { useRecordFeedback } from "@/lib/hooks/useMemory";
import { useEditorStore } from "@/lib/stores/editorStore";
import { markdownToHtml } from "@/lib/utils";
import type { FeedbackRequest } from "@/types";
import {
  AIAnnotationExtension,
  AIAnnotationMark,
  insertAIContentAt,
  replaceSelectionWithAIContent,
} from "./extensions/AIAnnotation";
import { Autosave } from "./extensions/Autosave";
import { DialogueMark } from "./extensions/DialogueMark";
import { GhostText, simulateSuggestion } from "./extensions/GhostText";
import { NarrareDocument } from "./extensions/NarrareDocument";
import { SceneBreak } from "./extensions/SceneBreak";
import { useGhostTextOnboarding } from "./GhostTextOnboarding";

type StudioTranslator = ReturnType<typeof useTranslations>;

export interface AISuggestion {
  original: string;
  suggestions: string[];
  labels: string[];
  position: { from: number; to: number };
}

type RewritePhase = "idle" | "selecting-mode" | "streaming" | "showing-alternatives";

interface RewriteSelection {
  text: string;
  from: number;
  to: number;
  contextBefore: string;
  contextAfter: string;
}

interface ControllerParams {
  content: string;
  onChange: (content: string) => void;
  onAutosave?: (content: string) => Promise<void>;
  autosaveInterval?: number;
  chapterId?: string;
  novelId?: string;
  locale: string;
  t: StudioTranslator;
}

export const MIN_SELECTION_LENGTH = 50;
export const MAX_SELECTION_LENGTH = 2000;

export function useTipTapEditorController({
  content,
  onChange,
  onAutosave,
  autosaveInterval,
  chapterId,
  novelId,
  locale,
  t,
}: ControllerParams) {
  const [aiSuggestion, setAiSuggestion] = useState<AISuggestion | null>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectionInput, setShowRejectionInput] = useState(false);
  const [rewritePhase, setRewritePhase] = useState<RewritePhase>("idle");
  const [rewriteSelection, setRewriteSelection] = useState<RewriteSelection | null>(null);
  const [rewriteError, setRewriteError] = useState<AIErrorResponse | null>(null);
  const rewriteConfigRef = useRef<RewriteConfig | null>(null);
  const rewriteSelectionRef = useRef<RewriteSelection | null>(null);
  const { shouldShow: showOnboarding, dismiss: dismissOnboarding } = useGhostTextOnboarding();
  const [onboardingAnchor, setOnboardingAnchor] = useState<HTMLElement | null>(null);
  const recordFeedback = useRecordFeedback(novelId ?? "");
  const saveFnRef = useRef(onAutosave ?? (async () => {}));

  useEffect(() => {
    saveFnRef.current = onAutosave ?? (async () => {});
  }, [onAutosave]);

  const autosaveConfig = useMemo(
    () => ({
      interval: autosaveInterval ?? 30_000,
      saveFn: (value: string) => saveFnRef.current(value),
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
            recordFeedback.mutate(feedbackData, { onError: () => {} });
            writingApi.acceptDraft(data.requestId, data.currentText).catch(() => {});
          }
        : undefined,
    }),
    [autosaveInterval, novelId, chapterId, recordFeedback, onAutosave],
  );

  const fetchSuggestionRef = useRef<
    | ((params: { textBefore: string; textAfter: string; signal: AbortSignal }) => Promise<string>)
    | undefined
  >(undefined);
  useEffect(() => {
    fetchSuggestionRef.current = chapterId
      ? createSseSuggestionFetcher(chapterId, locale)
      : undefined;
  }, [chapterId, locale]);
  const ghostTextConfig = useMemo(
    () =>
      ({
        fetchSuggestion: (params: { textBefore: string; textAfter: string; signal: AbortSignal }) =>
          fetchSuggestionRef.current?.(params) ?? simulateSuggestion(params),
        enabled: true,
        minChars: 5,
        suggestionDelay: 800,
        hintText: t("ghostText.hint"),
        // Localized fetching status — injected into the non-React extension via
        // options so no hardcoded English appears in ProseMirror DOM
        // (CR-AUFG-07-10, ADR-043 Note 7).
        fetchingStatusText: t("aiActions.aiThinking"),
      }) satisfies Partial<import("./extensions/GhostText").GhostTextOptions>,
    [t],
  );

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({ document: false, heading: { levels: [1, 2, 3] } }),
      NarrareDocument,
      SceneBreak,
      DialogueMark,
      AIAnnotationMark,
      AIAnnotationExtension,
      Autosave.configure(autosaveConfig),
      GhostText.configure(ghostTextConfig),
      Placeholder.configure({ placeholder: t("editor.placeholder") }),
    ],
    content,
    onUpdate: ({ editor: ed }) => onChange(ed.getHTML()),
    editorProps: { attributes: { class: "max-w-none focus:outline-none min-h-[70vh] py-6 pr-8" } },
  });

  useEffect(() => {
    if (editor && content !== editor.getHTML())
      editor.commands.setContent(
        content.trim().startsWith("<") ? content : markdownToHtml(content),
      );
  }, [content, editor]);
  useEffect(() => {
    if (!editor) return;
    useEditorStore.getState().setEditor(editor);
    if (typeof window !== "undefined")
      (window as unknown as Window & { __narrareEditor: unknown }).__narrareEditor = editor;
  }, [editor]);
  useEffect(() => {
    if (!showOnboarding || !editor) return;
    const checkForGhostText = () => {
      const ghostEl = document.querySelector(".ghost-text-suggestion");
      if (ghostEl) setOnboardingAnchor(ghostEl as HTMLElement);
    };
    const observer = new MutationObserver(checkForGhostText);
    observer.observe(editor.view.dom, { childList: true, subtree: true });
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

  // --- Rewrite AI Operation (§16 lifecycle management) ---

  const rewriteAiOp = useAIOperation<RewriteAlternative[]>({
    execute: async (signal) => {
      const config = rewriteConfigRef.current;
      const sel = rewriteSelectionRef.current;
      if (!sel || !chapterId || !novelId || !config) {
        return [];
      }

      const alternatives: RewriteAlternative[] = [];

      await streamRewrite(
        chapterId,
        novelId,
        {
          selection_text: sel.text,
          context_before: sel.contextBefore,
          context_after: sel.contextAfter,
          mode: config.mode,
          options: config.mode !== "custom" ? { option: config.option } : undefined,
          count: config.count,
          custom_instructions: config.customInstructions,
          language: locale,
        },
        {
          onRequestInfo: () => {},
          onAlternative: (label, text) => {
            alternatives.push({ label, text });
            setAiSuggestion((prev) =>
              prev
                ? {
                    ...prev,
                    suggestions: alternatives.map((a) => a.text),
                    labels: alternatives.map((a) => a.label),
                  }
                : {
                    original: sel.text,
                    suggestions: alternatives.map((a) => a.text),
                    labels: alternatives.map((a) => a.label),
                    position: { from: sel.from, to: sel.to },
                  },
            );
            if (alternatives.length === 1) setSelectedSuggestion(0);
            setRewritePhase("showing-alternatives");
          },
          onAlternativeFinal: () => {
            // Stream complete — alternatives already accumulated
          },
          onError: (error: Error) => {
            // Let useAIOperation's error mapper handle it
            throw error;
          },
        },
        signal,
      );

      return alternatives;
    },
    errorMapper: mapSSEError,
    onSuccess: () => {
      setRewriteError(null);
    },
    onError: (error) => {
      setRewriteError(error);
      // If no alternatives were generated, go back to idle
      setAiSuggestion((prev) => {
        if (!prev || prev.suggestions.length === 0) {
          setRewritePhase("idle");
          return null;
        }
        return prev;
      });
    },
    connectionLossTimeout: 20_000,
  });

  const getSelectionContext = useCallback(
    (from: number, to: number) => {
      if (!editor) return { contextBefore: "", contextAfter: "" };
      const contextRadius = 800;
      return {
        contextBefore: editor.state.doc.textBetween(Math.max(0, from - contextRadius), from, " "),
        contextAfter: editor.state.doc.textBetween(
          to,
          Math.min(editor.state.doc.content.size, to + contextRadius),
          " ",
        ),
      };
    },
    [editor],
  );

  const handleAIRewrite = useCallback(() => {
    if (!editor) return;
    const { from, to } = editor.state.selection;
    const selectedText = editor.state.doc.textBetween(from, to, " ");
    const trimmedLength = selectedText.trim().length;
    if (trimmedLength < MIN_SELECTION_LENGTH || trimmedLength > MAX_SELECTION_LENGTH) return;
    setRewriteSelection({ text: selectedText, from, to, ...getSelectionContext(from, to) });
    setRewritePhase("selecting-mode");
  }, [editor, getSelectionContext]);

  const handleRewriteGenerate = useCallback(
    (config: RewriteConfig) => {
      if (!editor || !rewriteSelection || !chapterId || !novelId) return;
      rewriteConfigRef.current = config;
      rewriteSelectionRef.current = rewriteSelection;
      setRewritePhase("streaming");
      setRewriteError(null);
      rewriteAiOp.start();
    },
    [editor, rewriteSelection, chapterId, novelId, rewriteAiOp],
  );

  const resetRewriteState = useCallback(() => {
    setAiSuggestion(null);
    setRewritePhase("idle");
    setRewriteSelection(null);
    setShowRejectionInput(false);
    setRejectionReason("");
    setRewriteError(null);
    rewriteAiOp.reset();
  }, [rewriteAiOp]);
  const acceptSuggestion = useCallback(() => {
    if (!editor || !aiSuggestion) return;
    replaceSelectionWithAIContent(
      editor,
      `rewrite-${Date.now()}`,
      "rewrite",
      aiSuggestion.suggestions[selectedSuggestion],
      aiSuggestion.position.from,
      aiSuggestion.position.to,
    );
    resetRewriteState();
  }, [editor, aiSuggestion, selectedSuggestion, resetRewriteState]);
  const insertAsNew = useCallback(() => {
    if (!editor || !aiSuggestion) return;
    insertAIContentAt(
      editor,
      `rewrite-${Date.now()}`,
      "rewrite",
      aiSuggestion.suggestions[selectedSuggestion],
      aiSuggestion.position.to,
    );
    resetRewriteState();
  }, [editor, aiSuggestion, selectedSuggestion, resetRewriteState]);
  const rejectSuggestion = useCallback(() => {
    if (rejectionReason.trim()) resetRewriteState();
    else setShowRejectionInput(true);
  }, [rejectionReason, resetRewriteState]);
  const selectionLength = editor
    ? editor.state.doc
        .textBetween(editor.state.selection.from, editor.state.selection.to, " ")
        .trim().length
    : 0;

  return {
    editor,
    aiSuggestion,
    selectedSuggestion,
    setSelectedSuggestion,
    rejectionReason,
    setRejectionReason,
    showRejectionInput,
    rewritePhase,
    rewriteSelection,
    rewriteError,
    showOnboarding,
    dismissOnboarding,
    onboardingAnchor,
    selectionLength,
    isRewriteEnabled:
      selectionLength >= MIN_SELECTION_LENGTH && selectionLength <= MAX_SELECTION_LENGTH,
    isRewriteStreaming:
      rewritePhase === "streaming" || rewriteAiOp.isLoading || rewriteAiOp.isStreaming,
    handleAIRewrite,
    handleRewriteGenerate,
    handleRewriteCancel: () => {
      rewriteAiOp.cancel();
      setRewritePhase("idle");
      setRewriteSelection(null);
    },
    acceptSuggestion,
    insertAsNew,
    rejectSuggestion,
  };
}
