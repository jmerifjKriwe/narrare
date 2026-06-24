/**
 * Pure menu-item building + active-index clamping (CR-AUFG-07-20).
 *
 * These helpers are split out of the React hook so the filtering/availability
 * logic is unit-testable without mounting a TipTap editor.
 */
import { describe, expect, it } from "vitest";
import { buildMenuItems, clampActiveIndex } from "../menu-items";
import { AI_SLASH_COMMANDS } from "../registry";

const t = (key: string) => key;

describe("clampActiveIndex", () => {
  it("wraps negative indices", () => {
    expect(clampActiveIndex(-1, 3)).toBe(2);
  });

  it("wraps indices past the end", () => {
    expect(clampActiveIndex(3, 3)).toBe(0);
  });

  it("returns 0 for an empty list", () => {
    expect(clampActiveIndex(5, 0)).toBe(0);
  });

  it("passes through in-range indices", () => {
    expect(clampActiveIndex(1, 3)).toBe(1);
  });
});

describe("buildMenuItems", () => {
  const allOps = new Set([
    "writing.continue",
    "writing.generation",
    "writing.rewrite",
    "writing.co_author",
    "chat.free_assistant",
  ]);

  it("returns all commands for an empty query", () => {
    const items = buildMenuItems(AI_SLASH_COMMANDS, "", t, true, allOps);
    expect(items).toHaveLength(AI_SLASH_COMMANDS.length);
  });

  it("filters by the query", () => {
    const items = buildMenuItems(AI_SLASH_COMMANDS, "rew", t, true, allOps);
    expect(items.map((i) => i.id)).toEqual(["rewrite"]);
  });

  it("marks a selection command without a selection as no-selection", () => {
    const items = buildMenuItems(AI_SLASH_COMMANDS, "rew", t, false, allOps);
    expect(items[0].availability).toBe("no-selection");
  });

  it("marks a command unavailable when its operation is not wired by the host", () => {
    const noContinue = new Set(allOps);
    noContinue.delete("writing.continue");
    const items = buildMenuItems(AI_SLASH_COMMANDS, "", t, true, noContinue);
    const cont = items.find((i) => i.id === "continue");
    expect(cont?.availability).toBe("unavailable");
  });

  it("marks a wired, selection-satisfied command available", () => {
    const items = buildMenuItems(AI_SLASH_COMMANDS, "rew", t, true, allOps);
    expect(items[0].availability).toBe("available");
  });

  it("preserves registry display order for an empty query", () => {
    const items = buildMenuItems(AI_SLASH_COMMANDS, "", t, true, allOps);
    expect(items.map((i) => i.id)).toEqual(AI_SLASH_COMMANDS.map((c) => c.id));
  });

  it("uses localized label tokens for matching", () => {
    // rewrite label key resolves to "slashCommands.rewrite.label"; ensure a
    // query matching the label token still hits the command.
    const items = buildMenuItems(AI_SLASH_COMMANDS, "slashCommands.rewrite.label", t, true, allOps);
    expect(items.map((i) => i.id)).toContain("rewrite");
  });
});
