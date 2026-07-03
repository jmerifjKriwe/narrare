import type { Editor } from "@tiptap/react";
import { useCallback, useState } from "react";
import { writingApi } from "@/lib/api/generation";
import { useEditorStore } from "@/lib/stores/editorStore";
import type { EditorGenerationActions } from "./types";

interface UseEditorGenerationActionsParams {
  editor: Editor | null;
  content: string;
  handleAutosave: (htmlContent: string) => Promise<void>;
}

export function useEditorGenerationActions({
  editor,
  content,
  handleAutosave,
}: UseEditorGenerationActionsParams): EditorGenerationActions {
  const activeRequestId = useEditorStore((s) => s.activeRequestId);
  const draftText = useEditorStore((s) => s.draftText);
  const setGenerating = useEditorStore((s) => s.setGenerating);
  const setActiveRequestId = useEditorStore((s) => s.setActiveRequestId);
  const setGenerationMode = useEditorStore((s) => s.setGenerationMode);
  const setDraftText = useEditorStore((s) => s.setDraftText);
  const setSessionActive = useEditorStore((s) => s.setSessionActive);
  const toggleGenerationPanel = useEditorStore((s) => s.toggleGenerationPanel);
  const [sessionMode, setSessionMode] = useState<"interactive_session" | "interview_assisted">(
    "interactive_session",
  );

  const handleDraftAccepted = useCallback(
    (text: string) => {
      if (editor) {
        editor.commands.insertContent(text);
      }
      setDraftText("");
      setGenerating(false);
      setActiveRequestId(null);
      const htmlContent = editor?.getHTML() ?? content;
      void handleAutosave(htmlContent);
    },
    [editor, content, setDraftText, setGenerating, setActiveRequestId, handleAutosave],
  );

  const handleStartSession = useCallback(
    (mode: string) => {
      setGenerationMode(mode);
      setSessionMode(mode as "interactive_session" | "interview_assisted");
      setSessionActive(true);
    },
    [setGenerationMode, setSessionActive],
  );

  const handleSessionClose = useCallback(() => {
    setSessionActive(false);
    setGenerationMode(null);
    setSessionMode("interactive_session");
  }, [setSessionActive, setGenerationMode]);

  const handleStartGeneration = useCallback(
    (mode: string) => {
      if (mode === "interactive_session" || mode === "interview_assisted") {
        handleStartSession(mode);
        return;
      }
      setGenerationMode(mode);
      toggleGenerationPanel();
    },
    [handleStartSession, setGenerationMode, toggleGenerationPanel],
  );

  const handleStopGeneration = useCallback(async () => {
    if (activeRequestId) {
      await writingApi.stopGeneration(activeRequestId);
    }
    setGenerating(false);
    setActiveRequestId(null);
  }, [activeRequestId, setGenerating, setActiveRequestId]);

  const handleAcceptDraft = useCallback(() => {
    if (draftText) {
      handleDraftAccepted(draftText);
    }
  }, [draftText, handleDraftAccepted]);

  const handleRejectDraft = useCallback(async () => {
    if (activeRequestId) {
      await writingApi.rejectDraft(activeRequestId);
    }
    setDraftText("");
    setGenerating(false);
    setActiveRequestId(null);
  }, [activeRequestId, setDraftText, setGenerating, setActiveRequestId]);

  return {
    sessionMode,
    handleDraftAccepted,
    handleStartSession,
    handleSessionClose,
    handleStartGeneration,
    handleStopGeneration,
    handleAcceptDraft,
    handleRejectDraft,
  };
}
