import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VolumeFormFields } from "@/components/studio/VolumeCard";

describe("VolumeFormFields", () => {
  const defaultProps = {
    title: "Test Title",
    subtitle: "",
    description: "",
    target: "",
    onTitleChange: vi.fn(),
    onSubtitleChange: vi.fn(),
    onDescriptionChange: vi.fn(),
    onTargetChange: vi.fn(),
    onSubmit: vi.fn(),
    onCancel: vi.fn(),
    submitLabel: "Save",
    isPending: false,
  };

  it("renders form labels", () => {
    render(<VolumeFormFields {...defaultProps} />);
    expect(screen.getByText(/volumes.titleLabel/)).toBeDefined();
    expect(screen.getByText("volumes.subtitleLabel")).toBeDefined();
    expect(screen.getByText("volumes.descriptionLabel")).toBeDefined();
    expect(screen.getByText("volumes.wordCountTargetLabel")).toBeDefined();
  });

  it("renders submit and cancel buttons", () => {
    render(<VolumeFormFields {...defaultProps} submitLabel="Create" />);
    expect(screen.getByText("Create")).toBeDefined();
    expect(screen.getByText("volumes.cancel")).toBeDefined();
  });

  it("calls onTitleChange when title input changes", () => {
    const onTitleChange = vi.fn();
    render(<VolumeFormFields {...defaultProps} onTitleChange={onTitleChange} />);
    fireEvent.change(screen.getByLabelText("volumes.titleLabel", { exact: false }), {
      target: { value: "New Volume" },
    });
    expect(onTitleChange).toHaveBeenCalledWith("New Volume");
  });

  it("calls onCancel when cancel is clicked", () => {
    const onCancel = vi.fn();
    render(<VolumeFormFields {...defaultProps} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("volumes.cancel"));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("calls onSubmit when submit is clicked", () => {
    const onSubmit = vi.fn();
    render(<VolumeFormFields {...defaultProps} onSubmit={onSubmit} title="My Title" />);
    const allButtons = screen.getAllByRole("button");
    fireEvent.click(allButtons[1]);
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("disables submit button when isPending", () => {
    const { container } = render(<VolumeFormFields {...defaultProps} isPending={true} title="Title" />);
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(2);
    // Second button is the submit button
    expect(buttons[1].disabled).toBe(true);
  });

  it("disables submit when title is empty", () => {
    render(<VolumeFormFields {...defaultProps} title="" />);
    // Button should exist and be disabled - button text is still "Save" when not pending
    const submitButton = screen.getByText("Save").closest("button");
    expect(submitButton).not.toBeNull();
    expect(submitButton!.disabled).toBe(true);
  });
});
