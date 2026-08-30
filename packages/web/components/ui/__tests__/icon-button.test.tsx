import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { Menu } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { IconButton } from "@/components/ui/icon-button";

describe("IconButton", () => {
  it("renders a button with type=button and the accessible name", () => {
    render(<IconButton label="Open menu" icon={Menu} onClick={() => {}} />);
    const btn = screen.getByRole("button", { name: "Open menu" });
    expect(btn).toHaveAttribute("type", "button");
  });

  it("forwards onClick", async () => {
    const onClick = vi.fn();
    render(<IconButton label="Close" icon={Menu} onClick={onClick} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and exposes aria-disabled when disabled", () => {
    render(<IconButton label="Refresh" icon={Menu} onClick={() => {}} disabled />);
    const btn = screen.getByRole("button", { name: "Refresh" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-disabled", "true");
  });

  it("hides the icon behind an aria-hidden spinner and sets aria-busy while loading", () => {
    const { container } = render(
      <IconButton label="Save" icon={Menu} onClick={() => {}} loading />,
    );
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });

  it("exposes an optional advisory title without changing the accessible name", () => {
    render(<IconButton label="Quick capture" icon={Menu} title="Quick capture (Ctrl/⌘+Shift+U)" />);
    const btn = screen.getByRole("button", { name: "Quick capture" });
    expect(btn).toHaveAttribute("title", "Quick capture (Ctrl/⌘+Shift+U)");
  });

  it("applies the destructive variant class", () => {
    render(<IconButton label="Delete" icon={Menu} onClick={() => {}} variant="destructive" />);
    const btn = screen.getByRole("button", { name: "Delete" });
    expect(btn.className).toContain("destructive");
  });
});
