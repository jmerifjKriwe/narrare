"use client";

/**
 * QuickCaptureProvider — global quick-capture surface (NOTES-001 §7).
 *
 * Mounts once in the (studio) layout, inside AuthGate (T29b) — a single
 * mount covers shell and non-shell studio pages alike. Owns: open/close
 * state, the Ctrl/⌘+Shift+U shortcut (collision audit: K = palette, S = save,
 * Enter = AI submit; Shift+N rejected — Chrome incognito), and the
 * slide-over panel itself. Any component can open it via `useQuickCapture()`.
 *
 * Escape, the Tab focus trap, initial focus into the panel, and focus
 * restore on close live in `useDialogFocus` (established WAI-ARIA dialog
 * pattern) — unlike NotesChatDrawer, this panel hosts no ChatPanel with
 * its own listener, so the dialog lifecycle must be owned here. The
 * window listener below therefore owns ONLY the capture shortcut.
 */

import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useDialogFocus } from "@/lib/hooks/use-dialog-focus";
import { overlayVariants, panelSlideRightVariants } from "@/lib/motion-variants";
import { QuickCapturePanel } from "./QuickCapturePanel";

interface QuickCaptureContextValue {
  open: () => void;
}

const QuickCaptureContext = createContext<QuickCaptureContextValue>({
  open: () => {},
});

/** Open the quick-capture panel from anywhere below the provider. */
export function useQuickCapture(): QuickCaptureContextValue {
  return useContext(QuickCaptureContext);
}

/** Locked plan decision: Ctrl/⌘+Shift+U (Shift makes the key "U"). */
function isQuickCaptureShortcut(event: KeyboardEvent): boolean {
  return (event.metaKey || event.ctrlKey) && event.shiftKey && event.key === "U";
}

export function QuickCaptureProvider({ children }: { children: ReactNode }) {
  const t = useTranslations("notes");
  const [isOpen, setIsOpen] = useState(false);
  const dialogRef = useRef<HTMLElement>(null);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  // Stable context value: `open` is referentially stable (useCallback), so
  // memoizing the wrapper keeps consumers (Sidebar etc.) from re-rendering on
  // the provider's own isOpen transitions.
  const contextValue = useMemo(() => ({ open }), [open]);

  useDialogFocus({ open: isOpen, dialogRef, onClose: close });

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (isQuickCaptureShortcut(event)) {
        event.preventDefault();
        setIsOpen((value) => !value);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <QuickCaptureContext.Provider value={contextValue}>
      {children}
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              variants={overlayVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
              onClick={close}
              aria-hidden="true"
            />
            <motion.aside
              ref={dialogRef}
              variants={panelSlideRightVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              role="dialog"
              aria-modal="true"
              aria-label={t("quickCapture.open")}
              className="fixed right-0 top-0 z-50 h-full w-full max-w-sm overflow-hidden border-l border-border bg-card shadow-2xl"
            >
              <QuickCapturePanel onClose={close} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </QuickCaptureContext.Provider>
  );
}
