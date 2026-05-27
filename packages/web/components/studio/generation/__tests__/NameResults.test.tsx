/**
 * NameResults tests — name generation results display.
 *
 * Tests:
 * 1. Shows loading spinner when isLoading
 * 2. Shows no results message when results are null
 * 3. Shows no results message when names array is empty
 * 4. Renders name list with correct names
 * 5. Shows pronunciation when available
 * 6. Shows meaning when available
 * 7. Shows duplicate badge when is_duplicate=true
 * 8. Renders Save to KB button for each name
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NameResults } from "@/components/studio/generation/NameResults";
import type { NameGenerateResponse } from "@/types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createResponse(overrides: Partial<NameGenerateResponse> = {}): NameGenerateResponse {
  return {
    names: [
      {
        name: "Elara",
        type: "character",
        name_style: "fantasy",
        pronunciation: "eh-LAH-rah",
        meaning: "shining light",
        is_duplicate: false,
        confidence: 0.85,
      },
      {
        name: "Theron",
        type: "character",
        name_style: "fantasy",
        pronunciation: "THEH-ron",
        meaning: "hunter",
        is_duplicate: true,
        confidence: 0.75,
      },
    ],
    count: 2,
    name_style: "fantasy",
    name_type: "character",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("NameResults", () => {
  it("shows loading spinner when isLoading", () => {
    render(<NameResults results={null} isLoading />);

    expect(screen.getByText("generation.generating")).toBeDefined();
  });

  it("shows no results message when results are null", () => {
    render(<NameResults results={null} isLoading={false} />);

    expect(screen.getByText("generation.noResults")).toBeDefined();
  });

  it("shows no results message when names array is empty", () => {
    render(
      <NameResults
        results={{ names: [], count: 0, name_style: "", name_type: "" } as NameGenerateResponse}
        isLoading={false}
      />,
    );

    expect(screen.getByText("generation.noResults")).toBeDefined();
  });

  it("renders name list with correct names", () => {
    render(<NameResults results={createResponse()} isLoading={false} />);

    expect(screen.getByText("Elara")).toBeDefined();
    expect(screen.getByText("Theron")).toBeDefined();
  });

  it("shows pronunciation when available", () => {
    render(<NameResults results={createResponse()} isLoading={false} />);

    // Both names have pronunciation — use getAllByText
    const pronunciationLabels = screen.getAllByText(/generation\.pronunciation/);
    expect(pronunciationLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/eh-LAH-rah/)).toBeDefined();
  });

  it("shows meaning when available", () => {
    render(<NameResults results={createResponse()} isLoading={false} />);

    // Both names have meaning — use getAllByText
    const meaningLabels = screen.getAllByText(/generation\.meaning/);
    expect(meaningLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/shining light/)).toBeDefined();
  });

  it("shows duplicate badge when is_duplicate=true", () => {
    render(<NameResults results={createResponse()} isLoading={false} />);

    expect(screen.getByText("generation.duplicate")).toBeDefined();
  });

  it("renders Save to KB button for each name", () => {
    render(<NameResults results={createResponse()} isLoading={false} />);

    const saveButtons = screen.getAllByText("generation.saveToKb");
    expect(saveButtons).toHaveLength(2);
  });

  it("renders count in header", () => {
    render(<NameResults results={createResponse()} isLoading={false} />);

    expect(screen.getByText(/generation.nameGenerator.*\(2\)/)).toBeDefined();
  });

  it("save button has aria-label with name", () => {
    render(<NameResults results={createResponse()} isLoading={false} />);

    expect(screen.getByLabelText("generation.saveToKb: Elara")).toBeDefined();
    expect(screen.getByLabelText("generation.saveToKb: Theron")).toBeDefined();
  });

  it("does not show duplicate badge for non-duplicate names", () => {
    const response = createResponse({
      names: [
        {
          name: "Elara",
          type: "character",
          name_style: "fantasy",
          pronunciation: null,
          meaning: null,
          is_duplicate: false,
          confidence: 0.9,
        },
      ],
    });

    render(<NameResults results={response} isLoading={false} />);

    expect(screen.queryByText("generation.duplicate")).toBeNull();
  });
});
