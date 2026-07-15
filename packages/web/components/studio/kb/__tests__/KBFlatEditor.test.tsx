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
import userEvent from "@testing-library/user-event";
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

const templateWithRequired: KBTemplate = {
  meta: {
    template_type: "location",
    template_version: "1",
    schema_version: "1",
  },
  fields: [
    { name: "name", field_type: "str", required: true, description: "Location name" },
    { name: "description", field_type: "str", required: true, description: "Description" },
    { name: "population", field_type: "int", required: false, description: "Population count" },
    { name: "climate", field_type: "str", required: false, description: "Climate zone" },
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

  it("always shows required fields and hides optional ones by default", () => {
    render(
      <KBFlatEditor
        {...defaultProps}
        template={templateWithRequired}
        fieldValues={{ name: "Tavern", description: "A cozy inn", population: 10, climate: "cold" }}
      />,
    );

    // Required fields are always visible.
    expect(screen.getByTestId("type-field-name")).toBeVisible();
    expect(screen.getByTestId("type-field-description")).toBeVisible();

    // Optional fields are collapsed inside the disclosure.
    expect(screen.getByTestId("type-field-population")).not.toBeVisible();
    expect(screen.getByTestId("type-field-climate")).not.toBeVisible();
  });

  it("reveals optional fields when the disclosure is expanded", async () => {
    const user = userEvent.setup();
    render(
      <KBFlatEditor
        {...defaultProps}
        template={templateWithRequired}
        fieldValues={{ name: "Tavern", population: 10 }}
      />,
    );

    expect(screen.getByTestId("type-field-population")).not.toBeVisible();

    await user.click(screen.getByText("kb.moreFields"));

    expect(screen.getByTestId("type-field-population")).toBeVisible();
    expect(screen.getByTestId("type-field-climate")).toBeVisible();
  });
});
