import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Icon } from "./icons";

/**
 * The shell's toast: one short confirmation that floats above the page and
 * goes away on its own — no action, no history, no queue. The approved
 * create screen's fourth state («Entität angelegt · 2 Beziehungen
 * verknüpft») is the first consumer; the interview handover (Task 11) is
 * the next.
 *
 * It is a polite live region, present in the DOM from the first paint so a
 * screen reader hears the message when it appears rather than only finding
 * it later. One message at a time: a second `show` replaces the first, which
 * is the honest answer for a single-shot confirmation. The timer lives in
 * the provider and clears on unmount, so a page that goes away cannot leave
 * a dismissed toast's timer behind.
 */

type Toast = { id: number; message: string };
type ToastApi = { show: (message: string) => void };

const ToastContext = createContext<ToastApi | null>(null);

/** The visible life of one toast. Long enough for a sentence, short enough
 *  that a writer never has to dismiss it. */
const TOAST_LIFETIME_MS = 6000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null);
  const nextId = useRef(0);

  const show = useCallback((message: string) => {
    nextId.current += 1;
    setToast({ id: nextId.current, message });
  }, []);

  useEffect(() => {
    if (toast === null) return;
    const id = toast.id;
    const timer = window.setTimeout(() => {
      setToast((current) => (current !== null && current.id === id ? null : current));
    }, TOAST_LIFETIME_MS);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        data-testid="toast-region"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center px-4"
      >
        {toast !== null && (
          <div
            data-testid="toast"
            className="pointer-events-auto flex max-w-md items-center gap-2 rounded-lg border border-rule bg-panel px-3 py-2 shadow-overlay"
          >
            <span className="shrink-0 text-success">
              <Icon name="check" size={14} />
            </span>
            <span className="text-meta font-medium leading-snug text-foreground">{toast.message}</span>
          </div>
        )}
      </div>
    </ToastContext.Provider>
  );
}

/** The shell's one toast door. Throwing outside the provider is deliberate:
 *  a page that believes it confirmed a write must not silently show nothing. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (api === null) throw new Error("useToast must be used inside ToastProvider");
  return api;
}
