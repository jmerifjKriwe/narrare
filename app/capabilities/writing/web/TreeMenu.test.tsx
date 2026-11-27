// @vitest-environment jsdom
/**
 * The tree row's quick menu (W4 Task 13): the shelf quick menu's popover
 * discipline re-owned for the explorer's rows — the workspace drafts draw
 * no rename/delete affordance, so the established pattern applies (no
 * invented geometry). A non-modal dialog: the moreVert trigger opens the
 * eyebrow + two rows (edit/rename, delete), focus lands on the first row,
 * Escape returns to the trigger, an outside press closes without stealing
 * focus. The actions hand off to the page's dialogs (the menu closes; the
 * opener's id rides along so the dialog can return focus to the trigger).
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { applyLocale } from "@shell/lib/locale";
import { de } from "@shell/lib/test/catalogs";

import { TreeMenu } from "./TreeMenu";

function renderMenu(overrides: Partial<Parameters<typeof TreeMenu>[0]> = {}) {
  const props = {
    label: de["writing.workspace.tree.chapterOptions"],
    editLabel: de["writing.workspace.tree.rename"],
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  const utils = render(<TreeMenu {...props} />);
  return { ...utils, ...props };
}

beforeEach(() => {
  applyLocale("de");
});

afterEach(cleanup);

describe("the trigger", () => {
  it("is a labelled dialog trigger, closed at rest", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] });
    expect(trigger.getAttribute("aria-haspopup")).toBe("dialog");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens the menu and focuses the first row", () => {
    renderMenu();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] }));
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-label")).toBe(de["writing.workspace.tree.chapterOptions"]);
    const first = screen.getByRole("button", { name: de["writing.workspace.tree.rename"] });
    expect(document.activeElement).toBe(first);
    expect(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] })).toBeTruthy();
  });
});

describe("the open menu", () => {
  it("the edit row hands off with the opener's id and closes the menu", () => {
    const props = renderMenu();
    const trigger = screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] });
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.rename"] }));
    expect(props.onEdit).toHaveBeenCalledTimes(1);
    // The opener id names the trigger — the dialog's focus return.
    const openerId = (props.onEdit as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(document.getElementById(openerId)).toBe(trigger);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(props.onDelete).not.toHaveBeenCalled();
  });

  it("the delete row hands off the same way", () => {
    const props = renderMenu();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] }));
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.delete"] }));
    expect(props.onDelete).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Escape closes and returns focus to the trigger", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] });
    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("an outside press closes without stealing focus", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] });
    fireEvent.click(trigger);
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).not.toBe(trigger);
  });

  it("a press inside the menu does not close it", () => {
    renderMenu();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] }));
    fireEvent.mouseDown(screen.getByRole("dialog"));
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("the trigger toggles the menu closed again", () => {
    renderMenu();
    const trigger = screen.getByRole("button", { name: de["writing.workspace.tree.chapterOptions"] });
    fireEvent.click(trigger);
    fireEvent.click(trigger);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
