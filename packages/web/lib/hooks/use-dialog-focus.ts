"use client";

import { type RefObject, useEffect, useRef } from "react";

interface UseDialogFocusOptions {
  /** Whether the dialog is currently open. */
  readonly open: boolean;
  /** Ref to the dialog container whose focusables we manage. */
  readonly dialogRef: RefObject<HTMLElement | null>;
  /** Invoked when the user dismisses the dialog with Escape. */
  readonly onClose: () => void;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

/**
 * Modal dialog focus lifecycle (WAI-ARIA dialog pattern):
 *  - on open: remember the opener (currently focused element) and move focus to
 *    the first focusable element inside the dialog;
 *  - while open: Escape closes, and Tab/Shift+Tab are trapped within the dialog
 *    (cycles between first and last focusable) so focus never leaves the modal
 *    overlay;
 *  - on close: restore focus to the remembered opener.
 *
 * Native DOM only — no new dependency (matches `usePanelFocus` philosophy and
 * the NewSeriesDialog "dependency-free" note). Unlike `usePanelFocus` (which
 * intentionally does NOT trap Tab because PanelShell renders inline on
 * desktop), this IS a true focus trap: modal dialogs must lock focus while open
 * (WAI-ARIA APG dialog pattern).
 *
 * `onClose` is read through a ref so the effect does not re-run when the caller
 * passes a fresh callback identity on every render (mirrors `usePanelFocus`).
 */
export function useDialogFocus({ open, dialogRef, onClose }: UseDialogFocusOptions) {
  const openerRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement as HTMLElement | null;

    const dialog = dialogRef.current;
    if (dialog) {
      dialog.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    }

    function getFocusables(): HTMLElement[] {
      const dialog = dialogRef.current;
      if (!dialog) return [];
      return Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE));
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const focusables = getFocusables();
      if (focusables.length === 0) {
        // No focusable child — keep focus on the dialog container itself.
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }

      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;

      if (event.shiftKey) {
        // Shift+Tab on the first element → wrap to the last.
        if (active === first || !dialogRef.current?.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else {
        // Tab on the last element → wrap to the first.
        if (active === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      openerRef.current?.focus();
    };
  }, [open, dialogRef]);
}
