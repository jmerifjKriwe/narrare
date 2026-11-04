// @vitest-environment jsdom
/**
 * The dialog trigger's paint, pinned at the API: R37's default is the quiet
 * secondary — a dialog trigger is an opener, not the page's action — and the
 * old hardcoded `bg-primary` cannot sneak back past this guard. Only a
 * caller that is its screen's one primary passes "primary", so the primary
 * string is asserted exactly as `buttonClass` spells it.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { buttonClass } from "./Button";
import { Dialog } from "./Dialog";

afterEach(cleanup);

describe("Dialog's trigger paint", () => {
  it("wears the quiet secondary by default", () => {
    render(
      <Dialog title="Ein Titel" triggerLabel="Öffnen">
        {() => <p>Inhalt</p>}
      </Dialog>,
    );
    const trigger = screen.getByRole("button", { name: "Öffnen" });
    expect(trigger.className).toContain(buttonClass("secondary", "md"));
  });

  it("wears the primary only when the caller passes it", () => {
    render(
      <Dialog title="Ein Titel" triggerLabel="Öffnen" triggerVariant="primary">
        {() => <p>Inhalt</p>}
      </Dialog>,
    );
    const trigger = screen.getByRole("button", { name: "Öffnen" });
    expect(trigger.className).toContain(buttonClass("primary", "md"));
  });
});
