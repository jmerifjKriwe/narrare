/**
 * ExtractionDone tests — success state after extraction.
 *
 * Tests:
 * 1. Renders success title
 * 2. Renders success description
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExtractionDone } from "@/components/studio/extraction/ExtractionDone";

describe("ExtractionDone", () => {
  it("renders success title", () => {
    render(<ExtractionDone />);

    expect(screen.getByText("kb.extractionAppliedTitle")).toBeDefined();
  });

  it("renders success description", () => {
    render(<ExtractionDone />);

    expect(screen.getByText("kb.extractionAppliedDesc")).toBeDefined();
  });

  it("renders with green text styling", () => {
    render(<ExtractionDone />);

    const title = screen.getByText("kb.extractionAppliedTitle");
    expect(title.className).toContain("text-green-600");
  });
});
