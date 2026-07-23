"use client";

import type { Editor } from "@tiptap/react";
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
import { DialogueCoachPanelSlot } from "./DialogueCoachPanelSlot";

export interface EditorPanelContentProps {
  activePanel: EditorRightPanelId;
  closePanel: (panel?: EditorRightPanelId) => void;
  novelId: string;
  activeChapterId: string;
  content: string;
  /**
   * The live TipTap editor instance. Threaded from EditorView so the Dialogue
   * Coach panel can read the current selection + apply rewrites without
   * reaching into the store from inside the panel (vercel-react-best-practices:
   * pass dependencies as props).
   */
  editor: Editor | null;
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

/**
 * Renders the single occupant of the editor right-panel slot.
 *
 * Extracted from {@link EditorRightPanelSlot} so the slot stays a thin
 * accessibility/ownership shell (Escape handling, shell live region,
 * responsive frame) while this module owns the exhaustive panel switch.
 * Keeps both files under the RULE-04 200-line component limit.
 */
export function EditorPanelContent({
  activePanel,
  closePanel,
  novelId,
  activeChapterId,
  content,
  editor,
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
}: EditorPanelContentProps) {
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
    case "dialogue_coach":
      // The coach needs the editor + its live selection. Render through a
      // scoped slot so the selection subscription re-renders only this side
      // panel, never the editor canvas (see DialogueCoachPanelSlot).
      return (
        <DialogueCoachPanelSlot
          editor={editor}
          chapterId={activeChapterId}
          onClose={() => closePanel("dialogue_coach")}
        />
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
}
