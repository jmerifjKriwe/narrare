"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GhostTextOnboardingProps {
  /** The anchor element (ghost text span) to position the tooltip near. */
  readonly anchorElement: HTMLElement | null;
  /** Called when the onboarding hint is dismissed or auto-dismissed. */
  readonly onDismiss: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = "narrare:ghostTextOnboardingShown";
const AUTO_DISMISS_MS = 5000;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * GhostTextOnboarding — first-use hint shown near ghost text suggestions.
 *
 * Displays a small tooltip with keyboard shortcuts (Tab / ArrowRight / Esc)
 * and auto-dismisses after 5 seconds. Only shown once per browser (tracked
 * via localStorage).
 */
export function GhostTextOnboarding({ anchorElement, onDismiss }: GhostTextOnboardingProps) {
  const t = useTranslations("studio");
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);

  // Auto-dismiss after 5 seconds
  useEffect(() => {
    const timer = setTimeout(onDismiss, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  // Position near the anchor element
  useEffect(() => {
    if (!anchorElement) return;

    const updatePosition = () => {
      const rect = anchorElement.getBoundingClientRect();
      setPosition({
        top: rect.bottom + 8,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - 320)),
      });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    return () => window.removeEventListener("resize", updatePosition);
  }, [anchorElement]);

  if (!position) return null;

  return (
    <div
      className="fixed z-50 px-3 py-2 rounded-lg bg-card border border-border shadow-lg text-xs text-muted-foreground animate-[overlay-show_0.3s_ease-out]"
      style={{ top: position.top, left: position.left }}
      role="status"
    >
      <span>{t("ghostText.onboardingHint")}</span>
      <button
        type="button"
        onClick={onDismiss}
        className="ml-2 text-muted-foreground/60 hover:text-foreground transition-colors"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns true if the onboarding has already been shown. */
export function isGhostTextOnboardingShown(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(STORAGE_KEY) === "true";
}

/** Marks the onboarding as shown so it won't appear again. */
export function markGhostTextOnboardingShown(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, "true");
}

/**
 * Hook to manage ghost text onboarding visibility.
 * Returns [shouldShow, dismiss] — only shows once.
 */
export function useGhostTextOnboarding() {
  const [shouldShow, setShouldShow] = useState(() => !isGhostTextOnboardingShown());

  const dismiss = useCallback(() => {
    setShouldShow(false);
    markGhostTextOnboardingShown();
  }, []);

  return { shouldShow, dismiss } as const;
}
