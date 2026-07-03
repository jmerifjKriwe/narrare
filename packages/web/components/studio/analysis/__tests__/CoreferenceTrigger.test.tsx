/**
 * CoreferenceTrigger tests — toolbar button for CoreferencePanel.
 *
 * Tests:
 * 1. Renders trigger button with label
 * 2. Calls toggleCoreferencePanel on click
 * 3. Reflects open state as aria-pressed
 * 4. Is disabled when disabled=true
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { CoreferenceTrigger } from "@/components/studio/analysis/CoreferenceTrigger";
import { useEditorStore } from "@/lib/stores/editorStore";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CoreferenceTrigger", () => {
  beforeEach(() => {
    useEditorStore.setState({
      rightPanel: { active: null, previous: null, requestedBy: null },
    });
  });

  it("renders trigger button with label", () => {
    render(<CoreferenceTrigger />);

    expect(screen.getByText("coreference.trigger")).toBeDefined();
  });

  it("renders with aria-label from tooltip", () => {
    render(<CoreferenceTrigger />);

    expect(screen.getByLabelText("coreference.triggerTooltip")).toBeDefined();
  });

  it("calls toggleCoreferencePanel on click", () => {
    render(<CoreferenceTrigger />);

    const button = screen.getByText("coreference.trigger").closest("button")!;
    fireEvent.click(button);

    expect(useEditorStore.getState().rightPanel.active).toBe("coreference");
  });

  it("reflects closed state as aria-pressed=false", () => {
    useEditorStore.setState({ rightPanel: { active: null, previous: null, requestedBy: null } });
    render(<CoreferenceTrigger />);

    const button = screen.getByText("coreference.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects open state as aria-pressed=true", () => {
    useEditorStore.setState({
      rightPanel: { active: "coreference", previous: null, requestedBy: "toolbar" },
    });
    render(<CoreferenceTrigger />);

    const button = screen.getByText("coreference.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });

  it("is disabled when disabled=true", () => {
    render(<CoreferenceTrigger disabled />);

    const button = screen.getByText("coreference.trigger").closest("button")!;
    expect(button.disabled).toBe(true);
  });

  it("is enabled by default", () => {
    render(<CoreferenceTrigger />);

    const button = screen.getByText("coreference.trigger").closest("button")!;
    expect(button.disabled).toBe(false);
  });
});
