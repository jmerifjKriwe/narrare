import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AIDiffSegment } from "@/lib/ai-diff/contracts";
import { AIDiffSegmentList } from "../AIDiffSegmentList";

// Note on i18n: setupTests.ts globally mocks next-intl to return the key as the
// rendered text. Tests therefore assert against i18n KEYS (e.g. "aiDiff.added"),
// matching the established repo convention. This verifies the component wires
// the correct key/namespace; real message resolution is a next-intl concern.

const added: AIDiffSegment = { kind: "added", text: "new" };
const removed: AIDiffSegment = { kind: "removed", text: "old" };

describe("AIDiffSegmentList", () => {
  it("renders additions in a semantic <ins> element", () => {
    const { container } = render(<AIDiffSegmentList segments={[added]} />);
    expect(container.querySelector("ins")).not.toBeNull();
    expect(container.querySelector("ins")?.textContent).toContain("new");
  });

  it("renders removals in a semantic <del> element", () => {
    const { container } = render(<AIDiffSegmentList segments={[removed]} />);
    expect(container.querySelector("del")).not.toBeNull();
    expect(container.querySelector("del")?.textContent).toContain("old");
  });

  it("renders unchanged text as a plain span (no ins/del)", () => {
    const { container } = render(
      <AIDiffSegmentList segments={[{ kind: "unchanged", text: "same" }]} />,
    );
    expect(container.querySelector("ins")).toBeNull();
    expect(container.querySelector("del")).toBeNull();
    expect(container.textContent).toContain("same");
  });

  it("does NOT rely on color alone: visible + / - markers are present", () => {
    const { container } = render(<AIDiffSegmentList segments={[removed, added]} />);
    // Each change segment renders an aria-hidden visible marker (+ or -).
    const markers = container.querySelectorAll("[aria-hidden='true']");
    expect(markers.length).toBeGreaterThanOrEqual(2);
  });

  it("labels each change segment for screen readers via sr-only text (right i18n key)", () => {
    const { container } = render(<AIDiffSegmentList segments={[added, removed]} />);
    // sr-only label resolves to the wired key under the global mock.
    expect(container.querySelector("ins .sr-only")?.textContent).toBe("aiDiff.added: ");
    expect(container.querySelector("del .sr-only")?.textContent).toBe("aiDiff.removed: ");
  });
});
