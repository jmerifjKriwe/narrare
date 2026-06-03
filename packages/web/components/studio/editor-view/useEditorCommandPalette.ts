import { type Dispatch, type SetStateAction, useEffect, useMemo, useState } from "react";
import { useEditorStore } from "@/lib/stores/editorStore";
import type { CommandContext, CommandState } from "../editor/commands";

interface UseEditorCommandPaletteParams {
  handleSave: () => Promise<void>;
  handleStartGeneration: (mode: string) => void;
  handleStopGeneration: () => Promise<void>;
  handleAcceptDraft: () => void;
  handleRejectDraft: () => Promise<void>;
}

interface UseEditorCommandPaletteResult {
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (open: boolean) => void;
  commandContext: CommandContext;
  commandState: CommandState;
}

export function useEditorCommandPalette({
  handleSave,
  handleStartGeneration,
  handleStopGeneration,
  handleAcceptDraft,
  handleRejectDraft,
}: UseEditorCommandPaletteParams): UseEditorCommandPaletteResult {
  const toggleSidebar = useEditorStore((s) => s.toggleSidebar);
  const toggleFocusMode = useEditorStore((s) => s.toggleFocusMode);
  const toggleContextPanel = useEditorStore((s) => s.toggleContextPanel);
  const toggleStoryboard = useEditorStore((s) => s.toggleStoryboard);
  const toggleGenerationPanel = useEditorStore((s) => s.toggleGenerationPanel);
  const isGenerating = useEditorStore((s) => s.isGenerating);
  const draftText = useEditorStore((s) => s.draftText);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  const commandContext: CommandContext = useMemo(
    () => ({
      toggleSidebar,
      toggleFocusMode,
      toggleContextPanel,
      toggleStoryboard,
      saveChapter: () => void handleSave(),
      createChapter: () => {},
      startGeneration: handleStartGeneration,
      stopGeneration: handleStopGeneration,
      acceptDraft: handleAcceptDraft,
      rejectDraft: handleRejectDraft,
      toggleGenerationPanel,
      startExtend: (_length: "short" | "medium" | "long") => {},
      startRewrite: () => {},
    }),
    [
      toggleSidebar,
      toggleFocusMode,
      toggleContextPanel,
      toggleStoryboard,
      handleSave,
      handleStartGeneration,
      handleStopGeneration,
      handleAcceptDraft,
      handleRejectDraft,
      toggleGenerationPanel,
    ],
  );

  const commandState: CommandState = useMemo(
    () => ({
      isGenerating,
      hasDraft: draftText.length > 0,
      hasPendingAnnotation: false,
      hasSelection: false,
      selectionLength: 0,
    }),
    [isGenerating, draftText],
  );

  useEditorKeyboardShortcuts({ handleSave, setCommandPaletteOpen });

  return {
    commandPaletteOpen,
    setCommandPaletteOpen,
    commandContext,
    commandState,
  };
}

function useEditorKeyboardShortcuts({
  handleSave,
  setCommandPaletteOpen,
}: {
  handleSave: () => Promise<void>;
  setCommandPaletteOpen: Dispatch<SetStateAction<boolean>>;
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "s") {
        event.preventDefault();
        void handleSave();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleSave, setCommandPaletteOpen]);
}
