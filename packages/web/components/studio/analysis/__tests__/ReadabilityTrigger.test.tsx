/**
 * ReadabilityTrigger tests — toolbar button for ReadabilityPanel.
 *
 * Tests:
 * 1. Renders trigger button with label
 * 2. Calls toggleReadabilityPanel on click
 * 3. Reflects open state as aria-pressed
 * 4. Is disabled when disabled=true
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReadabilityTrigger } from "@/components/studio/analysis/ReadabilityTrigger";
import { useEditorStore } from "@/lib/stores/editorStore";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ReadabilityTrigger", () => {
  beforeEach(() => {
    useEditorStore.setState({
      readabilityPanelOpen: false,
      toggleReadabilityPanel: vi.fn(() => {
        useEditorStore.setState((s) => ({ readabilityPanelOpen: !s.readabilityPanelOpen }));
      }),
    });
  });

  it("renders trigger button with label", () => {
    render(<ReadabilityTrigger />);

    expect(screen.getByText("readability.trigger")).toBeDefined();
  });

  it("renders with aria-label from tooltip", () => {
    render(<ReadabilityTrigger />);

    expect(screen.getByLabelText("readability.triggerTooltip")).toBeDefined();
  });

  it("calls toggleReadabilityPanel on click", () => {
    render(<ReadabilityTrigger />);

    const button = screen.getByText("readability.trigger").closest("button")!;
    fireEvent.click(button);

    expect(useEditorStore.getState().readabilityPanelOpen).toBe(true);
  });

  it("reflects closed state as aria-pressed=false", () => {
    useEditorStore.setState({ readabilityPanelOpen: false });
    render(<ReadabilityTrigger />);

    const button = screen.getByText("readability.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects open state as aria-pressed=true", () => {
    useEditorStore.setState({ readabilityPanelOpen: true });
    render(<ReadabilityTrigger />);

    const button = screen.getByText("readability.trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });

  it("is disabled when disabled=true", () => {
    render(<ReadabilityTrigger disabled />);

    const button = screen.getByText("readability.trigger").closest("button")!;
    expect(button.disabled).toBe(true);
  });

  it("is enabled by default", () => {
    render(<ReadabilityTrigger />);

    const button = screen.getByText("readability.trigger").closest("button")!;
    expect(button.disabled).toBe(false);
  });
});
