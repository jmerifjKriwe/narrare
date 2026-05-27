/**
 * KBFlatEditor tests — fallback flat editor for entries without template.
 *
 * Tests:
 * 1. Renders body textarea with value
 * 2. Calls onBodyChange when textarea changes
 * 3. Renders template fields when template provided
 * 4. Renders metadata key-value when no template and metadata exists
 * 5. Renders only body textarea when no template and no metadata
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBFlatEditor } from "@/components/studio/kb/KBFlatEditor";
import type { KBTemplate } from "@/lib/api/kb";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/components/studio/kb/KBTypeField", () => ({
  KBTypeField: ({ field, value }: { field: { name: string }; value: unknown }) => (
    <div data-testid={`type-field-${field.name}`}>
      {field.name}: {String(value)}
    </div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultTemplate: KBTemplate = {
  meta: {
    template_type: "location",
    template_version: "1",
    schema_version: "1",
  },
  fields: [
    {
      name: "description",
      field_type: "str",
      required: false,
      description: "Description of the location",
    },
    { name: "population", field_type: "int", required: false, description: "Population count" },
  ],
  field_groups: [],
  sections: [],
  body: "",
};

const defaultProps = {
  template: null as KBTemplate | null,
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

  it("renders template fields when template provided", () => {
    render(
      <KBFlatEditor
        {...defaultProps}
        template={defaultTemplate}
        fieldValues={{ description: "Forest", population: 100 }}
      />,
    );

    expect(screen.getByTestId("type-field-description")).toBeDefined();
    expect(screen.getByTestId("type-field-population")).toBeDefined();
  });

  it("renders metadata section header when template fields exist", () => {
    render(
      <KBFlatEditor
        {...defaultProps}
        template={defaultTemplate}
        fieldValues={{ description: "Forest" }}
      />,
    );

    expect(screen.getByText("kb.metadata")).toBeDefined();
  });

  it("renders metadata key-value display when no template but metadata exists", () => {
    render(
      <KBFlatEditor {...defaultProps} entryMetadata={{ climate: "temperate", region: "north" }} />,
    );

    // formatKey converts snake_case to Title Case
    expect(screen.getByText(/Climate:/)).toBeDefined();
    expect(screen.getByText(/Region:/)).toBeDefined();
    expect(screen.getByText("temperate")).toBeDefined();
    expect(screen.getByText("north")).toBeDefined();
  });

  it("renders only body textarea when no template and no metadata", () => {
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
