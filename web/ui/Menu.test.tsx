// @vitest-environment jsdom
/**
 * The action menu's keyboard contract, pinned at the primitive: the
 * trigger opens on press, Escape closes and returns focus to the trigger,
 * the arrow keys walk the items (skipping the disabled ones — a disabled
 * item is not a stop), and pressing a disabled item fires nothing.
 *
 * React Aria owns the contract; these cases pin that the wrapper hands it
 * through intact — the items' `onSelect`, their `isDisabled`, the shortcut
 * hints — because the runhead's menu (WP6) and the card menu (Task 13)
 * both ride this one primitive. The house has no jest-dom matchers: focus
 * and attributes are asserted as the DOM answers them.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ActionMenu } from "./Menu";

afterEach(cleanup);

function user() {
  return userEvent.setup({ pointerEventsCheck: 0 });
}

describe("ActionMenu", () => {
  it("the_trigger_opens_on_press_and_escape_closes", async () => {
    const onSelect = vi.fn();
    render(
      <ActionMenu
        label="Aktionen"
        triggerAriaLabel="Aktionen für Erstes"
        items={[{ id: "one", label: "Eins", onSelect }]}
      />,
    );
    const trigger = screen.getByRole("button", { name: "Aktionen für Erstes" });
    expect(screen.queryByRole("menu")).toBeNull();

    await user().click(trigger);
    expect(screen.getByRole("menu")).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Eins" })).toBeTruthy();

    // Escape closes and hands focus back to the trigger — the press that
    // opened the menu is the place a keyboard user returns to.
    await user().keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });

  it("arrow_keys_walk_the_items", async () => {
    const onSelect = vi.fn();
    render(
      <ActionMenu
        label="Aktionen"
        triggerAriaLabel="Aktionen für Erstes"
        items={[
          { id: "one", label: "Eins", onSelect },
          { id: "two", label: "Zwei", onSelect },
          { id: "three", label: "Drei", onSelect },
        ]}
      />,
    );
    await user().click(screen.getByRole("button", { name: "Aktionen für Erstes" }));

    // The walk: down into the list, along it, and back. Focus is the
    // walk's own state — the selection happens on activation, never on
    // the walk past.
    await user().keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Eins" }));
    await user().keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Zwei" }));
    await user().keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Eins" }));
  });

  it("a_disabled_item_does_not_fire", async () => {
    const onSelect = vi.fn();
    const onOther = vi.fn();
    render(
      <ActionMenu
        label="Aktionen"
        triggerAriaLabel="Aktionen für Erstes"
        items={[
          { id: "one", label: "Eins", onSelect },
          { id: "two", label: "Zwei", onSelect: onOther, disabled: true },
          { id: "three", label: "Drei", onSelect: onOther },
        ]}
      />,
    );
    await user().click(screen.getByRole("button", { name: "Aktionen für Erstes" }));

    // The walk skips the disabled item: one press of ArrowDown past the
    // top lands on Drei, not Zwei.
    await user().keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Eins" }));
    await user().keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Drei" }));

    // A press on the disabled item itself fires nothing — disabled means
    // absent to both the keyboard and the pointer.
    const disabled = screen.getByRole("menuitem", { name: "Zwei" });
    expect(disabled.getAttribute("aria-disabled")).toBe("true");
    await user().click(disabled);
    expect(onOther).not.toHaveBeenCalled();
    expect(onSelect).not.toHaveBeenCalled();

    // An enabled item still fires — the disabled one took nothing with it.
    await user().click(screen.getByRole("menuitem", { name: "Eins" }));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("carries_the_shortcut_hint_beside_the_label", async () => {
    render(
      <ActionMenu
        label="Aktionen"
        triggerAriaLabel="Aktionen für Erstes"
        items={[{ id: "one", label: "Nach oben", shortcut: "Alt+↑", onSelect: () => {} }]}
      />,
    );
    await user().click(screen.getByRole("button", { name: "Aktionen für Erstes" }));
    // The hint is visible beside the label for discovery (D6), and the
    // accessible name is the label alone: the keystroke travels in
    // `aria-keyshortcuts` — in UI Events key values, the form WAI-ARIA
    // expects, not the glyph the screen shows — and the glyph stays the
    // visible `<kbd>`'s own text.
    const item = screen.getByRole("menuitem", { name: "Nach oben" });
    expect(item.textContent).toContain("Alt+↑");
    expect(item.getAttribute("aria-keyshortcuts")).toBe("Alt+ArrowUp");
  });
});
