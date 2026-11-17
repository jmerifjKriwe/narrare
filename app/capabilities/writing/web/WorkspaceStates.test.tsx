// @vitest-environment jsdom
/**
 * The workspace's leave guard (W4 Task 12) — `workspace-states` KACHEL 10,
 * the Abschiedsschutz: a calm modal over the scrimmed editor that asks before
 * unsaved words are left behind. „Bleiben" is the safe default (focus lands
 * on it, Escape stays); „Verwerfen und verlassen" carries the honest
 * second-step wording — the consequence named on the control itself. The
 * dialog only ever appears after a write actually failed (the page flushes a
 * healthy pending body first); here it is driven directly.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";

import { LeaveGuardDialog } from "./WorkspaceStates";

const de = catalogs.de;

beforeEach(() => {
  applyLocale("de");
});

afterEach(() => {
  cleanup();
});

function mount(onStay = vi.fn(), onDiscard = vi.fn()) {
  render(<LeaveGuardDialog onStay={onStay} onDiscard={onDiscard} />);
  return { onStay, onDiscard };
}

describe("the Abschiedsschutz face (KACHEL 10)", () => {
  it("is a labelled modal alertdialog with the drafted copy", () => {
    mount();
    const dialog = screen.getByRole("alertdialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByText(de["writing.workspace.guard.title"])).toBeTruthy();
    expect(screen.getByText(de["writing.workspace.guard.body"])).toBeTruthy();
    expect(
      screen.getByRole("button", { name: de["writing.workspace.guard.stay"] }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: de["writing.workspace.guard.discard"] }),
    ).toBeTruthy();
    // The dialog names itself through its own heading.
    const labelledBy = dialog.getAttribute("aria-labelledby");
    expect(labelledBy).toBeTruthy();
    expect(document.getElementById(labelledBy as string)?.textContent).toBe(
      de["writing.workspace.guard.title"],
    );
  });

  it("the discard control carries the honest second-step wording", () => {
    mount();
    const discard = screen.getByRole("button", { name: de["writing.workspace.guard.discard"] });
    expect(discard.getAttribute("title")).toBe(de["writing.workspace.guard.discardNote"]);
  });

  it("focus lands on Bleiben — the safe default", () => {
    mount();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: de["writing.workspace.guard.stay"] }),
    );
  });

  it("Bleiben stays; Verwerfen und verlassen discards", () => {
    const stay = mount();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.stay"] }));
    expect(stay.onStay).toHaveBeenCalledTimes(1);
    expect(stay.onDiscard).not.toHaveBeenCalled();
    cleanup();
    const discard = mount();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.discard"] }));
    expect(discard.onDiscard).toHaveBeenCalledTimes(1);
    expect(discard.onStay).not.toHaveBeenCalled();
  });

  it("Escape stays — never discards by accident", () => {
    const { onStay, onDiscard } = mount();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onStay).toHaveBeenCalledTimes(1);
    expect(onDiscard).not.toHaveBeenCalled();
  });

  it("Tab wraps inside the panel — the modal weight", () => {
    mount();
    const stay = screen.getByRole("button", { name: de["writing.workspace.guard.stay"] });
    const discard = screen.getByRole("button", { name: de["writing.workspace.guard.discard"] });
    // Two controls: from the last, Tab wraps to the first.
    discard.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(stay);
    // From the first, Shift+Tab wraps to the last.
    stay.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(discard);
  });
});

/** The guard the way the page raises it: a focused control asks to leave,
 *  the flush fails, the dialog mounts over it; an answer unmounts the
 *  dialog as the page's own state does. The opener keeps the focus it had
 *  when the click raised the guard (jsdom does not focus on click). */
function mountOverOpener(onStay = vi.fn(), onDiscard = vi.fn()) {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <div>
        <button type="button" id="opener" onClick={() => setOpen(true)}>
          opener
        </button>
        {open && (
          <LeaveGuardDialog
            onStay={() => {
              onStay();
              setOpen(false);
            }}
            onDiscard={() => {
              onDiscard();
              setOpen(false);
            }}
          />
        )}
      </div>
    );
  }
  render(<Harness />);
  const opener = screen.getByRole("button", { name: "opener" });
  opener.focus();
  fireEvent.click(opener);
  return { onStay, onDiscard, opener };
}

describe("the focus return — neither path strands the writer", () => {
  it("Bleiben returns focus to the control that raised the guard", () => {
    const { opener } = mountOverOpener();
    // The safe answer holds the focus while the question stands.
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: de["writing.workspace.guard.stay"] }),
    );
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.stay"] }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("Verwerfen und verlassen returns focus too — the discard is no stranding", () => {
    const { opener } = mountOverOpener();
    fireEvent.click(screen.getByRole("button", { name: de["writing.workspace.guard.discard"] }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });
});
