/**
 * NoteFilterBar component tests (NOTES-001 §7 — T21b combobox + scope upgrade).
 *
 * Conventions (mirrors notes/__tests__/TagInput.test.tsx): the centralized
 * setupTests mock returns i18n KEY STRINGS verbatim — assertions check keys.
 *
 * Covers the two §7 upgrades over the T21 plain-select version:
 * 1. Tag filter as a single-tag autocomplete combobox (NOT the multi-chip
 *    editor): typing filters suggestions, picking (mouse or keyboard) sets
 *    the filter tag, the selection renders as a chip with a clear affordance.
 *    Because this is a FILTER, Enter only commits existing tags (a filter for
 *    a nonexistent tag would be a dead end) — unlike TagInput's free-form entry.
 * 2. Novel/series scope select — ONE grouped select, rendered ONLY while the
 *    parent signals `hasLinks` AND at least one option list is non-empty;
 *    selection flows through the single onFiltersChange(NoteFilters)
 *    contract as a typed scope object.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { NoteFilterBar, type NoteFilterBarProps, type NoteFilters } from "../NoteFilterBar";

const NOVELS = [{ id: "nv1", title: "The Lighthouse" }] as const;
const SERIES = [{ id: "sr1", title: "Northern Light" }] as const;

type HarnessOverrides = Omit<Partial<NoteFilterBarProps>, "filters" | "onFiltersChange">;

/**
 * Stateful harness mirroring the real parent (ScratchpadWorkspace owns filter
 * state and echoes onFiltersChange back into `filters`) so the controlled
 * combobox↔chip swap is exercised across re-renders.
 */
function Harness({
  spy,
  initial,
  ...overrides
}: HarnessOverrides & { spy?: (next: NoteFilters) => void; initial?: Partial<NoteFilters> }) {
  const [filters, setFilters] = useState<NoteFilters>({
    q: "",
    note_type: "",
    tag: "",
    scope: null,
    ...initial,
  });
  return (
    <NoteFilterBar
      filters={filters}
      onFiltersChange={(next) => {
        spy?.(next);
        setFilters(next);
      }}
      availableTags={["plot", "poem", "world"]}
      novels={NOVELS}
      series={SERIES}
      hasLinks
      semanticMode={false}
      onSemanticModeChange={vi.fn()}
      onSearchSubmit={vi.fn()}
      {...overrides}
    />
  );
}

describe("NoteFilterBar — tag filter combobox", () => {
  it("filters suggestions by typed prefix and picks one via mouse", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    const input = screen.getByTestId("note-filter-tag-input");
    fireEvent.change(input, { target: { value: "po" } });
    expect(screen.getByTestId("note-filter-tag-suggestion-poem")).toBeInTheDocument();
    expect(screen.queryByTestId("note-filter-tag-suggestion-plot")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("note-filter-tag-suggestion-poem"));
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ tag: "poem" }));
  });

  it("keyboard flow: ArrowDown highlights, Enter commits, chip replaces the input, clear resets", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    const input = screen.getByTestId("note-filter-tag-input");
    fireEvent.change(input, { target: { value: "p" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getByTestId("note-filter-tag-suggestion-plot")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.keyDown(input, { key: "Enter" });
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ tag: "plot" }));
    // Controlled echo: the selected filter renders as a chip, input is gone.
    const chip = screen.getByTestId("note-filter-tag-chip");
    expect(chip).toHaveTextContent("plot");
    expect(screen.queryByTestId("note-filter-tag-input")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("note-filter-tag-clear"));
    expect(spy).toHaveBeenLastCalledWith(expect.objectContaining({ tag: "" }));
    expect(screen.getByTestId("note-filter-tag-input")).toBeInTheDocument();
  });

  it("Enter commits only existing tags (normalized), never free-form drafts", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    const input = screen.getByTestId("note-filter-tag-input");
    fireEvent.change(input, { target: { value: "zzz" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(spy).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "POEM" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ tag: "poem" }));
  });

  it("wires combobox aria attributes; suggestions appear only while typing", () => {
    render(<Harness />);
    const input = screen.getByTestId("note-filter-tag-input");
    expect(input).toHaveAttribute("role", "combobox");
    expect(input).toHaveAttribute("aria-autocomplete", "list");
    // Empty draft → closed, even though tags exist (filter UX, not picker).
    expect(input).toHaveAttribute("aria-expanded", "false");
    fireEvent.change(input, { target: { value: "wo" } });
    expect(input).toHaveAttribute("aria-expanded", "true");
    const listbox = screen.getByRole("listbox");
    expect(input).toHaveAttribute("aria-controls", listbox.id);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    const option = screen.getByRole("option", { name: "world" });
    expect(input).toHaveAttribute("aria-activedescendant", option.id);
  });
});

describe("NoteFilterBar — novel/series scope filter", () => {
  it("renders the grouped scope select only when hasLinks and options exist", () => {
    const { rerender } = render(<Harness hasLinks={false} />);
    expect(screen.queryByTestId("note-scope-filter")).not.toBeInTheDocument();
    rerender(<Harness hasLinks novels={[]} series={[]} />);
    expect(screen.queryByTestId("note-scope-filter")).not.toBeInTheDocument();
    rerender(<Harness hasLinks />);
    const select = screen.getByTestId("note-scope-filter");
    expect(within(select).getByRole("option", { name: "list.allScopes" })).toHaveAttribute(
      "value",
      "",
    );
    expect(within(select).getByRole("group", { name: "list.scopeNovelsGroup" })).toBeTruthy();
    expect(within(select).getByRole("group", { name: "list.scopeSeriesGroup" })).toBeTruthy();
    expect(within(select).getByRole("option", { name: "The Lighthouse" })).toHaveAttribute(
      "value",
      "novel:nv1",
    );
    expect(within(select).getByRole("option", { name: "Northern Light" })).toHaveAttribute(
      "value",
      "series:sr1",
    );
  });

  it("fires onFiltersChange with the typed scope (and back to null for All)", () => {
    const spy = vi.fn();
    render(<Harness spy={spy} />);
    const select = screen.getByTestId("note-scope-filter");
    fireEvent.change(select, { target: { value: "novel:nv1" } });
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({ scope: { kind: "novel", id: "nv1" } }),
    );
    fireEvent.change(select, { target: { value: "series:sr1" } });
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({ scope: { kind: "series", id: "sr1" } }),
    );
    fireEvent.change(select, { target: { value: "" } });
    expect(spy).toHaveBeenLastCalledWith(expect.objectContaining({ scope: null }));
  });

  it("keeps a stale scope selectable-rendered (fallback option) until the parent clears it", () => {
    render(
      <Harness
        spy={vi.fn()}
        initial={{ q: "", note_type: "", tag: "", scope: { kind: "novel", id: "gone" } }}
      />,
    );
    const select = screen.getByTestId("note-scope-filter");
    expect(within(select).getByRole("option", { name: "gone" })).toHaveAttribute(
      "value",
      "novel:gone",
    );
  });
});

describe("NoteFilterBar — T21 contract stays intact", () => {
  it("search, type select and semantic toggle still report through their callbacks", () => {
    const onSemanticModeChange = vi.fn();
    render(<Harness onSemanticModeChange={onSemanticModeChange} />);
    fireEvent.change(screen.getByTestId("note-search-input"), { target: { value: "storm" } });
    fireEvent.change(screen.getByTestId("note-type-filter"), { target: { value: "idea" } });
    fireEvent.click(screen.getByTestId("note-semantic-toggle"));
    expect(onSemanticModeChange).toHaveBeenCalledWith(true);
  });
});
