/**
 * SearchInput primitive tests (Task 5).
 *
 * Covers: type=search, label association, controlled onValueChange, and the
 * optional clear control (reusing IconButton). The clear control requires a
 * resolved-i18n `clearLabel` (RULE-16) — no hardcoded strings inside the
 * primitive.
 */

import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SearchInput } from "@/components/ui/search-input";

describe("SearchInput", () => {
  it("renders a type=search input associated with its label", () => {
    render(<SearchInput label="Search knowledge base" value="" onValueChange={() => {}} />);
    const input = screen.getByRole("searchbox", { name: "Search knowledge base" });
    expect(input).toHaveAttribute("type", "search");
  });

  it("calls onValueChange as the user types", async () => {
    const onValueChange = vi.fn();
    render(<SearchInput label="q" value="" onValueChange={onValueChange} />);
    await userEvent.type(screen.getByRole("searchbox"), "a");
    expect(onValueChange).toHaveBeenCalled();
  });

  it("shows a clear IconButton that calls onClear", async () => {
    const onClear = vi.fn();
    render(
      <SearchInput
        label="q"
        value="dragons"
        onValueChange={() => {}}
        onClear={onClear}
        clearLabel="Clear search"
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("does not render the clear control when the value is empty", () => {
    render(
      <SearchInput
        label="q"
        value=""
        onValueChange={() => {}}
        onClear={() => {}}
        clearLabel="Clear search"
      />,
    );
    expect(screen.queryByRole("button")).toBeNull();
  });
});
