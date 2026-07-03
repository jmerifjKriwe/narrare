/**
 * ExtractionLoading tests — loading spinner state.
 *
 * Tests:
 * 1. Renders loading title
 * 2. Renders loading description
 * 3. Renders spinner animation
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExtractionLoading } from "@/components/studio/extraction/ExtractionLoading";

describe("ExtractionLoading", () => {
  it("renders loading title", () => {
    render(<ExtractionLoading />);

    expect(screen.getByText("aiThinking")).toBeDefined();
  });

  it("renders loading phase description", () => {
    render(<ExtractionLoading />);

    // Initial phase is "analysing"
    expect(screen.getByText("kb.extractionPhase.analysing")).toBeDefined();
  });

  // The bespoke purple title styling is now standardised onto the
  // StatusMessage primitive's semantic tokens; assert the accessible
  // loading contract (busy live region) instead.
  it("announces loading via a busy, polite status region", () => {
    render(<ExtractionLoading />);

    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region).toHaveTextContent("aiThinking");
  });

  it("renders centered layout", () => {
    const { container } = render(<ExtractionLoading />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("flex-col");
    expect(wrapper.className).toContain("items-center");
  });
});
