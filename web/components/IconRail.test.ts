// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("the rail's area hues", () => {
  it("derives the colour from the capability id", () => {
    const source = readFileSync(new URL("./IconRail.tsx", import.meta.url), "utf8");
    expect(source).toMatch(/var\(--area-\$\{[^}]+\}/);
    expect(source).not.toMatch(/AREA_ICON/);
  });
});
