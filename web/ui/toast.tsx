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

import { useTranslation } from "@shell/lib/i18n";

import { FOCUS } from "./card";
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
 * is the honest answer for a single-shot confirmation. WCAG 2.2.1: the
 * timer pauses while the pointer rests on the message or a control inside
 * it has focus, resumes when both leave, and the named close button
 * dismisses it at once. The timer lives in the provider and clears on
 * dismiss and unmount, so neither a dismissed toast nor a page that goes
 * away can leave a timer behind.
 */

type Toast = { id: number; message: string };
type ToastApi = { show: (message: string) => void };

const ToastContext = createContext<ToastApi | null>(null);

/** The visible life of one toast. Long enough for a sentence, short enough
 *  that a writer never has to dismiss it — and pausable for the writer who
 *  needs longer. */
const TOAST_LIFETIME_MS = 6000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const t = useTranslation();
  const [toast, setToast] = useState<Toast | null>(null);
  // A hovered or focused toast holds its remaining time; the two are
  // separate because leaving the pointer while focus stays inside must not
  // resume the timer.
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const nextId = useRef(0);
  const remaining = useRef(TOAST_LIFETIME_MS);
  const startedAt = useRef<number | null>(null);
  const timer = useRef<number | null>(null);
  const paused = hovered || focused;

  const show = useCallback((message: string) => {
    nextId.current += 1;
    remaining.current = TOAST_LIFETIME_MS;
    startedAt.current = null;
    setHovered(false);
    setFocused(false);
    setToast({ id: nextId.current, message });
  }, []);

  const dismiss = useCallback(() => {
    setToast(null);
    setHovered(false);
    setFocused(false);
  }, []);

  useEffect(() => {
    if (toast === null) return;
    if (paused) {
      // The transition's cleanup banked the elapsed part of the lifetime;
      // nothing runs while the reader rests on the message.
      return;
    }
    startedAt.current = Date.now();
    const id = toast.id;
    timer.current = window.setTimeout(() => {
      timer.current = null;
      setToast((current) => (current !== null && current.id === id ? null : current));
    }, remaining.current);
    return () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
        timer.current = null;
      }
      if (startedAt.current !== null) {
        remaining.current = Math.max(0, remaining.current - (Date.now() - startedAt.current));
        startedAt.current = null;
      }
    };
  }, [toast, paused]);

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
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            onFocus={() => setFocused(true)}
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                setFocused(false);
              }
            }}
            className="pointer-events-auto flex max-w-md items-start gap-2 rounded-lg border border-rule bg-panel px-3 py-2 shadow-overlay"
          >
            <span className="mt-0.5 shrink-0 text-success">
              <Icon name="check" size={14} />
            </span>
            <span className="flex-1 text-meta font-medium leading-snug text-foreground">
              {toast.message}
            </span>
            <button
              type="button"
              aria-label={t("shell.toast.dismiss")}
              onClick={dismiss}
              className={`-mr-1 shrink-0 rounded p-0.5 text-muted transition-colors hover:text-foreground ${FOCUS}`}
            >
              <Icon name="cross" size={12} />
            </button>
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
