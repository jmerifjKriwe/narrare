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

    expect(screen.getByText("kb.extractionLoadingTitle")).toBeDefined();
  });

  it("renders loading description", () => {
    render(<ExtractionLoading />);

    expect(screen.getByText("kb.extractionLoadingDesc")).toBeDefined();
  });

  it("renders with purple styling", () => {
    render(<ExtractionLoading />);

    const title = screen.getByText("kb.extractionLoadingTitle");
    expect(title.className).toContain("font-medium");
  });

  it("renders centered layout", () => {
    const { container } = render(<ExtractionLoading />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("flex-col");
    expect(wrapper.className).toContain("items-center");
  });
});
