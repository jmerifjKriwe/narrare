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

  // The bespoke green palette is now standardised onto the StatusMessage
  // primitive's semantic tokens; assert the accessible contract instead.
  it("announces success via a polite status region", () => {
    render(<ExtractionDone />);

    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent("kb.extractionAppliedTitle");
  });
});
