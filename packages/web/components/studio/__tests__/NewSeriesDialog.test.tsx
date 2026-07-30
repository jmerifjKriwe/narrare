/**
 * NewSeriesDialog tests — minimal accessible create-series dialog
 * (Spec 1, Slice 4, Task 4.5).
 *
 * The dialog is a basic Spec-1 create flow: a single title field with
 * Create / Cancel actions. It is intentionally dependency-free (no
 * @radix-ui/react-dialog) and uses role="dialog" semantics. i18n keys live
 * under studio.dashboard.series.* and are added in Task 4.9; the centralized
 * setupTests mock returns the keys verbatim, so assertions check for keys.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NewSeriesDialog } from "@/components/studio/NewSeriesDialog";

describe("NewSeriesDialog", () => {
  it("renders the title input when open", () => {
    render(<NewSeriesDialog open={true} onOpenChange={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.getByRole("textbox")).toBeDefined();
  });

  it("renders nothing when closed", () => {
    render(<NewSeriesDialog open={false} onOpenChange={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("disables the create button until a title is entered", () => {
    render(<NewSeriesDialog open={true} onOpenChange={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.getByTestId("new-series-create")).toHaveProperty("disabled", true);
  });

  it("calls onCreate with the trimmed title when Create is clicked", () => {
    const onCreate = vi.fn();
    render(<NewSeriesDialog open={true} onOpenChange={vi.fn()} onCreate={onCreate} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "  The Expanse  " } });
    fireEvent.click(screen.getByTestId("new-series-create"));
    expect(onCreate).toHaveBeenCalledWith("The Expanse");
  });

  it("calls onOpenChange(false) when Cancel is clicked", () => {
    const onOpenChange = vi.fn();
    render(<NewSeriesDialog open={true} onOpenChange={onOpenChange} onCreate={vi.fn()} />);
    fireEvent.click(screen.getByTestId("new-series-cancel"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
