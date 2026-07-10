/**
 * ConfirmDialog tests — accessible confirmation dialog.
 *
 * Tests:
 * 1. Does not render content when open=false
 * 2. Renders title and description when open=true
 * 3. Cancel button calls onOpenChange(false)
 * 4. Confirm button calls onConfirm and onOpenChange(false)
 * 5. Destructive variant renders destructive styling
 * 6. Custom labels override defaults
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  title: "Confirm Action",
  description: "This will permanently delete the item.",
  onConfirm: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ConfirmDialog", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders title and description when open", () => {
    render(<ConfirmDialog {...defaultProps} />);
    expect(screen.getByText("Confirm Action")).toBeTruthy();
    expect(screen.getByText("This will permanently delete the item.")).toBeTruthy();
  });

  it("does not render visible content when closed", () => {
    render(<ConfirmDialog {...defaultProps} open={false} />);
    expect(screen.queryByText("Confirm Action")).toBeNull();
  });

  it("calls onConfirm when confirm button is clicked", () => {
    render(<ConfirmDialog {...defaultProps} />);
    // Target by stable testid — immune to i18n mock return values
    fireEvent.click(screen.getByTestId("confirm-dialog-confirm"));
    expect(defaultProps.onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onOpenChange(false) when cancel button is clicked", () => {
    const onOpenChange = vi.fn();
    render(<ConfirmDialog {...defaultProps} onOpenChange={onOpenChange} />);
    // Target by stable testid — immune to i18n mock return values
    fireEvent.click(screen.getByTestId("confirm-dialog-cancel"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("renders custom confirm label", () => {
    render(<ConfirmDialog {...defaultProps} confirmLabel="Delete forever" />);
    expect(screen.getByText("Delete forever")).toBeTruthy();
  });

  it("renders custom cancel label", () => {
    render(<ConfirmDialog {...defaultProps} cancelLabel="Go back" />);
    expect(screen.getByText("Go back")).toBeTruthy();
  });

  it("applies destructive variant styling to confirm button", () => {
    render(<ConfirmDialog {...defaultProps} variant="destructive" />);
    const confirmBtn = screen.getByTestId("confirm-dialog-confirm");
    // The destructive variant adds bg-destructive class
    expect(confirmBtn.className).toContain("bg-destructive");
  });

  it("applies default variant styling to confirm button", () => {
    render(<ConfirmDialog {...defaultProps} variant="default" />);
    const confirmBtn = screen.getByTestId("confirm-dialog-confirm");
    expect(confirmBtn.className).toContain("bg-primary");
  });
});
