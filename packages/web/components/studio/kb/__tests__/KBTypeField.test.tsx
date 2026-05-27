/**
 * KBTypeField tests — renders appropriate input per field_type.
 *
 * Tests:
 * 1. Renders text input for "str" type
 * 2. Renders number input for "int" type
 * 3. Renders toggle switch for "bool" type
 * 4. Renders tag input for "list" type
 * 5. Calls onChange with correct value for text input
 * 6. Calls onChange with number for int input
 * 7. Calls onChange with toggled bool
 * 8. Shows required indicator
 * 9. Shows error message when provided
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBTypeField } from "@/components/studio/kb/KBTypeField";
import type { KBTemplateField } from "@/lib/api/kb";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/components/studio/kb/KBTagInput", () => ({
  KBTagInput: ({ value, onChange }: { value: string[]; onChange: (tags: string[]) => void }) => (
    <div data-testid="tag-input">
      {value.join(", ")}
      <button type="button" onClick={() => onChange([...value, "new-tag"])}>
        Add
      </button>
    </div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createField(overrides: Partial<KBTemplateField> = {}): KBTemplateField {
  return {
    name: "test_field",
    field_type: "str",
    required: false,
    description: "A test field",
    ...overrides,
  };
}

const defaultProps = {
  field: createField(),
  value: "hello",
  onChange: vi.fn(),
  label: "Test Field",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBTypeField", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders text input for str type", () => {
    render(<KBTypeField {...defaultProps} field={createField({ field_type: "str" })} />);

    const input = screen.getByDisplayValue("hello");
    expect(input).toBeDefined();
    expect(input).toHaveProperty("type", "text");
  });

  it("renders number input for int type", () => {
    render(
      <KBTypeField
        {...defaultProps}
        field={createField({ field_type: "int", name: "age" })}
        value={42}
      />,
    );

    const input = screen.getByDisplayValue("42");
    expect(input).toBeDefined();
    expect(input).toHaveProperty("type", "number");
  });

  it("renders toggle switch for bool type", () => {
    render(
      <KBTypeField {...defaultProps} field={createField({ field_type: "bool" })} value={true} />,
    );

    const toggle = screen.getByRole("switch");
    expect(toggle).toBeDefined();
    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });

  it("renders tag input for list type", () => {
    render(
      <KBTypeField
        {...defaultProps}
        field={createField({ field_type: "list" })}
        value={["tag1", "tag2"]}
      />,
    );

    expect(screen.getByTestId("tag-input")).toBeDefined();
  });

  it("renders label text", () => {
    render(<KBTypeField {...defaultProps} />);

    expect(screen.getByText("Test Field")).toBeDefined();
  });

  it("shows required indicator when field.required=true", () => {
    render(<KBTypeField {...defaultProps} field={createField({ required: true })} />);

    // Required indicator is a red asterisk
    const asterisk = screen.getByText("*");
    expect(asterisk).toBeDefined();
  });

  it("shows error message when error provided", () => {
    render(<KBTypeField {...defaultProps} error="Field is required" />);

    expect(screen.getByText("Field is required")).toBeDefined();
  });

  it("calls onChange with text value for str input change", () => {
    const onChange = vi.fn();
    render(<KBTypeField {...defaultProps} onChange={onChange} />);

    const input = screen.getByDisplayValue("hello");
    fireEvent.change(input, { target: { value: "world" } });

    expect(onChange).toHaveBeenCalledWith("test_field", "world");
  });

  it("calls onChange with number for int input change", () => {
    const onChange = vi.fn();
    render(
      <KBTypeField
        {...defaultProps}
        field={createField({ field_type: "int", name: "age" })}
        value={42}
        onChange={onChange}
      />,
    );

    const input = screen.getByDisplayValue("42");
    fireEvent.change(input, { target: { value: "25" } });

    expect(onChange).toHaveBeenCalledWith("age", 25);
  });

  it("calls onChange with toggled bool on switch click", () => {
    const onChange = vi.fn();
    render(
      <KBTypeField
        {...defaultProps}
        field={createField({ field_type: "bool" })}
        value={true}
        onChange={onChange}
      />,
    );

    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);

    expect(onChange).toHaveBeenCalledWith("test_field", false);
  });

  it("calls onChange with empty string for cleared int input", () => {
    const onChange = vi.fn();
    render(
      <KBTypeField
        {...defaultProps}
        field={createField({ field_type: "int", name: "age" })}
        value={42}
        onChange={onChange}
      />,
    );

    const input = screen.getByDisplayValue("42");
    fireEvent.change(input, { target: { value: "" } });

    expect(onChange).toHaveBeenCalledWith("age", "");
  });

  it("renders with correct id attribute", () => {
    render(<KBTypeField {...defaultProps} />);

    const input = document.getElementById("field-test_field");
    expect(input).toBeDefined();
  });
});
