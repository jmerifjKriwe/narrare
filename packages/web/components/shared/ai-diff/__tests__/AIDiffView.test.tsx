import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AIDiffViewModel } from "@/lib/ai-diff/contracts";
import { segmentize } from "@/lib/ai-diff/segmentize";
import { AIDiffView } from "../AIDiffView";

// Note on i18n: setupTests.ts globally mocks next-intl to return the key as the
// rendered text. Tests assert against i18n KEYS; prop-derived values (labels,
// field text) are asserted as-is.

const textVm: AIDiffViewModel = {
  id: "rw-1",
  mode: "text",
  segments: segmentize("cat", "dog"),
  originalFull: "cat",
  suggestedFull: "dog",
  label: "Sentence",
  provisional: false,
};

describe("AIDiffView", () => {
  it("renders the badge and label in text mode", () => {
    render(<AIDiffView viewModel={textVm} state="suggested" />);
    // label is a prop-derived value (not i18n)
    expect(screen.getByText("Sentence")).toBeTruthy();
    // badge uses the canonical aiActions.suggested key
    expect(screen.getByText("aiActions.suggested")).toBeTruthy();
  });

  it("renders the inline diff segments (ins/del) in text mode", () => {
    const { container } = render(<AIDiffView viewModel={textVm} state="suggested" />);
    expect(container.querySelector("ins")).not.toBeNull();
    expect(container.querySelector("del")).not.toBeNull();
  });

  it("announces a screen-reader summary on the region (wired srSummary key)", () => {
    render(<AIDiffView viewModel={textVm} state="suggested" />);
    // <section aria-label="..."> has implicit role="region". Under the global
    // next-intl mock the aria-label resolves to the wired key.
    const region = screen.getByRole("region");
    expect(region.getAttribute("aria-label")).toContain("srSummary");
  });

  it("renders before/after columns in field mode (no inline diff)", () => {
    const fieldVm: AIDiffViewModel = {
      id: "kb-role",
      mode: "field",
      segments: [],
      originalFull: "Mentor",
      suggestedFull: "Wise mentor",
      label: "Role",
      provisional: false,
    };
    const { container } = render(<AIDiffView viewModel={fieldVm} state="accepted" />);
    // Column headers via canonical aiActions keys
    expect(screen.getByText("aiActions.original")).toBeTruthy();
    expect(screen.getByText("aiActions.suggested")).toBeTruthy();
    // Whole field values (props)
    expect(screen.getByText("Mentor")).toBeTruthy();
    expect(screen.getByText("Wise mentor")).toBeTruthy();
    // Field mode must NOT produce inline ins/del segments
    expect(container.querySelector("ins")).toBeNull();
    expect(container.querySelector("del")).toBeNull();
  });

  it("shows a provisional indicator when viewModel.provisional is true", () => {
    const provVm: AIDiffViewModel = { ...textVm, provisional: true };
    render(<AIDiffView viewModel={provVm} state="suggested" />);
    expect(screen.getByText("aiDiff.provisional")).toBeTruthy();
  });

  it("omits the provisional indicator when viewModel.provisional is false", () => {
    render(<AIDiffView viewModel={textVm} state="suggested" />);
    expect(screen.queryByText("aiDiff.provisional")).toBeNull();
  });
});
