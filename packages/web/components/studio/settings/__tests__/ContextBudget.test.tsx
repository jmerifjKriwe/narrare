import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ContextBudget } from "@/components/studio/settings/ContextBudget";
import type { ContextTier } from "@/types";

const balancedPercentages: Record<ContextTier, number> = {
  immediate: 30,
  recent: 20,
  kb_referenced: 25,
  kb_suggested: 15,
  pinned: 10,
};

const unevenPercentages: Record<ContextTier, number> = {
  immediate: 50,
  recent: 20,
  kb_referenced: 15,
  kb_suggested: 10,
  pinned: 5,
};

describe("ContextBudget", () => {
  it("renders all 5 tier sliders", () => {
    render(<ContextBudget percentages={balancedPercentages} onChange={vi.fn()} />);

    const tierLabels = [
      "settings.ai.contextBudget.tierImmediate",
      "settings.ai.contextBudget.tierRecent",
      "settings.ai.contextBudget.tierKbReferenced",
      "settings.ai.contextBudget.tierKbSuggested",
      "settings.ai.contextBudget.tierPinned",
    ];
    for (const label of tierLabels) {
      expect(screen.getByText(label)).toBeDefined();
    }
  });

  it("renders pie chart SVG with path elements", () => {
    render(<ContextBudget percentages={unevenPercentages} onChange={vi.fn()} />);

    const svg = document.querySelector("svg");
    expect(svg).not.toBeNull();

    const paths = svg?.querySelectorAll("path");
    // All 5 tiers have > 0%, so all should render a path
    expect(paths).toHaveLength(5);
  });

  it("omits path elements for zero-percent tiers", () => {
    const withZero: Record<ContextTier, number> = {
      immediate: 100,
      recent: 0,
      kb_referenced: 0,
      kb_suggested: 0,
      pinned: 0,
    };
    render(<ContextBudget percentages={withZero} onChange={vi.fn()} />);

    const svg = document.querySelector("svg");
    const paths = svg?.querySelectorAll("path");
    // Only 1 tier has > 0%
    expect(paths).toHaveLength(1);
  });

  it("calls onChange when a slider is moved", () => {
    const onChange = vi.fn();
    render(<ContextBudget percentages={balancedPercentages} onChange={onChange} />);

    const sliders = screen.getAllByRole("slider");
    expect(sliders).toHaveLength(5);

    // Move the first slider (immediate) from 30 to 50
    fireEvent.change(sliders[0], { target: { value: "50" } });

    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith({
      ...balancedPercentages,
      immediate: 50,
    });
  });

  it("shows validation checkmark when total is 100%", () => {
    render(<ContextBudget percentages={balancedPercentages} onChange={vi.fn()} />);

    // Should show the checkmark text (✓ 100% rendered as a combined string)
    expect(screen.getByText(/\u2713\s*100%/)).toBeDefined();
    // Should NOT show the warning
    expect(screen.queryByText(/settings\.ai\.contextBudget\.sumWarning/)).toBeNull();
  });

  it("shows sum warning when total is not 100%", () => {
    const invalidPercentages: Record<ContextTier, number> = {
      immediate: 50,
      recent: 10,
      kb_referenced: 10,
      kb_suggested: 10,
      pinned: 5,
    };
    render(<ContextBudget percentages={invalidPercentages} onChange={vi.fn()} />);

    // Total is 85%, so warning should appear
    // The mock replaces {total} with the value, so the key is rendered with the param
    expect(screen.getByText(/settings\.ai\.contextBudget\.sumWarning/)).toBeDefined();
  });

  it("renders percentage labels for each tier", () => {
    render(<ContextBudget percentages={unevenPercentages} onChange={vi.fn()} />);

    // Each tier should show its percentage
    expect(screen.getByText("50%")).toBeDefined();
    expect(screen.getByText("20%")).toBeDefined();
    expect(screen.getByText("15%")).toBeDefined();
    expect(screen.getByText("10%")).toBeDefined();
    expect(screen.getByText("5%")).toBeDefined();
  });

  it("disables sliders when disabled prop is true", () => {
    render(<ContextBudget percentages={balancedPercentages} onChange={vi.fn()} disabled />);

    const sliders = screen.getAllByRole("slider");
    for (const slider of sliders) {
      expect((slider as HTMLInputElement).disabled).toBe(true);
    }
  });

  it("renders 5 color dots for tier legend", () => {
    render(<ContextBudget percentages={balancedPercentages} onChange={vi.fn()} />);

    const dots = document.querySelectorAll(".rounded-full");
    // 5 tier color dots (the checkmark span also has no rounded-full class)
    expect(dots).toHaveLength(5);
  });
});
