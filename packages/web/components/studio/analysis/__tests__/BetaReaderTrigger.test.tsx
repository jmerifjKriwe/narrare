/**
 * BetaReaderTrigger tests — toolbar button for BetaReaderPanel.
 *
 * Tests:
 * 1. Renders trigger button with label
 * 2. Calls toggleBetaReaderPanel on click
 * 3. Reflects open state as aria-pressed
 * 4. Is disabled when disabled=true
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BetaReaderTrigger } from "@/components/studio/analysis/BetaReaderTrigger";
import { useEditorStore } from "@/lib/stores/editorStore";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BetaReaderTrigger", () => {
  beforeEach(() => {
    useEditorStore.setState({
      betaReaderPanelOpen: false,
      toggleBetaReaderPanel: vi.fn(() => {
        useEditorStore.setState((s) => ({ betaReaderPanelOpen: !s.betaReaderPanelOpen }));
      }),
    });
  });

  it("renders trigger button with label", () => {
    render(<BetaReaderTrigger />);

    expect(screen.getByText("trigger")).toBeDefined();
  });

  it("renders with aria-label from tooltip", () => {
    render(<BetaReaderTrigger />);

    expect(screen.getByLabelText("triggerTooltip")).toBeDefined();
  });

  it("calls toggleBetaReaderPanel on click", () => {
    render(<BetaReaderTrigger />);

    const button = screen.getByText("trigger").closest("button")!;
    fireEvent.click(button);

    expect(useEditorStore.getState().betaReaderPanelOpen).toBe(true);
  });

  it("reflects closed state as aria-pressed=false", () => {
    useEditorStore.setState({ betaReaderPanelOpen: false });
    render(<BetaReaderTrigger />);

    const button = screen.getByText("trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects open state as aria-pressed=true", () => {
    useEditorStore.setState({ betaReaderPanelOpen: true });
    render(<BetaReaderTrigger />);

    const button = screen.getByText("trigger").closest("button")!;
    expect(button.getAttribute("aria-pressed")).toBe("true");
  });

  it("is disabled when disabled=true", () => {
    render(<BetaReaderTrigger disabled />);

    const button = screen.getByText("trigger").closest("button")!;
    expect(button.disabled).toBe(true);
  });

  it("is enabled by default", () => {
    render(<BetaReaderTrigger />);

    const button = screen.getByText("trigger").closest("button")!;
    expect(button.disabled).toBe(false);
  });
});
