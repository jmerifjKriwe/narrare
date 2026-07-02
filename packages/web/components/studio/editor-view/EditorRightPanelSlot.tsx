"use client";

import { useTranslations } from "next-intl";
import { useEffect } from "react";
import type { EditorRightPanelId } from "@/lib/stores/editorRightPanelState";
import type { Chapter, ChapterSummary, VolumeStats } from "@/types";
import { BetaReaderPanel } from "../analysis/BetaReaderPanel";
import { CharacterVoicePanel } from "../analysis/CharacterVoicePanel";
import { ConsistencyPanel } from "../analysis/ConsistencyPanel";
import { CoreferencePanel } from "../analysis/CoreferencePanel";
import { POVPanel } from "../analysis/POVPanel";
import { ReadabilityPanel } from "../analysis/ReadabilityPanel";
import { SentimentPanel } from "../analysis/SentimentPanel";
import { VoiceCheckPanel } from "../analysis/VoiceCheckPanel";
import { GenerationPanel } from "../editor/GenerationPanel";
import { MetadataSidebar } from "../editor/MetadataSidebar";
import { SessionPanel } from "../editor/SessionPanel";
import { WikiChapterSummaryPanel } from "../kb/WikiChapterSummaryPanel";

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
  novelId,
  activeChapterId,
  content,
  chapter,
  chapters,
  sessionStartWordCount,
  volumeStats,
  wordCount,
  charCount,
  paragraphCount,
  sessionMode,
  handleSessionClose,
  handleDraftAccepted,
  handleStartSession,
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

  if (activePanel === null) return null;

  const panelTitleId = "editor-right-panel-title";
  const panelContent = (() => {
    switch (activePanel) {
      case "session":
        return (
          <SessionPanel
            chapterId={activeChapterId}
            novelId={novelId}
            mode={sessionMode}
            onClose={handleSessionClose}
          />
        );
      case "generation":
        return (
          <GenerationPanel
            novelId={novelId}
            chapterId={activeChapterId}
            chapterContent={content}
            onDraftAccepted={handleDraftAccepted}
            onClose={() => closePanel("generation")}
            onStartSession={handleStartSession}
          />
        );
      case "metadata":
        return (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <MetadataSidebar
              wordCount={wordCount}
              charCount={charCount}
              paragraphCount={paragraphCount}
              chapter={chapter ?? null}
              chapters={chapters}
              sessionStartWordCount={sessionStartWordCount}
              activeVolumeStats={volumeStats ?? null}
            />
            <div className="px-4 pb-4">
              <WikiChapterSummaryPanel
                novelId={novelId}
                chapterId={activeChapterId}
                chapterTitle={chapter?.title}
              />
            </div>
          </div>
        );
      case "beta_reader":
        return (
          <BetaReaderPanel
            novelId={novelId}
            chapterIds={[activeChapterId]}
            onClose={() => closePanel("beta_reader")}
          />
        );
      case "readability":
        return (
          <ReadabilityPanel
            novelId={novelId}
            chapterIds={[activeChapterId]}
            onClose={() => closePanel("readability")}
          />
        );
      case "pov":
        return (
          <POVPanel
            novelId={novelId}
            chapterIds={[activeChapterId]}
            onClose={() => closePanel("pov")}
          />
        );
      case "coreference":
        return (
          <CoreferencePanel
            novelId={novelId}
            chapterIds={[activeChapterId]}
            onClose={() => closePanel("coreference")}
          />
        );
      case "character_voice":
        return (
          <CharacterVoicePanel
            novelId={novelId}
            chapterIds={[activeChapterId]}
            onClose={() => closePanel("character_voice")}
          />
        );
      case "voice_check":
        return (
          <VoiceCheckPanel chapterId={activeChapterId} onClose={() => closePanel("voice_check")} />
        );
      case "sentiment":
        return (
          <SentimentPanel
            novelId={novelId}
            chapterIds={[activeChapterId]}
            onClose={() => closePanel("sentiment")}
          />
        );
      case "consistency":
        return (
          <ConsistencyPanel
            novelId={novelId}
            chapterIds={[activeChapterId]}
            onClose={() => closePanel("consistency")}
          />
        );
      default: {
        const _exhaustive: never = activePanel;
        return _exhaustive;
      }
    }
  })();

  return (
    <section
      aria-labelledby={panelTitleId}
      className="hidden h-full w-96 shrink-0 border-l border-border bg-card lg:flex lg:flex-col"
    >
      <h2 id={panelTitleId} className="sr-only">
        {t("shell.editorRightPanel")}
      </h2>
      {panelContent}
    </section>
  );
}
