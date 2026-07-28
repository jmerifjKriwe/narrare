import { describe, expect, it } from "vitest";
import {
  closeEditorRightPanel,
  EDITOR_RIGHT_PANEL_PRIORITY,
  type EditorRightPanelState,
  isEditorRightPanelId,
  openEditorRightPanel,
  toggleEditorRightPanel,
} from "./editorRightPanelState";

describe("editor right panel state", () => {
  const closed: EditorRightPanelState = { active: null, previous: null, requestedBy: null };

  it("defines the approved priority order", () => {
    expect(EDITOR_RIGHT_PANEL_PRIORITY).toEqual([
      "session",
      "generation",
      "beta_reader",
      "readability",
      "pov",
      "coreference",
      "character_voice",
      "voice_check",
      "voice_drift",
      "author_voice",
      "dialogue_coach",
      "sentiment",
      "consistency",
      "metadata",
    ]);
  });

  it("can represent only one active panel", () => {
    const state = openEditorRightPanel(closed, "metadata", "toolbar");
    const next = openEditorRightPanel(state, "readability", "toolbar");
    expect(next).toEqual({ active: "readability", previous: "metadata", requestedBy: "toolbar" });
  });

  it("toggles the active panel closed and restores previous metadata", () => {
    const metadata = openEditorRightPanel(closed, "metadata", "toolbar");
    const readability = openEditorRightPanel(metadata, "readability", "toolbar");
    expect(toggleEditorRightPanel(readability, "readability", "toolbar")).toEqual({
      active: "metadata",
      previous: null,
      requestedBy: "recovery",
    });
  });

  it("closes to empty state when no previous panel is recoverable", () => {
    const state = openEditorRightPanel(closed, "voice_check", "toolbar");
    expect(closeEditorRightPanel(state, "voice_check")).toEqual(closed);
  });

  it("narrows valid panel IDs", () => {
    expect(isEditorRightPanelId("sentiment")).toBe(true);
    expect(isEditorRightPanelId("session")).toBe(true);
    expect(isEditorRightPanelId("dialogue_coach")).toBe(true);
    expect(isEditorRightPanelId("voice_drift")).toBe(true);
    expect(isEditorRightPanelId("author_voice")).toBe(true);
    expect(isEditorRightPanelId("extraction")).toBe(false);
  });
});
