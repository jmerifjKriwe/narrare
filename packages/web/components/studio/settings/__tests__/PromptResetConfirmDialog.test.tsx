/**
 * Tests for PromptResetConfirmDialog.
 *
 * The dialog shows the current override vs. the bundled default side by
 * side and asks for destructive-action confirmation before calling
 * ``onConfirm``.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PromptResetConfirmDialog } from "@/components/studio/settings/PromptResetConfirmDialog";

describe("PromptResetConfirmDialog", () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    promptId: "writing/en/new_chapter",
    overrideContent: "my override content",
    bundledContent: "default bundled content",
    onConfirm: vi.fn(),
    pending: false,
  };

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("does not render when closed", () => {
    const { container } = render(<PromptResetConfirmDialog {...defaultProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders override and bundled content preview", () => {
    render(<PromptResetConfirmDialog {...defaultProps} />);
    expect(screen.getByText(/my override content/)).toBeInTheDocument();
    expect(screen.getByText(/default bundled content/)).toBeInTheDocument();
  });

  it("calls onConfirm when the destructive confirm button is clicked", () => {
    const onConfirm = vi.fn();
    render(<PromptResetConfirmDialog {...defaultProps} onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: "settings.prompts.resetToDefault" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("disables the confirm button while pending", () => {
    render(<PromptResetConfirmDialog {...defaultProps} pending={true} />);
    expect(screen.getByRole("button", { name: "settings.prompts.resetToDefault" })).toBeDisabled();
  });

  it("calls onOpenChange(false) when cancel is clicked", () => {
    const onOpenChange = vi.fn();
    render(<PromptResetConfirmDialog {...defaultProps} onOpenChange={onOpenChange} />);
    fireEvent.click(screen.getByRole("button", { name: "settings.prompts.cancel" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
