/**
 * AuthorVoiceDriftTrigger tests — toolbar button for AuthorVoiceDriftPanel
 * (ANAL-009 Phase 2B).
 *
 * Mirrors AuthorVoiceTrigger.test.tsx / VoiceDriftTrigger.test.tsx. The trigger
 * is a store-coupled panel toggle (calls toggleRightPanel("author_voice_drift",
 * "toolbar")) and reflects the active state as aria-pressed. Tests:
 * 1. Renders trigger button with label
 * 2. Renders with aria-label from tooltip
 * 3. Calls toggleRightPanel("author_voice_drift") on click
 * 4. Reflects closed/open state as aria-pressed
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { AuthorVoiceDriftTrigger } from "@/components/studio/analysis/AuthorVoiceDriftTrigger";
import { useEditorStore } from "@/lib/stores/editorStore";

describe("AuthorVoiceDriftTrigger", () => {
  beforeEach(() => {
    useEditorStore.setState({
      rightPanel: { active: null, previous: null, requestedBy: null },
    });
  });

  it("renders trigger button with label", () => {
    render(<AuthorVoiceDriftTrigger />);

    expect(screen.getByText("authorVoiceDrift.trigger")).toBeDefined();
  });

  it("renders with aria-label from tooltip", () => {
    render(<AuthorVoiceDriftTrigger />);

    expect(screen.getByLabelText("authorVoiceDrift.triggerTooltip")).toBeDefined();
  });

  it("calls toggleRightPanel('author_voice_drift') on click", () => {
    render(<AuthorVoiceDriftTrigger />);

    const button = screen.getByText("authorVoiceDrift.trigger").closest("button")!;
    fireEvent.click(button);

    expect(useEditorStore.getState().rightPanel.active).toBe("author_voice_drift");
  });

  it("reflects closed state as aria-pressed=false", () => {
    useEditorStore.setState({ rightPanel: { active: null, previous: null, requestedBy: null } });
    render(<AuthorVoiceDriftTrigger />);

    const button = screen.getByText("authorVoiceDrift.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects open state as aria-pressed=true", () => {
    useEditorStore.setState({
      rightPanel: { active: "author_voice_drift", previous: null, requestedBy: "toolbar" },
    });
    render(<AuthorVoiceDriftTrigger />);

    const button = screen.getByText("authorVoiceDrift.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });
});
