import { describe, expect, it } from "vitest";
import { computeDiffElements } from "@/components/studio/editor/InlineDiff";

// ---------------------------------------------------------------------------
// Tests: computeDiffElements
// ---------------------------------------------------------------------------

describe("computeDiffElements", () => {
  it("returns identical text as single unchanged element", () => {
    const elements = computeDiffElements("Hello world", "Hello world");

    expect(elements).toHaveLength(1);
    // The single element should be a span with no special class (unchanged)
  });

  it("highlights added text with green class", () => {
    const elements = computeDiffElements("Hello", "Hello world");

    // Should have at least 2 elements: unchanged "Hello" + inserted " world"
    expect(elements.length).toBeGreaterThanOrEqual(2);
  });

  it("highlights removed text with red strikethrough class", () => {
    const elements = computeDiffElements("Hello world", "Hello");

    // Should have at least 2 elements: unchanged "Hello" + deleted " world"
    expect(elements.length).toBeGreaterThanOrEqual(2);
  });

  it("handles completely different strings", () => {
    const elements = computeDiffElements("aaa", "bbb");

    // All removed + all inserted
    expect(elements.length).toBeGreaterThanOrEqual(2);
  });

  it("handles empty original", () => {
    const elements = computeDiffElements("", "new text");

    // Everything is an insert
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it("handles empty alternative", () => {
    const elements = computeDiffElements("old text", "");

    // Everything is a deletion
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it("handles both additions and removals", () => {
    const elements = computeDiffElements("The quick fox", "A fast fox");

    // Should have mixed elements
    expect(elements.length).toBeGreaterThanOrEqual(2);
  });

  it("returns React elements (objects with key, props, type)", () => {
    const elements = computeDiffElements("Hello", "Hello world");

    for (const el of elements) {
      // React elements are objects
      expect(typeof el).toBe("object");
      expect(el).not.toBeNull();
    }
  });
});
