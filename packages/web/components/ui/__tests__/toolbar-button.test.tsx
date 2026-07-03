import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { Bold } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { ToolbarButton } from "@/components/ui/toolbar-button";

describe("ToolbarButton", () => {
  it("renders type=button with an accessible name", () => {
    render(<ToolbarButton label="Bold" icon={Bold} onClick={() => {}} />);
    const btn = screen.getByRole("button", { name: "Bold" });
    expect(btn).toHaveAttribute("type", "button");
  });

  it("reflects aria-pressed when active", () => {
    render(<ToolbarButton label="Bold" icon={Bold} active onClick={() => {}} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the visible label when showLabel is true", () => {
    render(<ToolbarButton label="Bold" icon={Bold} showLabel onClick={() => {}} />);
    // The label text is rendered visibly (and also used as accessible name).
    expect(screen.getByText("Bold")).toBeDefined();
  });

  it("forwards onClick and supports loading state", async () => {
    const onClick = vi.fn();
    render(<ToolbarButton label="Run" icon={Bold} loading onClick={onClick} />);
    const btn = screen.getByRole("button", { name: "Run" });
    expect(btn).toHaveAttribute("aria-busy", "true");
    // Loading disables interaction.
    expect(btn).toBeDisabled();
  });

  it("forwards onClick when clicked", async () => {
    const onClick = vi.fn();
    render(<ToolbarButton label="Bold" icon={Bold} onClick={onClick} />);
    await userEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
