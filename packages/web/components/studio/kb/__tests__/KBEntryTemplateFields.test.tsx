/**
 * KBEntryTemplateFields tests — template-driven field groups with progressive
 * disclosure (CR-AUFG-07-35).
 *
 * Tests:
 * 1. Renders the flat editor fallback when there is no template
 * 2. Required fields are always visible within a group
 * 3. Optional fields are hidden by default behind the "more fields" disclosure
 * 4. Optional fields become visible when the disclosure is expanded
 * 5. Renders no disclosure when all fields are required
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { KBEntryTemplateFields } from "@/components/studio/kb/KBEntryTemplateFields";
import type { KBTemplate } from "@/lib/api/kb";

// ---------------------------------------------------------------------------
// Mocks — keep KBMoreFields real (exercises the actual <details> behaviour),
// but stub the heavier presentational peers so we can assert field routing.
// ---------------------------------------------------------------------------

vi.mock("@/components/studio/kb/KBFieldGroup", () => ({
  KBFieldGroup: ({ title, children }: { title: string; children: React.ReactNode }) => (
    <section data-testid={`group-${title}`}>
      <h3>{title}</h3>
      {children}
    </section>
  ),
}));

vi.mock("@/components/studio/kb/KBTypeField", () => ({
  KBTypeField: ({ field }: { field: { name: string; required: boolean } }) => (
    <div data-testid={`field-${field.name}`}>
      {field.name}
      {field.required ? " (required)" : ""}
    </div>
  ),
}));

vi.mock("@/components/studio/kb/KBFlatEditor", () => ({
  KBFlatEditor: () => <div data-testid="flat-editor">flat</div>,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const templateWithOptional: KBTemplate = {
  meta: { template_type: "character", template_version: "1", schema_version: "1" },
  fields: [],
  field_groups: [
    {
      name: "basic_info",
      label_key: "",
      description_key: "",
      order: 0,
      fields: [
        { name: "full_name", field_type: "str", required: true, description: "" },
        { name: "age", field_type: "int", required: true, description: "" },
        { name: "nickname", field_type: "str", required: false, description: "" },
        { name: "hobby", field_type: "str", required: false, description: "" },
      ],
    },
  ],
  sections: [],
  body: "",
};

const templateAllRequired: KBTemplate = {
  meta: { template_type: "character", template_version: "1", schema_version: "1" },
  fields: [],
  field_groups: [
    {
      name: "basic_info",
      label_key: "",
      description_key: "",
      order: 0,
      fields: [
        { name: "full_name", field_type: "str", required: true, description: "" },
        { name: "age", field_type: "int", required: true, description: "" },
      ],
    },
  ],
  sections: [],
  body: "",
};

const defaultProps = {
  fieldValues: {} as Record<string, unknown>,
  entryMetadata: {} as Record<string, unknown>,
  body: "",
  onFieldChange: vi.fn(),
  onBodyChange: vi.fn(),
  label: (_key: string, fallback: string) => fallback,
  formatKey: (key: string) => key,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBEntryTemplateFields", () => {
  it("renders the flat editor fallback when there is no template", () => {
    render(<KBEntryTemplateFields {...defaultProps} template={null} />);

    expect(screen.getByTestId("flat-editor")).toBeDefined();
  });

  it("always shows required fields within a group", () => {
    render(<KBEntryTemplateFields {...defaultProps} template={templateWithOptional} />);

    expect(screen.getByTestId("field-full_name")).toBeVisible();
    expect(screen.getByTestId("field-age")).toBeVisible();
  });

  it("hides optional fields behind the disclosure by default", () => {
    render(<KBEntryTemplateFields {...defaultProps} template={templateWithOptional} />);

    // Optional fields exist in the DOM but are collapsed inside <details>.
    expect(screen.getByTestId("field-nickname")).not.toBeVisible();
    expect(screen.getByTestId("field-hobby")).not.toBeVisible();
  });

  it("reveals optional fields when the disclosure is expanded", async () => {
    const user = userEvent.setup();
    render(<KBEntryTemplateFields {...defaultProps} template={templateWithOptional} />);

    expect(screen.getByTestId("field-nickname")).not.toBeVisible();

    await user.click(screen.getByText("kb.moreFields"));

    expect(screen.getByTestId("field-nickname")).toBeVisible();
    expect(screen.getByTestId("field-hobby")).toBeVisible();
  });

  it("renders no disclosure when all fields are required", () => {
    render(<KBEntryTemplateFields {...defaultProps} template={templateAllRequired} />);

    expect(screen.getByTestId("field-full_name")).toBeVisible();
    expect(screen.getByTestId("field-age")).toBeVisible();
    expect(screen.queryByText("kb.moreFields")).toBeNull();
  });
});
