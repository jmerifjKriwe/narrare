import type { Editor } from "@tiptap/react";
import type { Chapter, ChapterSummary, VolumeStats } from "@/types";
import type { SlashCommandHandlers } from "../editor/slash-commands";

export interface EditorChapterData {
  chapter: Chapter | undefined;
  chapters: ChapterSummary[];
  volumeStats: VolumeStats | undefined;
  isLoading: boolean;
  title: string;
  setTitle: (title: string) => void;
  content: string;
  setContent: (content: string) => void;
  wordCount: number;
  charCount: number;
  paragraphCount: number;
  sessionStartWordCount: number;
}

export interface EditorPersistenceActions {
  handleSave: () => Promise<void>;
  handleAutosave: (htmlContent: string) => Promise<void>;
  lastSaved: string | null;
}

export interface EditorGenerationActions {
  sessionMode: "interactive_session" | "interview_assisted";
  handleDraftAccepted: (text: string) => void;
  handleStartSession: (mode: string) => void;
  handleSessionClose: () => void;
  handleStartGeneration: (mode: string) => void;
  handleStopGeneration: () => Promise<void>;
  handleAcceptDraft: () => void;
  handleRejectDraft: () => Promise<void>;
}

export interface EditorSurfaceProps {
  editor: Editor | null;
  novelId: string;
  activeChapterId: string;
  content: string;
  setContent: (content: string) => void;
  handleAutosave: (htmlContent: string) => Promise<void>;
  /** Host handlers for slash commands the workspace surface wires (B08/B09). */
  slashCommandHandlers?: Partial<SlashCommandHandlers>;
}
