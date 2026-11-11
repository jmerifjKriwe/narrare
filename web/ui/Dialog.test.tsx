// @vitest-environment jsdom
/**
 * The dialog trigger's paint, pinned at the API: R37's default is the quiet
 * secondary — a dialog trigger is an opener, not the page's action — and the
 * old hardcoded `bg-primary` cannot sneak back past this guard. Only a
 * caller that is its screen's one primary passes "primary", so the primary
 * string is asserted exactly as `buttonClass` spells it. The controlled
 * overlay's contract is pinned beside it: its accessible name, and Escape
 * closing it through `onOpenChange`.
 */
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { buttonClass } from "./Button";
import { Dialog, OverlayDialog } from "./Dialog";

afterEach(cleanup);

describe("Dialog's trigger paint", () => {
  it("wears the quiet secondary by default", () => {
    render(
      <Dialog title="Ein Titel" triggerLabel="Öffnen">
        {() => <p>Inhalt</p>}
      </Dialog>,
    );
    const trigger = screen.getByRole("button", { name: "Öffnen" });
    expect(trigger.className).toContain(buttonClass("secondary", "sm"));
  });

  it("wears the primary only when the caller passes it", () => {
    render(
      <Dialog title="Ein Titel" triggerLabel="Öffnen" triggerVariant="primary">
        {() => <p>Inhalt</p>}
      </Dialog>,
    );
    const trigger = screen.getByRole("button", { name: "Öffnen" });
    expect(trigger.className).toContain(buttonClass("primary", "sm"));
  });
});

describe("OverlayDialog", () => {
  it("labels the controlled dialog and closes through onOpenChange", async () => {
    const onOpenChange = vi.fn();
    render(
      <OverlayDialog
        isOpen
        onOpenChange={onOpenChange}
        overlayClassName="fixed inset-0"
        modalClassName="m-auto"
        dialogClassName="p-6"
        dialogAriaLabel="Palette"
      >
        <p>Inhalt</p>
      </OverlayDialog>,
    );

    expect(screen.getByRole("dialog", { name: "Palette" })).toBeTruthy();

    const user = userEvent.setup();
    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
