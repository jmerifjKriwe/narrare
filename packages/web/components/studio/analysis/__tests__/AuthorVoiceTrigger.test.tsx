/**
 * AuthorVoiceTrigger tests — toolbar button for AuthorVoicePanel (ANAL-007).
 *
 * Mirrors VoiceDriftTrigger.test.tsx. The trigger is a store-coupled panel
 * toggle (calls toggleRightPanel("author_voice", "toolbar")) and reflects the
 * active state as aria-pressed. Tests:
 * 1. Renders trigger button with label
 * 2. Renders with aria-label from tooltip
 * 3. Calls toggleRightPanel("author_voice") on click
 * 4. Reflects closed/open state as aria-pressed
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { AuthorVoiceTrigger } from "@/components/studio/analysis/AuthorVoiceTrigger";
import { useEditorStore } from "@/lib/stores/editorStore";

describe("AuthorVoiceTrigger", () => {
  beforeEach(() => {
    useEditorStore.setState({
      rightPanel: { active: null, previous: null, requestedBy: null },
    });
  });

  it("renders trigger button with label", () => {
    render(<AuthorVoiceTrigger />);

    expect(screen.getByText("authorVoice.trigger")).toBeDefined();
  });

  it("renders with aria-label from tooltip", () => {
    render(<AuthorVoiceTrigger />);

    expect(screen.getByLabelText("authorVoice.triggerTooltip")).toBeDefined();
  });

  it("calls toggleRightPanel('author_voice') on click", () => {
    render(<AuthorVoiceTrigger />);

    const button = screen.getByText("authorVoice.trigger").closest("button")!;
    fireEvent.click(button);

    expect(useEditorStore.getState().rightPanel.active).toBe("author_voice");
  });

  it("reflects closed state as aria-pressed=false", () => {
    useEditorStore.setState({ rightPanel: { active: null, previous: null, requestedBy: null } });
    render(<AuthorVoiceTrigger />);

    const button = screen.getByText("authorVoice.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects open state as aria-pressed=true", () => {
    useEditorStore.setState({
      rightPanel: { active: "author_voice", previous: null, requestedBy: "toolbar" },
    });
    render(<AuthorVoiceTrigger />);

    const button = screen.getByText("authorVoice.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });
});
