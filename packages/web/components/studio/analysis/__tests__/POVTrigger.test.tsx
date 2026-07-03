/**
 * POVTrigger tests — toolbar button for POVPanel.
 *
 * Tests:
 * 1. Renders trigger button with label
 * 2. Calls togglePovPanel on click
 * 3. Reflects open state as aria-pressed
 * 4. Is disabled when disabled=true
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { POVTrigger } from "@/components/studio/analysis/POVTrigger";
import { useEditorStore } from "@/lib/stores/editorStore";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("POVTrigger", () => {
  beforeEach(() => {
    useEditorStore.setState({
      rightPanel: { active: null, previous: null, requestedBy: null },
    });
  });

  it("renders trigger button with label", () => {
    render(<POVTrigger />);

    expect(screen.getByText("pov.trigger")).toBeDefined();
  });

  it("renders with aria-label from tooltip", () => {
    render(<POVTrigger />);

    expect(screen.getByLabelText("pov.triggerTooltip")).toBeDefined();
  });

  it("calls togglePovPanel on click", () => {
    render(<POVTrigger />);

    const button = screen.getByText("pov.trigger").closest("button")!;
    fireEvent.click(button);

    expect(useEditorStore.getState().rightPanel.active).toBe("pov");
  });

  it("reflects closed state as aria-pressed=false", () => {
    useEditorStore.setState({ rightPanel: { active: null, previous: null, requestedBy: null } });
    render(<POVTrigger />);

    const button = screen.getByText("pov.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects open state as aria-pressed=true", () => {
    useEditorStore.setState({
      rightPanel: { active: "pov", previous: null, requestedBy: "toolbar" },
    });
    render(<POVTrigger />);

    const button = screen.getByText("pov.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });

  it("is disabled when disabled=true", () => {
    render(<POVTrigger disabled />);

    const button = screen.getByText("pov.trigger").closest("button")!;
    expect(button.disabled).toBe(true);
  });

  it("is enabled by default", () => {
    render(<POVTrigger />);

    const button = screen.getByText("pov.trigger").closest("button")!;
    expect(button.disabled).toBe(false);
  });
});
