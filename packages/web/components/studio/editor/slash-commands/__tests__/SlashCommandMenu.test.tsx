/**
 * SlashCommandMenu component tests (CR-AUFG-07-20).
 *
 * Covers: rendered i18n labels, keyboard navigation (arrows + enter), disabled
 * commands with actionable guidance (no-selection), dispatch on select, and the
 * empty state when no command matches the query.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SlashCommandMenu, type SlashCommandMenuItem } from "../SlashCommandMenu";

const t = (key: string, params?: Record<string, unknown>) =>
  params ? `${key}:${JSON.stringify(params)}` : key;

function item(partial: Partial<SlashCommandMenuItem> & { id: string }): SlashCommandMenuItem {
  return {
    labelKey: `slashCommands.${partial.id}.label`,
    descriptionKey: `slashCommands.${partial.id}.description`,
    availability: "available",
    ...partial,
  };
}

const AVAILABLE_ITEMS: SlashCommandMenuItem[] = [
  item({ id: "continue" }),
  item({ id: "draft" }),
  item({ id: "rewrite", availability: "no-selection" }),
];

function renderMenu(overrides: Partial<Parameters<typeof SlashCommandMenu>[0]> = {}) {
  const onActiveIndexChange = vi.fn();
  const onSelect = vi.fn();
  const onDismiss = vi.fn();
  const result = render(
    <SlashCommandMenu
      items={AVAILABLE_ITEMS}
      activeIndex={0}
      query=""
      position={{ top: 100, left: 50 }}
      onActiveIndexChange={onActiveIndexChange}
      onSelect={onSelect}
      onDismiss={onDismiss}
      t={t}
      {...overrides}
    />,
  );
  return { ...result, onActiveIndexChange, onSelect, onDismiss };
}

describe("SlashCommandMenu rendering", () => {
  it("renders each command label and description from i18n keys", () => {
    renderMenu();
    expect(screen.getByText("slashCommands.continue.label")).toBeInTheDocument();
    expect(screen.getByText("slashCommands.draft.label")).toBeInTheDocument();
    expect(screen.getByText("slashCommands.rewrite.label")).toBeInTheDocument();
    expect(screen.getByText("slashCommands.continue.description")).toBeInTheDocument();
  });

  it("marks the active item with an aria-selected/active affordance", () => {
    const { container } = renderMenu({ activeIndex: 1 });
    const options = container.querySelectorAll("[role='option']");
    expect(options[1]).toHaveAttribute("aria-selected", "true");
  });

  it("renders as a listbox for assistive tech", () => {
    renderMenu();
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });
});

describe("SlashCommandMenu disabled guidance", () => {
  it("marks a no-selection command as disabled with a guidance reason", () => {
    renderMenu();
    const rewrite = screen.getByText("slashCommands.rewrite.label").closest("[role='option']");
    expect(rewrite).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("slashCommands.disabledReasons.noSelection")).toBeInTheDocument();
  });
});

describe("SlashCommandMenu keyboard navigation", () => {
  it("ArrowDown moves active to the next available item (skipping disabled)", () => {
    // The menu is controlled: the hook re-renders with the new active index
    // between key presses. Simulate that here with rerender.
    const { onActiveIndexChange, rerender } = renderMenu({ activeIndex: 0 });
    // index 1 (draft) is available; index 2 (rewrite) is disabled
    fireEvent.keyDown(window, { key: "ArrowDown" });
    expect(onActiveIndexChange).toHaveBeenLastCalledWith(1);
    // hook applied the change → re-render with activeIndex 1
    rerender(
      <SlashCommandMenu
        items={AVAILABLE_ITEMS}
        activeIndex={1}
        query=""
        position={{ top: 100, left: 50 }}
        onActiveIndexChange={onActiveIndexChange}
        onSelect={vi.fn()}
        onDismiss={vi.fn()}
        t={t}
      />,
    );
    // a second ArrowDown skips the disabled index 2 and wraps to 0
    fireEvent.keyDown(window, { key: "ArrowDown" });
    expect(onActiveIndexChange).toHaveBeenLastCalledWith(0);
  });

  it("ArrowUp moves active to the previous available item", () => {
    const { onActiveIndexChange } = renderMenu({ activeIndex: 1 });
    fireEvent.keyDown(window, { key: "ArrowUp" });
    expect(onActiveIndexChange).toHaveBeenLastCalledWith(0);
  });

  it("Enter selects the active command", () => {
    const { onSelect } = renderMenu({ activeIndex: 0 });
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(0);
  });

  it("Enter on a disabled command does not select", () => {
    const { onSelect } = renderMenu({ activeIndex: 2 });
    fireEvent.keyDown(window, { key: "Enter" });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("Escape dismisses the menu", () => {
    const { onDismiss } = renderMenu();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("ArrowDown prevents default so the editor caret does not move", () => {
    renderMenu();
    const event = new KeyboardEvent("keydown", {
      key: "ArrowDown",
      bubbles: true,
      cancelable: true,
    });
    const preventDefault = vi.spyOn(event, "preventDefault");
    window.dispatchEvent(event);
    expect(preventDefault).toHaveBeenCalled();
  });
});

describe("SlashCommandMenu dispatch", () => {
  it("clicking an available command selects it", () => {
    const { onSelect } = renderMenu();
    fireEvent.click(screen.getByText("slashCommands.draft.label"));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("clicking a disabled command does not select", () => {
    const { onSelect } = renderMenu();
    fireEvent.click(screen.getByText("slashCommands.rewrite.label"));
    expect(onSelect).not.toHaveBeenCalled();
  });
});

describe("SlashCommandMenu empty state", () => {
  it("renders the empty-state guidance when no items match", () => {
    renderMenu({ items: [], query: "zzz" });
    expect(screen.getByText("slashCommands.empty")).toBeInTheDocument();
  });
});
