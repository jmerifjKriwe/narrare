/**
 * PanelTabs primitive tests (Task 6).
 *
 * Covers the ARIA tabs pattern (spec §5.4): tablist/tab/tabpanel roles,
 * aria-selected, aria-controls ↔ aria-labelledby linking, roving tabindex
 * via click and arrow-key navigation, and the optional leading icon. The
 * component is controlled — the caller binds `value`/`onValueChange` (to
 * `useUrlParam` or any other state source). No hardcoded user-facing strings
 * inside the primitive: labels and `ariaLabel` are required resolved-i18n
 * props (RULE-16).
 */

import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { LayoutGrid } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { PanelTabs } from "@/components/ui/panel-tabs";

const TABS = [
  { id: "general", label: "General", content: <p>General content</p> },
  { id: "ai", label: "AI", content: <p>AI content</p> },
];

describe("PanelTabs", () => {
  it("renders a tablist with the given aria-label and tab roles", () => {
    render(
      <PanelTabs
        tabs={TABS}
        value="general"
        onValueChange={() => {}}
        ariaLabel="Settings sections"
      />,
    );
    expect(screen.getByRole("tablist", { name: "Settings sections" })).toBeDefined();
    expect(screen.getAllByRole("tab")).toHaveLength(2);
  });

  it("marks only the active tab aria-selected and renders its panel", () => {
    render(<PanelTabs tabs={TABS} value="ai" onValueChange={() => {}} ariaLabel="x" />);
    const [general, ai] = screen.getAllByRole("tab");
    expect(general).toHaveAttribute("aria-selected", "false");
    expect(ai).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("AI content")).toBeDefined();
  });

  it("links tab and panel via aria-controls / aria-labelledby", () => {
    render(<PanelTabs tabs={TABS} value="general" onValueChange={() => {}} ariaLabel="x" />);
    const tab = screen.getAllByRole("tab")[0];
    const controlsId = tab.getAttribute("aria-controls");
    expect(controlsId).toBeTruthy();
    const panel = screen.getByRole("tabpanel");
    expect(panel.getAttribute("aria-labelledby")).toBe(tab.getAttribute("id"));
  });

  it("calls onValueChange on click", async () => {
    const onValueChange = vi.fn();
    render(<PanelTabs tabs={TABS} value="general" onValueChange={onValueChange} ariaLabel="x" />);
    await userEvent.click(screen.getAllByRole("tab")[1]);
    expect(onValueChange).toHaveBeenCalledWith("ai");
  });

  // PanelTabs is controlled: navigation is computed from the current `value`,
  // so each keyboard case renders with the appropriate starting value.
  it("activates the next tab on ArrowRight", async () => {
    const onValueChange = vi.fn();
    render(<PanelTabs tabs={TABS} value="general" onValueChange={onValueChange} ariaLabel="x" />);
    screen.getAllByRole("tab")[0].focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onValueChange).toHaveBeenLastCalledWith("ai");
  });

  it("wraps from the last tab to the first on ArrowRight", async () => {
    const onValueChange = vi.fn();
    render(<PanelTabs tabs={TABS} value="ai" onValueChange={onValueChange} ariaLabel="x" />);
    screen.getAllByRole("tab")[1].focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onValueChange).toHaveBeenLastCalledWith("general");
  });

  it("moves to the first tab on Home", async () => {
    const onValueChange = vi.fn();
    render(<PanelTabs tabs={TABS} value="ai" onValueChange={onValueChange} ariaLabel="x" />);
    screen.getAllByRole("tab")[1].focus();
    await userEvent.keyboard("{Home}");
    expect(onValueChange).toHaveBeenLastCalledWith("general");
  });

  it("moves to the last tab on End", async () => {
    const onValueChange = vi.fn();
    render(<PanelTabs tabs={TABS} value="general" onValueChange={onValueChange} ariaLabel="x" />);
    screen.getAllByRole("tab")[0].focus();
    await userEvent.keyboard("{End}");
    expect(onValueChange).toHaveBeenLastCalledWith("ai");
  });

  it("renders an optional leading icon as aria-hidden when provided", () => {
    const { container } = render(
      <PanelTabs
        tabs={[{ id: "a", label: "A", icon: LayoutGrid, content: <p>a</p> }]}
        value="a"
        onValueChange={() => {}}
        ariaLabel="x"
      />,
    );
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });
});
