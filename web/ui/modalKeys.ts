import { useEffect, type RefObject } from "react";

/**
 * The modal keyboard discipline, one shell home (#895): the trap the
 * writing dialogs grew verbatim in three places — TreeDialogs'
 * `useModalKeys`, the LeaveGuardDialog's and the NewBookDialog's inline
 * keydown effects — extracted before the book-settings dialog family
 * (W4 Task 19) grew a fourth copy. The shell is the home because the
 * dialogs span capabilities (rule 1: a capability never imports another
 * capability's code).
 *
 * The shared contract is the trap population and the wrap: Tab wraps
 * inside the panel at both ends, and a focus outside the panel is pulled
 * back in. The Escape ANSWER stays the caller's own rule — close, stay,
 * hold while busy or dirty — handed in as `onEscape`; the hook only
 * prevents the default and calls it. Unmount unbinds both.
 */

/** The trap's population: every live control inside the panel, in DOM
 *  order — disabled controls and negative tabindex stay out of it. */
export const FOCUSABLE =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

/** Bind the modal's keyboard discipline to one panel: Tab wraps inside it
 *  at both ends; Escape answers through the caller's own rule. `enabled:
 *  false` stands the discipline down without unbinding the caller's tree —
 *  a confirm standing over the form it came from (the W6 destructive
 *  stack) suspends the form's trap so the confirm owns the keyboard. */
export function useModalKeys(
  panelRef: RefObject<HTMLDivElement | null>,
  onEscape: () => void,
  { enabled = true }: { enabled?: boolean } = {},
): void {
  useEffect(() => {
    if (!enabled) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onEscape();
        return;
      }
      if (event.key !== "Tab") return;
      const panel = panelRef.current;
      if (panel === null) return;
      const nodes = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !panel.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last || !panel.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [panelRef, onEscape, enabled]);
}
