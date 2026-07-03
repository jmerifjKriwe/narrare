"use client";

import { useTranslations } from "next-intl";
import { useEffect } from "react";
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

  useEffect(() => {
    if (activePanel === null) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closePanel(activePanel);
        if (returnFocusTo?.isConnected) returnFocusTo.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activePanel, closePanel, returnFocusTo]);

  // Shell-owned live region, always mounted so screen readers receive the
  // close transition (the section below unmounts when the panel is cleared,
  // which would otherwise swallow the "closed" announcement). Mirrors the
  // status announcement pattern in StudioWorkspaceShell.
  const statusRegion = (
    <div role="status" aria-live="polite" className="sr-only">
      {activePanel === null ? t("shell.panelClosed") : t("shell.panelOpened")}
    </div>
  );

  if (activePanel === null) return statusRegion;

  return (
    <>
      {statusRegion}
      <section
        data-testid="editor-right-panel"
        aria-labelledby="editor-right-panel-title"
        className="fixed inset-x-0 bottom-0 z-30 flex max-h-[85vh] flex-col overflow-y-auto rounded-t-xl border border-border bg-card shadow-2xl lg:static lg:z-auto lg:flex lg:h-full lg:max-h-none lg:w-96 lg:shrink-0 lg:overflow-hidden lg:rounded-none lg:border-y-0 lg:border-r-0 lg:border-l lg:shadow-none"
      >
        <h2 id="editor-right-panel-title" className="sr-only">
          {t("shell.editorRightPanel")}
        </h2>
        <EditorPanelContent
          activePanel={activePanel}
          closePanel={closePanel}
          {...panelContentProps}
        />
      </section>
    </>
  );
}
