import type { Editor } from "@tiptap/react";
import type {
  BetaReaderResponse,
  ConsistencyResponse,
  SentimentOverview,
} from "@/lib/api/analysis";
import type { ChapterSummary, SaveStatus } from "@/types";

export interface EditorState {
  activeChapterId: string | null;
  activeVolumeId: string | null;
  saveStatus: SaveStatus;
  lastSavedAt: Date | null;
  sidebarOpen: boolean;
  contextPanelOpen: boolean;
  focusMode: boolean;
  storyboardOpen: boolean;
  editor: Editor | null;
  isDragging: boolean;
  isGenerating: boolean;
  activeRequestId: string | null;
  generationMode: string | null;
  draftText: string;
  sessionActive: boolean;
  generationPanelOpen: boolean;
  extractionPanelOpen: boolean;
  betaReaderPanelOpen: boolean;
  betaReaderResult: BetaReaderResponse | null;
  betaReaderLoading: boolean;
  sentimentPanelOpen: boolean;
  sentimentResult: SentimentOverview[] | null;
  sentimentLoading: boolean;
  consistencyPanelOpen: boolean;
  consistencyResult: ConsistencyResponse | null;
  consistencyLoading: boolean;
  readabilityPanelOpen: boolean;
  povPanelOpen: boolean;
  coreferencePanelOpen: boolean;

  setActiveChapterId: (id: string | null) => void;
  setActiveVolumeId: (id: string | null) => void;
  setSaveStatus: (status: SaveStatus) => void;
  setEditor: (editor: Editor | null) => void;
  setIsDragging: (dragging: boolean) => void;
  toggleSidebar: () => void;
  toggleContextPanel: () => void;
  toggleFocusMode: () => void;
  toggleStoryboard: () => void;
  updateChapterWordCount: (
    chapterId: string,
    wordCount: number,
    chapters: ChapterSummary[],
  ) => ChapterSummary[];
  setGenerating: (value: boolean) => void;
  setActiveRequestId: (id: string | null) => void;
  setGenerationMode: (mode: string | null) => void;
  setDraftText: (text: string) => void;
  setSessionActive: (value: boolean) => void;
  toggleGenerationPanel: () => void;
  toggleExtractionPanel: () => void;
  toggleBetaReaderPanel: () => void;
  setBetaReaderResult: (result: BetaReaderResponse | null) => void;
  setBetaReaderLoading: (loading: boolean) => void;
  toggleSentimentPanel: () => void;
  setSentimentResult: (result: SentimentOverview[] | null) => void;
  setSentimentLoading: (loading: boolean) => void;
  toggleConsistencyPanel: () => void;
  setConsistencyResult: (result: ConsistencyResponse | null) => void;
  setConsistencyLoading: (loading: boolean) => void;
  toggleReadabilityPanel: () => void;
  togglePovPanel: () => void;
  toggleCoreferencePanel: () => void;
}
