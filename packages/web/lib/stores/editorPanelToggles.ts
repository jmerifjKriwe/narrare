import type { EditorState } from "./editorStoreTypes";

type PanelPatch = Partial<EditorState>;

const closeRightPanels: PanelPatch = {
  contextPanelOpen: false,
  generationPanelOpen: false,
  betaReaderPanelOpen: false,
  sentimentPanelOpen: false,
  consistencyPanelOpen: false,
  readabilityPanelOpen: false,
  povPanelOpen: false,
  coreferencePanelOpen: false,
  characterVoicePanelOpen: false,
  voiceCheckPanelOpen: false,
};

export function toggleBetaReaderPanel(s: EditorState): PanelPatch {
  return s.betaReaderPanelOpen
    ? { betaReaderPanelOpen: false }
    : { ...closeRightPanels, betaReaderPanelOpen: true };
}

export function toggleSentimentPanel(s: EditorState): PanelPatch {
  return s.sentimentPanelOpen
    ? { sentimentPanelOpen: false }
    : { ...closeRightPanels, sentimentPanelOpen: true };
}

export function toggleConsistencyPanel(s: EditorState): PanelPatch {
  return s.consistencyPanelOpen
    ? { consistencyPanelOpen: false }
    : { ...closeRightPanels, consistencyPanelOpen: true };
}

export function toggleReadabilityPanel(s: EditorState): PanelPatch {
  return s.readabilityPanelOpen
    ? { readabilityPanelOpen: false }
    : { ...closeRightPanels, readabilityPanelOpen: true };
}

export function togglePovPanel(s: EditorState): PanelPatch {
  return s.povPanelOpen ? { povPanelOpen: false } : { ...closeRightPanels, povPanelOpen: true };
}

export function toggleCoreferencePanel(s: EditorState): PanelPatch {
  return s.coreferencePanelOpen
    ? { coreferencePanelOpen: false }
    : { ...closeRightPanels, coreferencePanelOpen: true };
}

export function toggleCharacterVoicePanel(s: EditorState): PanelPatch {
  return s.characterVoicePanelOpen
    ? { characterVoicePanelOpen: false }
    : { ...closeRightPanels, characterVoicePanelOpen: true };
}

export function toggleVoiceCheckPanel(s: EditorState): PanelPatch {
  return s.voiceCheckPanelOpen
    ? { voiceCheckPanelOpen: false }
    : { ...closeRightPanels, voiceCheckPanelOpen: true };
}
