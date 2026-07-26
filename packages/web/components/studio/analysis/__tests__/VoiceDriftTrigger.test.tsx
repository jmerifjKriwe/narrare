/**
 * VoiceDriftTrigger tests — toolbar button for VoiceDriftPanel (ANAL-009).
 *
 * Mirrors CharacterVoiceTrigger.test.tsx. The trigger is a store-coupled
 * panel toggle (calls toggleRightPanel("voice_drift", "toolbar")) and reflects
 * the active state as aria-pressed. Tests:
 * 1. Renders trigger button with label
 * 2. Renders with aria-label from tooltip
 * 3. Calls toggleRightPanel("voice_drift") on click
 * 4. Reflects closed/open state as aria-pressed
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { VoiceDriftTrigger } from "@/components/studio/analysis/VoiceDriftTrigger";
import { useEditorStore } from "@/lib/stores/editorStore";

describe("VoiceDriftTrigger", () => {
  beforeEach(() => {
    useEditorStore.setState({
      rightPanel: { active: null, previous: null, requestedBy: null },
    });
  });

  it("renders trigger button with label", () => {
    render(<VoiceDriftTrigger />);

    expect(screen.getByText("voiceDrift.trigger")).toBeDefined();
  });

  it("renders with aria-label from tooltip", () => {
    render(<VoiceDriftTrigger />);

    expect(screen.getByLabelText("voiceDrift.triggerTooltip")).toBeDefined();
  });

  it("calls toggleRightPanel('voice_drift') on click", () => {
    render(<VoiceDriftTrigger />);

    const button = screen.getByText("voiceDrift.trigger").closest("button")!;
    fireEvent.click(button);

    expect(useEditorStore.getState().rightPanel.active).toBe("voice_drift");
  });

  it("reflects closed state as aria-pressed=false", () => {
    useEditorStore.setState({ rightPanel: { active: null, previous: null, requestedBy: null } });
    render(<VoiceDriftTrigger />);

    const button = screen.getByText("voiceDrift.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects open state as aria-pressed=true", () => {
    useEditorStore.setState({
      rightPanel: { active: "voice_drift", previous: null, requestedBy: "toolbar" },
    });
    render(<VoiceDriftTrigger />);

    const button = screen.getByText("voiceDrift.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });
});
