import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { KBTagInput } from "./KBTagInput";

describe("KBTagInput", () => {
  it("renders with initial tags", () => {
    render(<KBTagInput value={["brave", "kind"]} onChange={() => {}} />);
    expect(screen.getByText("brave")).toBeInTheDocument();
    expect(screen.getByText("kind")).toBeInTheDocument();
  });

  it("adds a tag on Enter", async () => {
    const onChange = vi.fn();
    render(<KBTagInput value={[]} onChange={onChange} />);

    const input = screen.getByRole("textbox", { name: "Add tag" });
    await userEvent.type(input, "curious{Enter}");

    expect(onChange).toHaveBeenCalledWith(["curious"]);
  });

  it("adds a tag on comma", async () => {
    const onChange = vi.fn();
    render(<KBTagInput value={[]} onChange={onChange} />);

    const input = screen.getByRole("textbox", { name: "Add tag" });
    await userEvent.type(input, "brave,");

    expect(onChange).toHaveBeenCalledWith(["brave"]);
  });

  it("removes a tag when X is clicked", async () => {
    const onChange = vi.fn();
    render(<KBTagInput value={["brave", "kind"]} onChange={onChange} />);

    const removeButtons = screen.getAllByRole("button");
    // First remove button is for "brave"
    await userEvent.click(removeButtons[0]);

    expect(onChange).toHaveBeenCalledWith(["kind"]);
  });

  it("removes last tag on Backspace in empty input", async () => {
    const onChange = vi.fn();
    render(<KBTagInput value={["brave"]} onChange={onChange} />);

    const input = screen.getByRole("textbox", { name: "Add tag" });
    await userEvent.type(input, "{Backspace}");

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("does not add duplicate tags", async () => {
    const onChange = vi.fn();
    render(<KBTagInput value={["brave"]} onChange={onChange} />);

    const input = screen.getByRole("textbox", { name: "Add tag" });
    await userEvent.type(input, "brave{Enter}");

    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows placeholder when no tags", () => {
    render(<KBTagInput value={[]} onChange={() => {}} placeholder="Add something..." />);
    const input = screen.getByRole("textbox", { name: "Add tag" });
    expect(input).toHaveAttribute("placeholder", "Add something...");
  });

  it("hides placeholder when tags exist", () => {
    render(<KBTagInput value={["brave"]} onChange={() => {}} placeholder="Add something..." />);
    const input = screen.getByRole("textbox", { name: "Add tag" });
    expect(input).not.toHaveAttribute("placeholder");
  });

  it("handles paste of comma-separated tags", async () => {
    const onChange = vi.fn();
    render(<KBTagInput value={[]} onChange={onChange} />);

    const input = screen.getByRole("textbox", { name: "Add tag" });
    await userEvent.click(input);
    await userEvent.paste("brave, kind, curious");

    expect(onChange).toHaveBeenCalledWith(["brave", "kind", "curious"]);
  });

  // CR-07 §16: no hardcoded English visible fallbacks in production.
  it("does not use hardcoded English 'Tags' for listbox aria-label when no placeholder is passed", () => {
    render(<KBTagInput value={[]} onChange={() => {}} />);
    // The listbox must use the i18n key (kb.tags) under the key-returning
    // translation mock, never the literal "Tags" fallback.
    expect(screen.queryByRole("listbox")).not.toHaveAttribute("aria-label", "Tags");
  });
});
