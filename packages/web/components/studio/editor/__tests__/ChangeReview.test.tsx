/**
 * ChangeReview component tests — adoption of the shared AIDiffView (CR-AUFG-07-18 Task 14).
 *
 * Asserts:
 *  - the shared AIDiffView renders accessible <ins>/<del>
 *  - toggle aria-labels use i18n keys (no hard-coded English — RULE-16)
 *  - the state badge reflects the accepted state
 *  - onToggle fires with the change id
 *
 * i18n: setupTests.ts globally mocks next-intl to return the key as the text.
 * Tests therefore assert i18n KEYS (e.g. "aiDiff.acceptChange"), matching the
 * established repo convention.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ChangeDetail } from "@/lib/api/coauthor";
import { ChangeReview } from "../ChangeReview";

const change: ChangeDetail = {
  id: "ch-1",
  change_type: "word_choice",
  original_text: "quick",
  revised_text: "swift",
  index: 0,
};

describe("ChangeReview (adopted — CR-AUFG-07-18)", () => {
  it("renders the shared AIDiffView with accessible ins/del", () => {
    const { container } = render(<ChangeReview change={change} isAccepted={false} />);

    expect(container.querySelector("ins")).not.toBeNull();
    expect(container.querySelector("del")).not.toBeNull();
  });

  it("uses i18n aria-labels for the toggle (no hard-coded English)", () => {
    render(<ChangeReview change={change} isAccepted={false} onToggle={vi.fn()} />);

    // Accessible name resolves to the wired key under the global mock.
    expect(screen.getByRole("button", { name: "aiDiff.acceptChange" })).toBeTruthy();
  });

  it("uses the reject aria-label when already accepted", () => {
    render(<ChangeReview change={change} isAccepted={true} onToggle={vi.fn()} />);

    expect(screen.getByRole("button", { name: "aiDiff.rejectChange" })).toBeTruthy();
  });

  it("reflects the accepted state in the AIDiffView badge", () => {
    render(<ChangeReview change={change} isAccepted={true} onToggle={vi.fn()} />);

    // AIDiffBadge renders the dedicated accepted-state key.
    expect(screen.getByText("aiDiff.accepted")).toBeTruthy();
  });

  it("invokes onToggle with the change id on click", () => {
    const onToggle = vi.fn();
    render(<ChangeReview change={change} isAccepted={false} onToggle={onToggle} />);

    fireEvent.click(screen.getByRole("button", { name: "aiDiff.acceptChange" }));

    expect(onToggle).toHaveBeenCalledWith("ch-1");
  });

  it("omits the toggle button in read-only mode", () => {
    render(<ChangeReview change={change} isAccepted={false} readOnly />);

    expect(screen.queryByRole("button")).toBeNull();
  });
});
