import { describe, expect, it } from "vitest";

import { sideBySide } from "./diff";

describe("sideBySide", () => {
  it("keeps identical lines on both sides", () => {
    expect(sideBySide("a\nb", "a\nb")).toEqual([
      { left: "a", right: "a" },
      { left: "b", right: "b" },
    ]);
  });

  it("marks an insertion on the right", () => {
    expect(sideBySide("a\nc", "a\nb\nc")).toEqual([
      { left: "a", right: "a" },
      { left: null, right: "b" },
      { left: "c", right: "c" },
    ]);
  });

  it("marks a deletion on the left", () => {
    expect(sideBySide("a\nb\nc", "a\nc")).toEqual([
      { left: "a", right: "a" },
      { left: "b", right: null },
      { left: "c", right: "c" },
    ]);
  });

  it("marks a replacement as deletion plus insertion", () => {
    expect(sideBySide("a\nb", "a\nc")).toEqual([
      { left: "a", right: "a" },
      { left: "b", right: null },
      { left: null, right: "c" },
    ]);
  });
});
