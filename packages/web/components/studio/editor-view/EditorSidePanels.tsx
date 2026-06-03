import type { Chapter, ChapterSummary, VolumeStats } from "@/types";
import { BetaReaderPanel } from "../analysis/BetaReaderPanel";
import { ConsistencyPanel } from "../analysis/ConsistencyPanel";
import { POVPanel } from "../analysis/POVPanel";
import { ReadabilityPanel } from "../analysis/ReadabilityPanel";
import { SentimentPanel } from "../analysis/SentimentPanel";
import { GenerationPanel } from "../editor/GenerationPanel";
import { MetadataSidebar } from "../editor/MetadataSidebar";
import { SessionPanel } from "../editor/SessionPanel";
import { WikiChapterSummaryPanel } from "../kb/WikiChapterSummaryPanel";
import type { EditorPanelVisibility } from "./useEditorPanelVisibility";

interface EditorSidePanelsProps {
  visibility: EditorPanelVisibility;
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
  toggleGenerationPanel: () => void;
  toggleBetaReaderPanel: () => void;
  toggleReadabilityPanel: () => void;
  togglePovPanel: () => void;
  toggleSentimentPanel: () => void;
  toggleConsistencyPanel: () => void;
}

export function EditorSidePanels({
  visibility,
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
  toggleGenerationPanel,
  toggleBetaReaderPanel,
  toggleReadabilityPanel,
  togglePovPanel,
  toggleSentimentPanel,
  toggleConsistencyPanel,
}: EditorSidePanelsProps) {
  return (
    <>
      {visibility.showSessionPanel && (
        <SessionPanel
          chapterId={activeChapterId}
          novelId={novelId}
          mode={sessionMode}
          onClose={handleSessionClose}
        />
      )}
      {visibility.showGenerationPanel && (
        <GenerationPanel
          novelId={novelId}
          chapterId={activeChapterId}
          chapterContent={content}
          onDraftAccepted={handleDraftAccepted}
          onClose={toggleGenerationPanel}
          onStartSession={handleStartSession}
        />
      )}
      {visibility.showMetadataSidebar && (
        <div className="w-80 border-l border-border bg-card overflow-y-auto">
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
      )}
      {visibility.showBetaReaderPanel && (
        <BetaReaderPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={toggleBetaReaderPanel}
        />
      )}
      {visibility.showReadabilityPanel && (
        <ReadabilityPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={toggleReadabilityPanel}
        />
      )}
      {visibility.showPOVPanel && (
        <POVPanel novelId={novelId} chapterIds={[activeChapterId]} onClose={togglePovPanel} />
      )}
      {visibility.showSentimentPanel && (
        <SentimentPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={toggleSentimentPanel}
        />
      )}
      {visibility.showConsistencyPanel && (
        <ConsistencyPanel
          novelId={novelId}
          chapterIds={[activeChapterId]}
          onClose={toggleConsistencyPanel}
        />
      )}
    </>
  );
}
