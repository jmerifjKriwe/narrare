/**
 * use-dialog-focus hook tests.
 *
 * Covers the modal-dialog focus lifecycle (WAI-ARIA APG dialog pattern) used
 * by NewSeriesDialog (spec SERIES-001): focus move-in on open, Escape to
 * close, Tab / Shift+Tab trapping within the dialog (wrapping between the
 * first and last focusable), and focus restore to the opener on close. The
 * hook is presentation-only and uses native DOM APIs only (no new dependency).
 *
 * Unlike `usePanelFocus` (which intentionally does NOT trap because PanelShell
 * renders inline on desktop), this hook IS a true focus trap — modal dialogs
 * must lock keyboard focus while open.
 *
 * Branch coverage targets every decision point in `use-dialog-focus.ts`:
 *   - `!open` early return (no focus management while closed);
 *   - `dialog` null / present and `querySelector(FOCUSABLE)` hit / miss;
 *   - `getFocusables` null-dialog guard;
 *   - Escape close; non-Escape / non-Tab early return;
 *   - empty-focusables fallback (focus the dialog container itself);
 *   - Tab wrap at the last focusable; Shift+Tab wrap at the first focusable or
 *     when focus is outside the dialog; no wrap from a middle element.
 */
import { act, renderHook } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useDialogFocus } from "@/lib/hooks/use-dialog-focus";

/**
 * Renders the hook against a real dialog subtree with `focusableCount`
 * focusable children. The opener is focused before the hook mounts so the
 * hook records it as the restore target.
 */
function setup(open: boolean, focusableCount = 3) {
  const onClose = vi.fn();
  const dialog = document.createElement("div");
  const focusables: HTMLElement[] = [];
  for (let i = 0; i < focusableCount; i++) {
    const button = document.createElement("button");
    button.type = "button";
    dialog.appendChild(button);
    focusables.push(button);
  }
  document.body.appendChild(dialog);

  const opener = document.createElement("button");
  opener.type = "button";
  document.body.appendChild(opener);
  opener.focus();

  const { rerender } = renderHook(
    (props: { open: boolean }) => {
      const ref = useRef<HTMLElement | null>(dialog);
      useDialogFocus({ open: props.open, dialogRef: ref, onClose });
      return ref;
    },
    { initialProps: { open } },
  );
  return { onClose, dialog, focusables, opener, rerender };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("useDialogFocus", () => {
  it("does not move focus or attach key listeners while closed", () => {
    const { onClose, opener } = setup(false);
    expect(document.activeElement).toBe(opener);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("moves focus to the first focusable when opened", () => {
    const { focusables } = setup(true);
    expect(document.activeElement).toBe(focusables[0]);
  });

  it("does not move focus when the dialog has no focusable children", () => {
    const { opener } = setup(true, 0);
    expect(document.activeElement).toBe(opener);
  });

  it("does not crash when dialogRef.current is null and still closes on Escape", () => {
    const onClose = vi.fn();
    renderHook(() => {
      const ref = useRef<HTMLElement | null>(null);
      useDialogFocus({ open: true, dialogRef: ref, onClose });
    });
    expect(document.activeElement).toBe(document.body);

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    });
    expect(onClose).not.toHaveBeenCalled();

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("keeps focus on the dialog container when it has no focusables and Tab is pressed", () => {
    const { dialog, onClose } = setup(true, 0);
    dialog.tabIndex = -1;
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Tab" }));
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(dialog);
  });

  it("calls onClose on Escape while open and prevents the default action", () => {
    const { onClose } = setup(true);
    const event = new KeyboardEvent("keydown", { key: "Escape", cancelable: true });
    act(() => {
      window.dispatchEvent(event);
    });
    expect(onClose).toHaveBeenCalledOnce();
    expect(event.defaultPrevented).toBe(true);
  });

  it("ignores non-Escape, non-Tab keys while open", () => {
    const { onClose } = setup(true);
    const event = new KeyboardEvent("keydown", { key: "Enter", cancelable: true });
    act(() => {
      window.dispatchEvent(event);
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(event.defaultPrevented).toBe(false);
  });

  it("restores focus to the opener when closed", () => {
    const { opener, rerender } = setup(true);
    rerender({ open: false });
    expect(document.activeElement).toBe(opener);
  });

  it("wraps Tab from the last focusable to the first", () => {
    const { focusables } = setup(true);
    act(() => {
      focusables[focusables.length - 1].focus();
    });
    const event = new KeyboardEvent("keydown", { key: "Tab", cancelable: true });
    act(() => {
      window.dispatchEvent(event);
    });
    expect(event.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(focusables[0]);
  });

  it("does not wrap Tab from a middle focusable", () => {
    const { focusables } = setup(true);
    act(() => {
      focusables[1].focus();
    });
    const event = new KeyboardEvent("keydown", { key: "Tab", cancelable: true });
    act(() => {
      window.dispatchEvent(event);
    });
    expect(event.defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(focusables[1]);
  });

  it("wraps Shift+Tab from the first focusable to the last", () => {
    const { focusables } = setup(true);
    act(() => {
      focusables[0].focus();
    });
    const event = new KeyboardEvent("keydown", {
      key: "Tab",
      shiftKey: true,
      cancelable: true,
    });
    act(() => {
      window.dispatchEvent(event);
    });
    expect(event.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(focusables[focusables.length - 1]);
  });

  it("wraps Shift+Tab to the last when focus is outside the dialog", () => {
    const { focusables, opener } = setup(true);
    act(() => {
      opener.focus();
    });
    const event = new KeyboardEvent("keydown", {
      key: "Tab",
      shiftKey: true,
      cancelable: true,
    });
    act(() => {
      window.dispatchEvent(event);
    });
    expect(event.defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(focusables[focusables.length - 1]);
  });

  it("does not wrap Shift+Tab from a middle focusable", () => {
    const { focusables } = setup(true);
    act(() => {
      focusables[1].focus();
    });
    const event = new KeyboardEvent("keydown", {
      key: "Tab",
      shiftKey: true,
      cancelable: true,
    });
    act(() => {
      window.dispatchEvent(event);
    });
    expect(event.defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(focusables[1]);
  });

  it("always invokes the latest onClose even when its identity changes", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(
      (props: { onClose: () => void }) => {
        const ref = useRef<HTMLElement | null>(document.body);
        useDialogFocus({ open: true, dialogRef: ref, onClose: props.onClose });
        return ref;
      },
      { initialProps: { onClose: first } },
    );
    rerender({ onClose: second });
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledOnce();
  });
});
