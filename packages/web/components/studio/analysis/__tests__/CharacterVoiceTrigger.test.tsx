/**
 * CharacterVoiceTrigger tests — toolbar button for CharacterVoicePanel.
 *
 * Mirrors CoreferenceTrigger.test.tsx. Tests:
 * 1. Renders trigger button with label
 * 2. Renders with aria-label from tooltip
 * 3. Calls toggleCharacterVoicePanel on click
 * 4. Reflects closed/open state as aria-pressed
 * 5. Is disabled when disabled=true / enabled by default
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { CharacterVoiceTrigger } from "@/components/studio/analysis/CharacterVoiceTrigger";
import { useEditorStore } from "@/lib/stores/editorStore";

describe("CharacterVoiceTrigger", () => {
  beforeEach(() => {
    useEditorStore.setState({
      rightPanel: { active: null, previous: null, requestedBy: null },
    });
  });

  it("renders trigger button with label", () => {
    render(<CharacterVoiceTrigger />);

    expect(screen.getByText("characterVoice.trigger")).toBeDefined();
  });

  it("renders with aria-label from tooltip", () => {
    render(<CharacterVoiceTrigger />);

    expect(screen.getByLabelText("characterVoice.triggerTooltip")).toBeDefined();
  });

  it("calls toggleCharacterVoicePanel on click", () => {
    render(<CharacterVoiceTrigger />);

    const button = screen.getByText("characterVoice.trigger").closest("button")!;
    fireEvent.click(button);

    expect(useEditorStore.getState().rightPanel.active).toBe("character_voice");
  });

  it("reflects closed state as aria-pressed=false", () => {
    useEditorStore.setState({ rightPanel: { active: null, previous: null, requestedBy: null } });
    render(<CharacterVoiceTrigger />);

    const button = screen.getByText("characterVoice.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects open state as aria-pressed=true", () => {
    useEditorStore.setState({
      rightPanel: { active: "character_voice", previous: null, requestedBy: "toolbar" },
    });
    render(<CharacterVoiceTrigger />);

    const button = screen.getByText("characterVoice.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });

  it("is disabled when disabled=true", () => {
    render(<CharacterVoiceTrigger disabled />);

    const button = screen.getByText("characterVoice.trigger").closest("button")!;
    expect(button.disabled).toBe(true);
  });

  it("is enabled by default", () => {
    render(<CharacterVoiceTrigger />);

    const button = screen.getByText("characterVoice.trigger").closest("button")!;
    expect(button.disabled).toBe(false);
  });
});
