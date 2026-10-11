export type EditorRightPanelId =
  | "metadata"
  | "session"
  | "generation"
  | "scene_plan"
  | "beta_reader"
  | "readability"
  | "pov"
  | "coreference"
  | "character_voice"
  | "voice_check"
  | "voice_drift"
  | "author_voice"
  | "author_voice_drift"
  | "dialogue_coach"
  | "sentiment"
  | "consistency";

export type EditorRightPanelRequestSource =
  | "toolbar"
  | "sidebar"
  | "ai_result"
  | "recovery"
  | "url";

/**
 * Analysis panels rendered through the shared {@link EditorAnalysisPanels}
 * switch (RULE-04 extraction from {@link EditorPanelContent}). Derived from
 * {@link EditorRightPanelId} so it cannot drift — the non-analysis panels
 * (session / generation / scene_plan / metadata / dialogue_coach) stay in
 * EditorPanelContent.
 */
export type AnalysisPanelId = Exclude<
  EditorRightPanelId,
  "session" | "generation" | "scene_plan" | "metadata" | "dialogue_coach"
>;

export interface EditorRightPanelState {
  active: EditorRightPanelId | null;
  previous: EditorRightPanelId | null;
  requestedBy: EditorRightPanelRequestSource | null;
}

export const EDITOR_RIGHT_PANEL_PRIORITY = [
  "session",
  "generation",
  "scene_plan",
  "beta_reader",
  "readability",
  "pov",
  "coreference",
  "character_voice",
  "voice_check",
  "voice_drift",
  "author_voice",
  "author_voice_drift",
  "dialogue_coach",
  "sentiment",
  "consistency",
  "metadata",
] as const satisfies readonly EditorRightPanelId[];

export const CLOSED_EDITOR_RIGHT_PANEL_STATE: EditorRightPanelState = {
  active: null,
  previous: null,
  requestedBy: null,
};

const PANEL_IDS = new Set<EditorRightPanelId>(EDITOR_RIGHT_PANEL_PRIORITY);

export function isEditorRightPanelId(value: string | null): value is EditorRightPanelId {
  return value !== null && PANEL_IDS.has(value as EditorRightPanelId);
}

export function openEditorRightPanel(
  state: EditorRightPanelState,
  panel: EditorRightPanelId,
  requestedBy: EditorRightPanelRequestSource,
): EditorRightPanelState {
  return {
    active: panel,
    previous: state.active === panel ? state.previous : state.active,
    requestedBy,
  };
}

export function closeEditorRightPanel(
  state: EditorRightPanelState,
  panel: EditorRightPanelId | null = state.active,
): EditorRightPanelState {
  if (panel !== null && state.active !== panel) return state;
  if (state.previous !== null) {
    return { active: state.previous, previous: null, requestedBy: "recovery" };
  }
  return CLOSED_EDITOR_RIGHT_PANEL_STATE;
}

export function toggleEditorRightPanel(
  state: EditorRightPanelState,
  panel: EditorRightPanelId,
  requestedBy: EditorRightPanelRequestSource,
): EditorRightPanelState {
  if (state.active === panel) return closeEditorRightPanel(state, panel);
  return openEditorRightPanel(state, panel, requestedBy);
}
