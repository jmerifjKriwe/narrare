import { describe, expect, it } from "vitest";
import { segmentize } from "../segmentize";

describe("segmentize", () => {
  it("returns a single unchanged segment when strings are equal", () => {
    const segs = segmentize("hello", "hello");
    expect(segs).toEqual([{ kind: "unchanged", text: "hello" }]);
  });

  it("produces added + removed segments for a real change", () => {
    const segs = segmentize("the cat", "the dog");
    const kinds = segs.map((s) => s.kind);
    expect(kinds).toContain("removed");
    expect(kinds).toContain("added");
    expect(kinds).toContain("unchanged"); // "the " prefix
  });

  it("is pure: same input => same output and no mutation", () => {
    const a = segmentize("a b", "a c");
    const b = segmentize("a b", "a c");
    expect(a).toEqual(b);
  });

  it("concatenated removed+added text reproduces the change", () => {
    const segs = segmentize("old", "new");
    const removed = segs
      .filter((s) => s.kind === "removed")
      .map((s) => s.text)
      .join("");
    const added = segs
      .filter((s) => s.kind === "added")
      .map((s) => s.text)
      .join("");
    expect(removed).toBe("old");
    expect(added).toBe("new");
  });
});
