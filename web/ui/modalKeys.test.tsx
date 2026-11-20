// @vitest-environment jsdom
/**
 * The shell's modal keyboard discipline (#895): one home for the trap the
 * writing dialogs grew three copies of — Tab wraps inside the panel at both
 * ends, Escape answers through the caller's own rule, the same FOCUSABLE
 * population. The hook owns the wrap and the population; the Escape answer
 * (close, stay, hold while busy or dirty) stays with the caller.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FOCUSABLE, useModalKeys } from "./modalKeys";

afterEach(cleanup);

function Panel({ onEscape, disabledLast = false }: { onEscape: () => void; disabledLast?: boolean }) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  useModalKeys(panelRef, onEscape);
  return (
    <div ref={panelRef} role="dialog" aria-modal="true" aria-label="panel">
      <button type="button">first</button>
      <input aria-label="middle" />
      <button type="button" disabled={disabledLast}>
        last
      </button>
    </div>
  );
}

/** A suspended panel (a confirm standing over the form it came from): the
 *  trap must stand down while another dialog owns the keyboard. */
function SuspendedPanel({ onEscape, enabled }: { onEscape: () => void; enabled: boolean }) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  useModalKeys(panelRef, onEscape, { enabled });
  return (
    <div ref={panelRef} role="dialog" aria-label="suspended">
      <button type="button">only</button>
    </div>
  );
}

describe("useModalKeys", () => {
  it("Tab on the last control wraps to the first", () => {
    render(<Panel onEscape={vi.fn()} />);
    const first = screen.getByRole("button", { name: "first" });
    const last = screen.getByRole("button", { name: "last" });
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
  });

  it("Shift+Tab on the first control wraps to the last", () => {
    render(<Panel onEscape={vi.fn()} />);
    const first = screen.getByRole("button", { name: "first" });
    const last = screen.getByRole("button", { name: "last" });
    first.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
  });

  it("Tab from outside the panel lands on the first control", () => {
    render(
      <div>
        <button type="button">outside</button>
        <Panel onEscape={vi.fn()} />
      </div>,
    );
    screen.getByRole("button", { name: "outside" }).focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "first" }));
  });

  it("Shift+Tab from outside the panel lands on the last control", () => {
    render(
      <div>
        <button type="button">outside</button>
        <Panel onEscape={vi.fn()} />
      </div>,
    );
    screen.getByRole("button", { name: "outside" }).focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "last" }));
  });

  it("a disabled control stays out of the trap's population", () => {
    render(<Panel onEscape={vi.fn()} disabledLast />);
    const input = screen.getByLabelText("middle");
    input.focus();
    // The last live control is the input now — Tab wraps to the first.
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "first" }));
  });

  it("Escape answers through the caller's own rule", () => {
    const onEscape = vi.fn();
    render(<Panel onEscape={onEscape} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it("other keys pass through untouched", () => {
    const onEscape = vi.fn();
    render(<Panel onEscape={onEscape} />);
    const first = screen.getByRole("button", { name: "first" });
    first.focus();
    fireEvent.keyDown(document, { key: "a" });
    fireEvent.keyDown(document, { key: "Enter" });
    expect(onEscape).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(first);
  });

  it("the discipline leaves with the panel — unmount unbinds it", () => {
    const onEscape = vi.fn();
    const { unmount } = render(<Panel onEscape={onEscape} />);
    unmount();
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.keyDown(document, { key: "Tab" });
    expect(onEscape).not.toHaveBeenCalled();
  });

  it("a disabled trap neither answers Escape nor steals Tab", () => {
    // The destructive-confirm stack (W6): the form beneath the confirm
    // stands down — its trap must not eat the confirm's Tab presses.
    const onEscape = vi.fn();
    render(
      <div>
        <SuspendedPanel onEscape={onEscape} enabled={false} />
        <button type="button">elsewhere</button>
      </div>,
    );
    const elsewhere = screen.getByRole("button", { name: "elsewhere" });
    elsewhere.focus();
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.keyDown(document, { key: "Tab" });
    expect(onEscape).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(elsewhere);
  });

  it("FOCUSABLE names every live control kind the dialogs offer", () => {
    // The one selector the three homes shared — pinned so a later edit
    // cannot quietly narrow the trap's population.
    expect(FOCUSABLE).toContain("button:not([disabled])");
    expect(FOCUSABLE).toContain("input:not([disabled])");
    expect(FOCUSABLE).toContain("select:not([disabled])");
    expect(FOCUSABLE).toContain("textarea:not([disabled])");
    expect(FOCUSABLE).toContain("a[href]");
    expect(FOCUSABLE).toContain('[tabindex]:not([tabindex="-1"])');
  });
});
