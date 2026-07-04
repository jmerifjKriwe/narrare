/**
 * use-panel-focus hook tests (Task 7).
 *
 * Covers the drawer focus lifecycle for PanelShell (spec §5.3, Phase C §10.1):
 * focus move-in on open, Escape to close, and focus return to the opener on
 * close. The hook stays presentation-only and uses native DOM APIs only (no
 * new dependency — spec §3).
 *
 * Note: a Tab focus-trap is intentionally NOT provided here. PanelShell's
 * adopter (EditorRightPanelSlot) renders inline at the `lg` breakpoint
 * (`lg:static`), where a global Tab-trap would lock the keyboard inside the
 * panel and prevent reaching the editor. The mobile sheet is not a full modal.
 * Trapping is therefore omitted rather than guessed.
 */
import { act, renderHook } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePanelFocus } from "@/lib/hooks/use-panel-focus";

function setup(open: boolean) {
  const onClose = vi.fn();
  const panel = document.createElement("div");
  const focusable = document.createElement("button");
  focusable.type = "button";
  panel.appendChild(focusable);
  document.body.appendChild(panel);
  const opener = document.createElement("button");
  opener.type = "button";
  document.body.appendChild(opener);
  opener.focus();

  const { rerender } = renderHook(
    (props: { open: boolean }) => {
      const ref = useRef<HTMLElement | null>(panel);
      usePanelFocus({ open: props.open, panelRef: ref, onClose });
      return ref;
    },
    { initialProps: { open } },
  );
  return { onClose, panel, focusable, opener, rerender };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("usePanelFocus", () => {
  it("moves focus into the panel when it opens", () => {
    const { focusable } = setup(true);
    expect(document.activeElement).toBe(focusable);
  });

  it("does not move focus or attach listeners when closed", () => {
    const { onClose } = setup(false);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("calls onClose on Escape while open", () => {
    const { onClose } = setup(true);
    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("restores focus to the opener when it closes", () => {
    const { opener, rerender } = setup(true);
    rerender({ open: false });
    expect(document.activeElement).toBe(opener);
  });

  it("always invokes the latest onClose even if its identity changes", () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(
      (props: { onClose: () => void }) => {
        const ref = useRef<HTMLElement | null>(document.body);
        usePanelFocus({ open: true, panelRef: ref, onClose: props.onClose });
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
