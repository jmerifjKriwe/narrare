// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("the rail's area hues", () => {
  it("derives the utility from the capability id", () => {
    const source = readFileSync(new URL("./IconRail.tsx", import.meta.url), "utf8");
    expect(source).toMatch(/text-area-\$\{[^}]+\}/);
    expect(source).not.toMatch(/AREA_ICON/);
  });
});
