/**
 * KBFlatEditor tests — flat editor for KB entry detail.
 *
 * Since B04 the template endpoint returns `TemplateDetailResponse` (a YAML
 * prompt template), not a field schema, so the editor always renders the
 * metadata key-value display + body textarea.
 *
 * Tests:
 * 1. Renders body textarea with value
 * 2. Calls onBodyChange when textarea changes
 * 3. Renders body label and placeholder
 * 4. Renders metadata key-value when metadata exists
 * 5. Renders only body textarea when no metadata
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBFlatEditor } from "@/components/studio/kb/KBFlatEditor";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  fieldValues: {} as Record<string, unknown>,
  body: "A dark forest with ancient trees.",
  entryMetadata: {} as Record<string, unknown>,
  onFieldChange: vi.fn(),
  onBodyChange: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBFlatEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders body textarea with value", () => {
    render(<KBFlatEditor {...defaultProps} />);

    const textarea = screen.getByDisplayValue("A dark forest with ancient trees.");
    expect(textarea).toBeDefined();
  });

  it("calls onBodyChange when textarea changes", () => {
    const onBodyChange = vi.fn();
    render(<KBFlatEditor {...defaultProps} onBodyChange={onBodyChange} />);

    const textarea = screen.getByDisplayValue("A dark forest with ancient trees.");
    fireEvent.change(textarea, { target: { value: "A bright meadow." } });

    expect(onBodyChange).toHaveBeenCalledWith("A bright meadow.");
  });

  it("renders body label", () => {
    render(<KBFlatEditor {...defaultProps} />);

    expect(screen.getByText("kb.body")).toBeDefined();
  });

  it("renders body placeholder", () => {
    render(<KBFlatEditor {...defaultProps} body="" />);

    expect(screen.getByPlaceholderText("kb.bodyPlaceholder")).toBeDefined();
  });

  it("renders metadata key-value display when metadata exists", () => {
    render(
      <KBFlatEditor {...defaultProps} entryMetadata={{ climate: "temperate", region: "north" }} />,
    );

    // formatKey converts snake_case to Title Case
    expect(screen.getByText(/Climate:/)).toBeDefined();
    expect(screen.getByText(/Region:/)).toBeDefined();
    expect(screen.getByText("temperate")).toBeDefined();
    expect(screen.getByText("north")).toBeDefined();
  });

  it("renders only body textarea when no metadata", () => {
    render(<KBFlatEditor {...defaultProps} />);

    expect(screen.getByDisplayValue("A dark forest with ancient trees.")).toBeDefined();
    // Should not show metadata section
    expect(screen.queryByText("kb.metadata")).toBeNull();
  });

  it("renders textarea with correct id", () => {
    render(<KBFlatEditor {...defaultProps} />);

    const textarea = document.getElementById("entry-body");
    expect(textarea).toBeDefined();
  });
});
