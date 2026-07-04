"use client";

import { useTranslations } from "next-intl";
import { PanelShell } from "@/components/ui/panel-shell";
import type { EditorRightPanelId } from "@/lib/stores/editorRightPanelState";
import type { Chapter, ChapterSummary, VolumeStats } from "@/types";
import { EditorPanelContent } from "./EditorPanelContent";

export interface EditorRightPanelSlotProps {
  activePanel: EditorRightPanelId | null;
  closePanel: (panel?: EditorRightPanelId) => void;
  returnFocusTo?: HTMLElement | null;
  novelId: string;
  activeChapterId: string;
  content: string;
  chapter: Chapter | undefined;
  chapters: ChapterSummary[];
  sessionStartWordCount: number;
  volumeStats: VolumeStats | undefined;
  wordCount: number;
  charCount: number;
  paragraphCount: number;
  sessionMode: "interactive_session" | "interview_assisted";
  handleSessionClose: () => void;
  handleDraftAccepted: (text: string) => void;
  handleStartSession: (mode: string) => void;
}

export function EditorRightPanelSlot({
  activePanel,
  closePanel,
  returnFocusTo,
  ...panelContentProps
}: EditorRightPanelSlotProps) {
  const t = useTranslations("studio");

  // Shell-owned live region, always mounted so screen readers receive the
  // close transition (the PanelShell below unmounts when the panel is cleared,
  // which would otherwise swallow the "closed" announcement). Mirrors the
  // status announcement pattern in StudioWorkspaceShell.
  const statusRegion = (
    <div role="status" aria-live="polite" className="sr-only">
      {activePanel === null ? t("shell.panelClosed") : t("shell.panelOpened")}
    </div>
  );

  if (activePanel === null) return statusRegion;

  // Escape handling + focus lifecycle are owned by PanelShell's use-panel-focus
  // hook. Focus-return-to-the-opener is folded into onClose so the dismiss
  // control (Escape) restores focus to the invoking element, matching the
  // previous bespoke keydown handler.
  const handleClose = () => {
    closePanel(activePanel);
    if (returnFocusTo?.isConnected) returnFocusTo.focus();
  };

  return (
    <>
      {statusRegion}
      <PanelShell
        titleId="editor-right-panel-title"
        dialogLabel={t("shell.editorRightPanel")}
        side="right"
        testId="editor-right-panel"
        onClose={handleClose}
      >
        <EditorPanelContent
          activePanel={activePanel}
          closePanel={closePanel}
          {...panelContentProps}
        />
      </PanelShell>
    </>
  );
}
