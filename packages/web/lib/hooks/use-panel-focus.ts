import { type RefObject, useEffect, useRef } from "react";

interface UsePanelFocusOptions {
  /** Whether the panel is currently open (drawer active). */
  readonly open: boolean;
  /** Ref to the panel container whose focusables we manage. */
  readonly panelRef: RefObject<HTMLElement | null>;
  /** Invoked when the user dismisses the panel with Escape. */
  readonly onClose: () => void;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/**
 * Drawer focus lifecycle for PanelShell (spec §5.3, Phase C §10.1):
 *  - on open: remember the opener (currently focused element) and move focus
 *    to the first focusable element inside the panel;
 *  - while open: Escape closes (calls `onClose`);
 *  - on close: restore focus to the remembered opener.
 *
 * `onClose` is read through a ref so the effect does not re-run (and re-move
 * focus / re-return focus) when the caller passes a fresh callback identity on
 * every render — the slot rebuilds its close handler each render, so a naive
 * dep would flicker focus on every parent re-render.
 *
 * No Tab focus-trap: PanelShell renders inline at the `lg` breakpoint
 * (`lg:static`), where trapping would lock the keyboard out of the editor.
 * Native DOM only — no new dependency (spec §3).
 */
export function usePanelFocus({ open, panelRef, onClose }: UsePanelFocusOptions) {
  const openerRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement as HTMLElement | null;

    const panel = panelRef.current;
    if (panel) {
      panel.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      openerRef.current?.focus();
    };
  }, [open, panelRef]);
}
