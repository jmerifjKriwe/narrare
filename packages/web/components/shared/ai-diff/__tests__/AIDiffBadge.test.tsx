import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AIDiffState } from "@/lib/ai-diff/contracts";
import { AIDiffBadge } from "../AIDiffBadge";

// Note on i18n: setupTests.ts globally mocks next-intl to return the key as the
// rendered text. Tests assert against i18n KEYS, matching the repo convention.

describe("AIDiffBadge", () => {
  it("shows the canonical Suggested label (aiActions.suggested) for the suggested state", () => {
    render(<AIDiffBadge state="suggested" />);
    expect(screen.getByText("aiActions.suggested")).toBeTruthy();
  });

  it("shows dedicated diff keys for accepted/rejected/unchanged", () => {
    const states: AIDiffState[] = ["accepted", "rejected", "unchanged"];
    const expectedKeys = ["aiDiff.accepted", "aiDiff.rejected", "aiDiff.unchanged"];
    for (let i = 0; i < states.length; i++) {
      const { unmount } = render(<AIDiffBadge state={states[i]} />);
      expect(screen.getByText(expectedKeys[i])).toBeTruthy();
      unmount();
    }
  });

  it("renders a visible label element (not color alone)", () => {
    const { container } = render(<AIDiffBadge state="accepted" />);
    // The badge is a span with visible text content.
    const badge = container.querySelector("span");
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toBeTruthy();
  });
});
