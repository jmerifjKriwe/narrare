"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";

/** localStorage key that tracks tour completion. */
export const TOUR_STORAGE_KEY = "narrare:featureTourCompleted";

export interface TourStep {
  /** CSS selector for the element to spotlight. Omit to center the tooltip. */
  target?: string;
  /** i18n key (relative to `studio` namespace) for the step title. */
  titleKey: string;
  /** i18n key (relative to `studio` namespace) for the step description. */
  descriptionKey: string;
}

interface FeatureTourProps {
  steps: TourStep[];
}

export function FeatureTour({ steps }: FeatureTourProps) {
  const t = useTranslations("studio");
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [mounted, setMounted] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);

  // SSR guard — portal needs document
  useEffect(() => {
    setMounted(true);
  }, []);

  // Activate on first visit (no completion flag in localStorage)
  useEffect(() => {
    if (!mounted || steps.length === 0) return;
    setActive(localStorage.getItem(TOUR_STORAGE_KEY) !== "true");
  }, [mounted, steps.length]);

  // Measure target element whenever the step changes
  useEffect(() => {
    if (!active) return;
    const step = steps[stepIndex];
    if (!step?.target) {
      setRect(null);
      return;
    }

    const el = document.querySelector(step.target);
    if (!el) {
      setRect(null);
      return;
    }

    const measure = () => setRect(el.getBoundingClientRect());
    measure();
    el.scrollIntoView({ behavior: "smooth", block: "center" });

    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [active, stepIndex, steps]);

  const complete = useCallback(() => {
    localStorage.setItem(TOUR_STORAGE_KEY, "true");
    setActive(false);
  }, []);

  const next = useCallback(() => {
    if (stepIndex < steps.length - 1) {
      setStepIndex(stepIndex + 1);
    } else {
      complete();
    }
  }, [stepIndex, steps.length, complete]);

  const back = useCallback(() => {
    if (stepIndex > 0) setStepIndex(stepIndex - 1);
  }, [stepIndex]);

  // Keyboard navigation
  useEffect(() => {
    if (!active) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") complete();
      if (e.key === "ArrowRight") next();
      if (e.key === "ArrowLeft" && stepIndex > 0) back();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [active, stepIndex, back, complete, next]);

  if (!mounted || !active || steps.length === 0) return null;

  const step = steps[stepIndex];
  if (!step) return null;
  const isLast = stepIndex === steps.length - 1;

  return createPortal(
    <div className="fixed inset-0 z-[100]" role="dialog" aria-label={t(step.titleKey)}>
      {/* Overlay — spotlight cut-out when target exists, plain overlay otherwise */}
      {rect ? (
        <div
          className="rounded-lg"
          style={{
            position: "fixed",
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
            zIndex: 1,
            boxShadow: "0 0 0 2px var(--primary), 0 0 0 9999px rgba(0,0,0,0.4)",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-black/40" />
      )}

      {/* Tooltip */}
      <div
        className="absolute bg-card border border-border rounded-xl shadow-2xl p-5"
        style={{ ...getTooltipPosition(rect), zIndex: 2, maxWidth: "24rem" }}
      >
        <div className="flex gap-1.5" aria-hidden="true">
          {steps.map((s) => (
            <div
              key={s.titleKey}
              className={
                s.titleKey === step.titleKey
                  ? "w-2 h-2 rounded-full bg-primary"
                  : "w-2 h-2 rounded-full bg-muted"
              }
            />
          ))}
        </div>
        <p className="text-sm font-medium mt-3">{t(step.titleKey)}</p>
        <p className="text-sm text-muted-foreground mt-1">{t(step.descriptionKey)}</p>
        <div className="flex items-center gap-3 mt-4">
          <button
            type="button"
            onClick={complete}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            {t("tour.skip")}
          </button>
          {stepIndex > 0 && (
            <button
              type="button"
              onClick={back}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              {t("tour.back")}
            </button>
          )}
          <button
            type="button"
            onClick={next}
            className="bg-primary text-primary-foreground rounded-md px-4 py-1.5 text-sm ml-auto"
          >
            {isLast ? t("tour.done") : t("tour.next")}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

// ---------------------------------------------------------------------------
// Tooltip positioning & public helpers
// ---------------------------------------------------------------------------

const TW = 384; // max-w-sm ≈ 24rem
const GAP = 12;

function getTooltipPosition(targetRect: DOMRect | null): React.CSSProperties {
  if (!targetRect) {
    return { top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: TW };
  }
  let top = targetRect.bottom + GAP;
  let left = targetRect.left + targetRect.width / 2 - TW / 2;
  if (left < 16) left = 16;
  if (left + TW > window.innerWidth - 16) left = window.innerWidth - 16 - TW;
  if (top + 200 > window.innerHeight) top = targetRect.top - GAP - 180;
  if (top < 16) top = 16;
  return { top, left, width: TW };
}

/** Remove the completion flag so the tour auto-starts on next mount. */
export function requestFeatureTour(): void {
  if (typeof window !== "undefined") localStorage.removeItem(TOUR_STORAGE_KEY);
}
