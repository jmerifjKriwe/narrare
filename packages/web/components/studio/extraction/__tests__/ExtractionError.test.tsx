/**
 * ExtractionError tests — error state with retry button.
 *
 * Tests:
 * 1. Renders error message
 * 2. Renders retry button
 * 3. Calls onRetry when retry button clicked
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExtractionError } from "@/components/studio/extraction/ExtractionError";

describe("ExtractionError", () => {
  it("renders error message", () => {
    render(<ExtractionError message="Network error" onRetry={vi.fn()} />);

    expect(screen.getByText("Network error")).toBeDefined();
  });

  it("renders retry button with label", () => {
    render(<ExtractionError message="Network error" onRetry={vi.fn()} />);

    expect(screen.getByText("kb.extractionRetry")).toBeDefined();
  });

  it("calls onRetry when retry button clicked", () => {
    const onRetry = vi.fn();
    render(<ExtractionError message="Network error" onRetry={onRetry} />);

    fireEvent.click(screen.getByText("kb.extractionRetry"));
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders with red error styling", () => {
    render(<ExtractionError message="Error" onRetry={vi.fn()} />);

    const messageEl = screen.getByText("Error");
    expect(messageEl.className).toContain("text-red-600");
  });
});
