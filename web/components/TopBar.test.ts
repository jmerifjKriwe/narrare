// @vitest-environment node
/**
 * The bar's chrome fixtures, pinned the way the rail's are: TopBar renders
 * against the router, the page-title store and the shortcut registry, so
 * the contract here reads the source — the one definition the app ships.
 * The drafted Tier 1 answer (spec §6.4): the bar is a flat panel bound by
 * the hairline, and the palette's key is a Keycap — the one primitive,
 * not a chip this file grows a second shell for.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("the top bar's chrome", () => {
  const source = readFileSync(new URL("./TopBar.tsx", import.meta.url), "utf8");

  it("sits on the panel ground behind a hairline edge, flat (Tier 1)", () => {
    expect(source).toMatch(/border-b border-border bg-panel/);
    expect(source).not.toMatch(/shadow-/);
  });

  it("renders the palette's key through the Keycap primitive", () => {
    expect(source).toMatch(/import \{ Keycap \} from "\.\.\/ui\/Keycap"/);
    expect(source).toMatch(/<Keycap>\{paletteKey\}<\/Keycap>/);
  });
});
