/**
 * KBMoreFields tests — progressive-disclosure wrapper for optional KB fields.
 *
 * Tests (CR-AUFG-07-32 native <details> pattern):
 * 1. Shows the "more fields" toggle by default
 * 2. Optional children are present in the DOM but hidden by default
 * 3. Children become visible after expanding the disclosure
 * 4. Toggle label switches to "fewer fields" when expanded
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { KBMoreFields } from "@/components/studio/kb/KBMoreFields";

describe("KBMoreFields", () => {
  it("shows the 'more fields' toggle by default", () => {
    render(
      <KBMoreFields>
        <div data-testid="opt">optional</div>
      </KBMoreFields>,
    );

    expect(screen.getByText("kb.moreFields")).toBeDefined();
  });

  it("hides optional children by default (collapsed disclosure)", () => {
    render(
      <KBMoreFields>
        <div data-testid="opt">optional</div>
      </KBMoreFields>,
    );

    // Present in the DOM (so values are submitted) but not visible.
    expect(screen.getByTestId("opt")).not.toBeVisible();
  });

  it("reveals children when the disclosure is expanded", async () => {
    const user = userEvent.setup();
    render(
      <KBMoreFields>
        <div data-testid="opt">optional</div>
      </KBMoreFields>,
    );

    expect(screen.getByTestId("opt")).not.toBeVisible();

    await user.click(screen.getByText("kb.moreFields"));

    expect(screen.getByTestId("opt")).toBeVisible();
  });

  it("switches the toggle label to 'fewer fields' when expanded", async () => {
    const user = userEvent.setup();
    render(
      <KBMoreFields>
        <div data-testid="opt">optional</div>
      </KBMoreFields>,
    );

    await user.click(screen.getByText("kb.moreFields"));

    expect(screen.getByText("kb.fewerFields")).toBeDefined();
    expect(screen.queryByText("kb.moreFields")).toBeNull();
  });
});
