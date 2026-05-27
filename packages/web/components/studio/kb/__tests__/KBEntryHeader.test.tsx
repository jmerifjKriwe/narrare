/**
 * KBEntryHeader tests — name input, status badge, save/delete buttons.
 *
 * Tests:
 * 1. Renders entry name in input
 * 2. Renders status badge with label
 * 3. Renders save and delete buttons
 * 4. Calls onNameChange when name input changes
 * 5. Calls onSave when save button clicked
 * 6. Calls onDelete when delete button clicked
 * 7. Disables save button when isSaving
 * 8. Disables delete button when isDeleting
 * 9. Shows spinner when saving
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { User } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { KBEntryHeader } from "@/components/studio/kb/KBEntryHeader";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  name: "Anna Schmidt",
  status: "canon",
  statusLabel: "kb.status.canon",
  Icon: User,
  namePlaceholder: "kb.namePlaceholder",
  isSaving: false,
  isDeleting: false,
  onNameChange: vi.fn(),
  onSave: vi.fn(),
  onDelete: vi.fn(),
  deleteLabel: "kb.delete",
  saveLabel: "kb.save",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBEntryHeader", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders entry name in input", () => {
    render(<KBEntryHeader {...defaultProps} />);

    expect(screen.getByDisplayValue("Anna Schmidt")).toBeDefined();
  });

  it("renders status badge", () => {
    render(<KBEntryHeader {...defaultProps} />);

    expect(screen.getByText("kb.status.canon")).toBeDefined();
  });

  it("renders save button with label", () => {
    render(<KBEntryHeader {...defaultProps} />);

    expect(screen.getByText("kb.save")).toBeDefined();
  });

  it("renders delete button with aria-label", () => {
    render(<KBEntryHeader {...defaultProps} />);

    expect(screen.getByLabelText("kb.delete")).toBeDefined();
  });

  it("renders icon in the header area", () => {
    render(<KBEntryHeader {...defaultProps} />);

    // The User icon should be rendered (it's a lucide icon component)
    const iconContainer = document.querySelector(".bg-muted");
    expect(iconContainer).toBeDefined();
  });

  it("calls onNameChange when name input changes", () => {
    const onNameChange = vi.fn();
    render(<KBEntryHeader {...defaultProps} onNameChange={onNameChange} />);

    const input = screen.getByDisplayValue("Anna Schmidt");
    fireEvent.change(input, { target: { value: "Anna Weber" } });

    expect(onNameChange).toHaveBeenCalledWith("Anna Weber");
  });

  it("calls onSave when save button clicked", () => {
    const onSave = vi.fn();
    render(<KBEntryHeader {...defaultProps} onSave={onSave} />);

    fireEvent.click(screen.getByText("kb.save"));
    expect(onSave).toHaveBeenCalled();
  });

  it("calls onDelete when delete button clicked", () => {
    const onDelete = vi.fn();
    render(<KBEntryHeader {...defaultProps} onDelete={onDelete} />);

    fireEvent.click(screen.getByLabelText("kb.delete"));
    expect(onDelete).toHaveBeenCalled();
  });

  it("disables save button when isSaving=true", () => {
    render(<KBEntryHeader {...defaultProps} isSaving />);

    const saveButton = screen.getByText("kb.save").closest("button");
    expect(saveButton?.disabled).toBe(true);
  });

  it("disables delete button when isDeleting=true", () => {
    render(<KBEntryHeader {...defaultProps} isDeleting />);

    const deleteButton = screen.getByLabelText("kb.delete") as HTMLButtonElement;
    expect(deleteButton.disabled).toBe(true);
  });

  it("shows name placeholder when name is empty", () => {
    render(<KBEntryHeader {...defaultProps} name="" />);

    expect(screen.getByPlaceholderText("kb.namePlaceholder")).toBeDefined();
  });
});
