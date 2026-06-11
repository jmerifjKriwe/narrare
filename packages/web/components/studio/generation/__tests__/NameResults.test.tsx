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
 * 9. Save button triggers API call with correct payload
 * 10. Shows loading state during API call
 * 11. Shows success feedback on save
 * 12. Shows error feedback on failure
 * 13. Save button disabled while saving
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NameResults } from "@/components/studio/generation/NameResults";
import type { NameGenerateResponse } from "@/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockCreateEntry = vi.fn();

vi.mock("@/lib/api/kb", () => ({
  kbApi: {
    createEntry: (...args: unknown[]) => mockCreateEntry(...args),
  },
}));

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
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockCreateEntry.mockResolvedValue({ id: "entry-1", name: "Elara" });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows loading spinner when isLoading", () => {
    render(<NameResults results={null} isLoading novelId="novel-1" nameType="character" />);

    expect(screen.getByText("generation.generating")).toBeDefined();
  });

  it("shows no results message when results are null", () => {
    render(<NameResults results={null} isLoading={false} novelId="novel-1" nameType="character" />);

    expect(screen.getByText("generation.noResults")).toBeDefined();
  });

  it("shows no results message when names array is empty", () => {
    render(
      <NameResults
        results={{ names: [], count: 0, name_style: "", name_type: "" } as NameGenerateResponse}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    expect(screen.getByText("generation.noResults")).toBeDefined();
  });

  it("renders name list with correct names", () => {
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    expect(screen.getByText("Elara")).toBeDefined();
    expect(screen.getByText("Theron")).toBeDefined();
  });

  it("shows pronunciation when available", () => {
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    // Both names have pronunciation — use getAllByText
    const pronunciationLabels = screen.getAllByText(/generation\.pronunciation/);
    expect(pronunciationLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/eh-LAH-rah/)).toBeDefined();
  });

  it("shows meaning when available", () => {
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    // Both names have meaning — use getAllByText
    const meaningLabels = screen.getAllByText(/generation\.meaning/);
    expect(meaningLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/shining light/)).toBeDefined();
  });

  it("shows duplicate badge when is_duplicate=true", () => {
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    expect(screen.getByText("generation.duplicate")).toBeDefined();
  });

  it("renders Save to KB button for each name", () => {
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    const saveButtons = screen.getAllByText("generation.saveToKb");
    expect(saveButtons).toHaveLength(2);
  });

  it("renders count in header", () => {
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    expect(screen.getByText(/generation.nameGenerator.*\(2\)/)).toBeDefined();
  });

  it("save button has aria-label with name", () => {
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

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

    render(
      <NameResults results={response} isLoading={false} novelId="novel-1" nameType="character" />,
    );

    expect(screen.queryByText("generation.duplicate")).toBeNull();
  });

  // -- Save-to-KB integration tests --

  it("save button calls API with correct payload", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    const saveButton = screen.getByLabelText("generation.saveToKb: Elara");
    await user.click(saveButton);

    expect(mockCreateEntry).toHaveBeenCalledOnce();
    expect(mockCreateEntry).toHaveBeenCalledWith("novel-1", {
      entity_type: "character",
      name: "Elara",
      source: "name_generator",
      review_status: "approved",
      status: "draft",
      metadata: {
        pronunciation: "eh-LAH-rah",
        meaning: "shining light",
        name_style: "fantasy",
      },
    });
  });

  it("shows saving state during API call", async () => {
    // Make the API call hang
    mockCreateEntry.mockReturnValue(new Promise(() => {}));

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    const saveButton = screen.getByLabelText("generation.saveToKb: Elara");
    await user.click(saveButton);

    expect(screen.getByText("generation.saving")).toBeDefined();
    // Button is disabled while saving
    expect(screen.getByText("generation.saving").closest("button")).toBeDisabled();
  });

  it("shows saved feedback on successful save", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    const saveButton = screen.getByLabelText("generation.saveToKb: Elara");
    await user.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("generation.saved")).toBeDefined();
    });

    // Saved button should be disabled
    expect(screen.getByText("generation.saved").closest("button")).toBeDisabled();
  });

  it("shows error feedback on failed save", async () => {
    mockCreateEntry.mockRejectedValue(new Error("Network error"));

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <NameResults
        results={createResponse()}
        isLoading={false}
        novelId="novel-1"
        nameType="character"
      />,
    );

    const saveButton = screen.getByLabelText("generation.saveToKb: Elara");
    await user.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("generation.saveError")).toBeDefined();
    });

    // Error button should NOT be disabled — user can retry
    expect(screen.getByText("generation.saveError").closest("button")).not.toBeDisabled();
  });

  it("maps place name_type to location entity_type", async () => {
    const response = createResponse({
      names: [
        {
          name: "Aethoria",
          type: "place",
          name_style: "fantasy",
          pronunciation: null,
          meaning: "city of winds",
          is_duplicate: false,
          confidence: 0.9,
        },
      ],
      name_type: "place",
    });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<NameResults results={response} isLoading={false} novelId="novel-1" nameType="place" />);

    await user.click(screen.getByLabelText("generation.saveToKb: Aethoria"));

    expect(mockCreateEntry).toHaveBeenCalledWith(
      "novel-1",
      expect.objectContaining({
        entity_type: "location",
        name: "Aethoria",
      }),
    );
  });

  it("sends no metadata when pronunciation and meaning are null", async () => {
    const response = createResponse({
      names: [
        {
          name: "Simple",
          type: "character",
          name_style: "modern",
          pronunciation: null,
          meaning: null,
          is_duplicate: false,
          confidence: 0.9,
        },
      ],
    });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <NameResults results={response} isLoading={false} novelId="novel-1" nameType="character" />,
    );

    await user.click(screen.getByLabelText("generation.saveToKb: Simple"));

    expect(mockCreateEntry).toHaveBeenCalledWith(
      "novel-1",
      expect.objectContaining({
        metadata: {
          name_style: "modern",
        },
      }),
    );
  });
});
