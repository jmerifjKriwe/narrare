import { fireEvent, render, screen } from "@testing-library/react";
import type { Editor } from "@tiptap/react";
import { describe, expect, it, vi } from "vitest";
import { EditorToolbar } from "./EditorToolbar";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

// Child triggers pull from useEditorStore; stub them so the toolbar's own
// onClickCapture opener-tracking is what we exercise.
vi.mock("../analysis/BetaReaderTrigger", () => ({
  BetaReaderTrigger: () => <div data-testid="beta-reader-trigger" />,
}));
vi.mock("../analysis/SentimentTrigger", () => ({
  SentimentTrigger: () => <div data-testid="sentiment-trigger" />,
}));
vi.mock("../analysis/ConsistencyTrigger", () => ({
  ConsistencyTrigger: () => <div data-testid="consistency-trigger" />,
}));
vi.mock("../analysis/ReadabilityTrigger", () => ({
  ReadabilityTrigger: () => <div data-testid="readability-trigger" />,
}));
vi.mock("../analysis/POVTrigger", () => ({
  POVTrigger: () => <div data-testid="pov-trigger" />,
}));
vi.mock("../analysis/CoreferenceTrigger", () => ({
  CoreferenceTrigger: () => <div data-testid="coreference-trigger" />,
}));
vi.mock("../analysis/CharacterVoiceTrigger", () => ({
  CharacterVoiceTrigger: () => <div data-testid="character-voice-trigger" />,
}));
vi.mock("../analysis/VoiceCheckTrigger", () => ({
  VoiceCheckTrigger: () => <div data-testid="voice-check-trigger" />,
}));
vi.mock("../editor/GhostTextConfig", () => ({
  GhostTextConfig: () => <div data-testid="ghost-text-config" />,
}));

// Minimal editor stub: only isActive() is read at render; click handlers here
// go through the mocked props, not the editor.
const editorStub = { isActive: () => false } as unknown as Editor;

const baseProps = {
  editor: editorStub,
  activeRightPanel: null,
  extractionPanelOpen: false,
  toggleRightPanel: vi.fn(),
  toggleExtractionPanel: vi.fn(),
  openNameGenerator: vi.fn(),
};

describe("EditorToolbar opener tracking", () => {
  it("records the opener button when the click lands on an SVG icon", () => {
    const onRightPanelOpenerChange = vi.fn();
    render(<EditorToolbar {...baseProps} onRightPanelOpenerChange={onRightPanelOpenerChange} />);

    const generateButton = screen.getByRole("button", { name: "editor.generate" });
    const icon = generateButton.querySelector("svg");
    expect(icon).not.toBeNull();

    // lucide icons render as SVGElement (not HTMLElement). Clicking the icon
    // must still resolve to its enclosing button for focus-return tracking.
    fireEvent.click(icon as SVGElement);

    expect(onRightPanelOpenerChange).toHaveBeenCalledTimes(1);
    expect(onRightPanelOpenerChange).toHaveBeenCalledWith(generateButton);
  });
});
