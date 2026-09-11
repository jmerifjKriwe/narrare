/**
 * TagInput component tests (NOTES-001) — chips + free-form entry +
 * suggestion filtering + normalization + max cap.
 *
 * Conventions (mirrors notes/__tests__/NoteList.test.tsx): the centralized
 * setupTests mock returns i18n KEY STRINGS verbatim — assertions check keys.
 *
 * Beyond the five plan-mandated behavior tests, keyboard a11y is covered per
 * the repo autocomplete convention (useMentionAutocomplete): ArrowUp/ArrowDown
 * cycle the suggestion listbox (with wrap-around), Enter picks the highlighted
 * option — or adds the typed draft when nothing is highlighted, Escape clears
 * the highlight, and the input is wired as a combobox (aria-expanded /
 * aria-controls / aria-autocomplete / aria-activedescendant). Backspace on an
 * empty draft removes the last chip (KBTagInput convention).
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TagInput } from "../TagInput";

describe("TagInput", () => {
  it("adds a typed tag on Enter and normalizes it (trim + lowercase)", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={[]} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "  Plot Twist " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["plot twist"]);
  });

  it("filters suggestions by the current input prefix", () => {
    render(<TagInput value={[]} onChange={vi.fn()} suggestions={["plot", "world", "poem"]} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "po" } });
    expect(screen.getByText("poem")).toBeInTheDocument();
    expect(screen.queryByText("plot")).not.toBeInTheDocument();
  });

  it("picking a suggestion adds exactly that tag", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={["plot"]} />);
    fireEvent.change(screen.getByTestId("tag-input"), { target: { value: "pl" } });
    fireEvent.click(screen.getByTestId("tag-suggestion-plot"));
    expect(onChange).toHaveBeenCalledWith(["plot"]);
  });

  it("removes a chip via its remove button", () => {
    const onChange = vi.fn();
    render(<TagInput value={["plot"]} onChange={onChange} suggestions={[]} />);
    fireEvent.click(screen.getByTestId("tag-remove-plot"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("ignores duplicates and enforces the max cap", () => {
    const onChange = vi.fn();
    render(<TagInput value={["plot"]} onChange={onChange} suggestions={[]} maxTags={2} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "PLOT" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: "world" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["plot", "world"]);
    fireEvent.change(input, { target: { value: "third" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledTimes(1); // capped — no further calls
  });

  it("navigates suggestions with arrow keys (wrap-around) and picks with Enter", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={["plot", "poem"]} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "p" } });
    expect(screen.getByTestId("tag-suggestion-plot")).toHaveAttribute("aria-selected", "false");
    // ArrowUp from nothing wraps to the last suggestion.
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(screen.getByTestId("tag-suggestion-poem")).toHaveAttribute("aria-selected", "true");
    // Enter picks the highlighted suggestion, not the typed draft.
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["poem"]);
  });

  it("wires combobox aria attributes to the suggestion listbox", () => {
    // The only suggestion is already selected → listbox hidden.
    const { rerender } = render(
      <TagInput value={["plot"]} onChange={vi.fn()} suggestions={["plot"]} />,
    );
    const input = screen.getByTestId("tag-input");
    expect(input).toHaveAttribute("aria-expanded", "false");
    expect(input).not.toHaveAttribute("aria-controls");
    expect(input).toHaveAttribute("aria-autocomplete", "list");
    // An empty draft still shows every unselected suggestion (picker style).
    rerender(<TagInput value={[]} onChange={vi.fn()} suggestions={["plot"]} />);
    expect(input).toHaveAttribute("aria-expanded", "true");
    fireEvent.change(input, { target: { value: "pl" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    const option = screen.getByRole("option", { name: "plot" });
    expect(option).toHaveAttribute("aria-selected", "true");
    expect(input).toHaveAttribute("aria-activedescendant", option.id);
    const listbox = screen.getByRole("listbox");
    expect(listbox).toHaveAttribute("aria-label", "editor.tagSuggestions");
    expect(input).toHaveAttribute("aria-controls", listbox.id);
  });

  it("Escape clears the keyboard highlight; Enter then adds the typed draft", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={["plot"]} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "pl" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.getByTestId("tag-suggestion-plot")).toHaveAttribute("aria-selected", "false");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["pl"]);
  });

  it("clears the hover highlight when the pointer leaves the suggestions (P-FE2)", () => {
    // Regression: a hovered pill used to keep the highlight after the pointer
    // left the pill row, so Enter picked a stale pill instead of the draft.
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={["plot"]} />);
    const input = screen.getByTestId("tag-input");
    fireEvent.change(input, { target: { value: "pl" } });
    fireEvent.mouseEnter(screen.getByTestId("tag-suggestion-plot"));
    expect(screen.getByTestId("tag-suggestion-plot")).toHaveAttribute("aria-selected", "true");
    fireEvent.mouseLeave(screen.getByRole("listbox"));
    expect(screen.getByTestId("tag-suggestion-plot")).toHaveAttribute("aria-selected", "false");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["pl"]);
  });

  it("renders suggestion pills as non-tabbable options (APG activedescendant pattern)", () => {
    // The combobox input owns focus; pills are pointed at via
    // aria-activedescendant and must not join the tab order.
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={["plot"]} />);
    expect(screen.getByTestId("tag-suggestion-plot")).toHaveAttribute("tabindex", "-1");
    // Pointer picking keeps working on the non-focusable pill.
    fireEvent.click(screen.getByTestId("tag-suggestion-plot"));
    expect(onChange).toHaveBeenCalledWith(["plot"]);
  });

  it("Backspace on an empty draft removes the last chip", () => {
    const onChange = vi.fn();
    render(<TagInput value={["plot", "world"]} onChange={onChange} suggestions={[]} />);
    fireEvent.keyDown(screen.getByTestId("tag-input"), { key: "Backspace" });
    expect(onChange).toHaveBeenCalledWith(["plot"]);
  });

  it("caps tag length at 32 characters (backend NoteLimits parity)", () => {
    const onChange = vi.fn();
    render(<TagInput value={[]} onChange={onChange} suggestions={[]} />);
    fireEvent.change(screen.getByTestId("tag-input"), {
      target: { value: "a".repeat(40) },
    });
    fireEvent.keyDown(screen.getByTestId("tag-input"), { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["a".repeat(32)]);
  });
});
