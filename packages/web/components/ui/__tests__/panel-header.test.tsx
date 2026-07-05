import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { Shield } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { PanelHeader } from "@/components/ui/panel-header";

describe("PanelHeader", () => {
  it("renders the title as a heading with a stable id", () => {
    render(<PanelHeader title="Consistency" titleId="h-consistency" />);
    const heading = screen.getByRole("heading", { name: "Consistency" });
    expect(heading).toHaveAttribute("id", "h-consistency");
  });

  it("renders a leading icon aria-hidden", () => {
    const { container } = render(<PanelHeader title="Consistency" icon={Shield} />);
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("renders a status slot and actions slot", () => {
    render(
      <PanelHeader
        title="Consistency"
        statusSlot={<span>Running…</span>}
        actions={<button type="button">Refresh</button>}
      />,
    );
    expect(screen.getByText("Running…")).toBeDefined();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeDefined();
  });

  it("renders an IconButton close control that calls onClose", async () => {
    const onClose = vi.fn();
    render(<PanelHeader title="Consistency" closeLabel="Close" onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
