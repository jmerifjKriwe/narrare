import { useEditorStore } from "@/lib/stores/editorStore";

export interface EditorPanelVisibility {
  showSessionPanel: boolean;
  showGenerationPanel: boolean;
  showBetaReaderPanel: boolean;
  showReadabilityPanel: boolean;
  showPOVPanel: boolean;
  showSentimentPanel: boolean;
  showConsistencyPanel: boolean;
  showMetadataSidebar: boolean;
}

export function useEditorPanelVisibility(activeChapterId: string | null): EditorPanelVisibility {
  const contextPanelOpen = useEditorStore((s) => s.contextPanelOpen);
  const sessionActive = useEditorStore((s) => s.sessionActive);
  const generationPanelOpen = useEditorStore((s) => s.generationPanelOpen);
  const betaReaderPanelOpen = useEditorStore((s) => s.betaReaderPanelOpen);
  const sentimentPanelOpen = useEditorStore((s) => s.sentimentPanelOpen);
  const consistencyPanelOpen = useEditorStore((s) => s.consistencyPanelOpen);
  const readabilityPanelOpen = useEditorStore((s) => s.readabilityPanelOpen);
  const povPanelOpen = useEditorStore((s) => s.povPanelOpen);
  const hasActiveChapter = !!activeChapterId;

  const showSessionPanel = sessionActive && hasActiveChapter;
  const showGenerationPanel = generationPanelOpen && hasActiveChapter && !showSessionPanel;
  const showBetaReaderPanel =
    betaReaderPanelOpen && hasActiveChapter && !showSessionPanel && !showGenerationPanel;
  const showReadabilityPanel =
    readabilityPanelOpen &&
    hasActiveChapter &&
    !showSessionPanel &&
    !showGenerationPanel &&
    !showBetaReaderPanel;
  const showPOVPanel =
    povPanelOpen &&
    hasActiveChapter &&
    !showSessionPanel &&
    !showGenerationPanel &&
    !showBetaReaderPanel &&
    !showReadabilityPanel;
  const showSentimentPanel =
    sentimentPanelOpen &&
    hasActiveChapter &&
    !showSessionPanel &&
    !showGenerationPanel &&
    !showBetaReaderPanel &&
    !showReadabilityPanel &&
    !showPOVPanel;
  const showConsistencyPanel =
    consistencyPanelOpen &&
    hasActiveChapter &&
    !showSessionPanel &&
    !showGenerationPanel &&
    !showBetaReaderPanel &&
    !showReadabilityPanel &&
    !showPOVPanel &&
    !showSentimentPanel;
  const showMetadataSidebar =
    contextPanelOpen &&
    !showSessionPanel &&
    !showGenerationPanel &&
    !showBetaReaderPanel &&
    !showReadabilityPanel &&
    !showPOVPanel &&
    !showSentimentPanel &&
    !showConsistencyPanel;

  return {
    showSessionPanel,
    showGenerationPanel,
    showBetaReaderPanel,
    showReadabilityPanel,
    showPOVPanel,
    showSentimentPanel,
    showConsistencyPanel,
    showMetadataSidebar,
  };
}
