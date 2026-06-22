/**
 * InlineDiff component tests — accessible rendering via the shared primitive.
 *
 * CR-AUFG-07-18 Task 12: InlineDiff now delegates to `segmentize` +
 * `AIDiffSegmentList`. These tests assert the accessible contract
 * (`<ins>`/`<del>` + visible markers, never color alone).
 *
 * The pure `computeDiffElements` unit tests live in `InlineDiff.test.ts`.
 *
 * i18n: setupTests.ts globally mocks next-intl; no provider required.
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InlineDiff } from "../InlineDiff";

describe("InlineDiff (refactored — CR-AUFG-07-18)", () => {
  it("renders additions in a semantic <ins> and removals in a <del>", () => {
    const { container } = render(<InlineDiff original="cat" alternative="dog" />);

    expect(container.querySelector("ins")).not.toBeNull();
    expect(container.querySelector("del")).not.toBeNull();
  });

  it("conveys change type with visible +/- markers (not color alone)", () => {
    const { container } = render(<InlineDiff original="cat" alternative="dog" />);

    // AIDiffSegmentList emits one aria-hidden marker per change segment.
    expect(container.querySelectorAll("[aria-hidden='true']").length).toBeGreaterThanOrEqual(2);
  });

  it("renders no <ins>/<del> when the texts are identical", () => {
    const { container } = render(<InlineDiff original="same" alternative="same" />);

    expect(container.querySelector("ins")).toBeNull();
    expect(container.querySelector("del")).toBeNull();
  });
});
