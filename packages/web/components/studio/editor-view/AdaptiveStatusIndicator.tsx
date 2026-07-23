"use client";

/**
 * AdaptiveStatusIndicator — the always-visible adaptivity signal in the editor
 * toolbar (ADR-069 Decision 14).
 *
 * Derives a 3-state status directly from the canonical adaptive context
 * ({@link useAdaptiveContext}, ADR-069 D15 TanStack key) so it stays in lockstep
 * with the Adaptive Dashboard and the Dialogue Coach panel:
 *   - active  : enabled + has_any_signal   → brand-coloured, gently pulsing
 *   - paused  : disabled + has_any_signal  → muted
 *   - no-data : no signal                  → dashed/outline
 *
 * The status is computed during render (never mirrored into state) — it is pure
 * derived state, so the indicator never drifts from the query cache.
 *
 * Clicking the trigger opens a non-modal popover (keeps the writer in flow)
 * with a one-line explanation and a "Manage in Settings" deep-link to the
 * Learning tab. Keyboard behaviour: Escape dismisses and returns focus to the
 * trigger; a pointer-down outside also dismisses it. The state is always
 * conveyed by icon + label, never by colour alone (WAI-ARIA). Native DOM only
 * — no new dependency (mirrors the {@link usePanelFocus} ethos).
 */
import { Activity, CircleDashed, type LucideIcon, Pause } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";
import { useAdaptiveContext } from "@/lib/hooks/useAdaptiveContext";

type IndicatorState = "active" | "paused" | "no-data";

const STATE_ICON: Record<IndicatorState, LucideIcon> = {
  active: Activity,
  paused: Pause,
  "no-data": CircleDashed,
};

/** i18n leaf key per state (resolves `adaptive.indicator.<key>`). */
const STATE_LABEL_KEY: Record<IndicatorState, string> = {
  active: "active",
  paused: "paused",
  "no-data": "noData",
};

function deriveState(enabled: boolean, hasSignal: boolean): IndicatorState {
  if (enabled && hasSignal) return "active";
  if (!enabled && hasSignal) return "paused";
  return "no-data";
}

export function AdaptiveStatusIndicator({ novelId }: { readonly novelId: string }) {
  const t = useTranslations("adaptive");
  const { data } = useAdaptiveContext(novelId);
  const [open, setOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverId = useId();

  const state = deriveState(data?.enabled ?? false, data?.has_any_signal ?? false);
  const labelKey = STATE_LABEL_KEY[state];
  const Icon = STATE_ICON[state];

  // Escape dismisses the popover and returns focus to the trigger (non-modal).
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  // A pointer-down landing outside the indicator dismisses the popover.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      const container = containerRef.current;
      if (container && !container.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        ref={triggerRef}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
        onClick={() => setOpen((value) => !value)}
        className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-sm transition-colors ${
          state === "active"
            ? "text-violet-600 dark:text-violet-400"
            : "text-muted-foreground hover:text-foreground"
        }`}
      >
        <Icon
          aria-hidden="true"
          className={`h-3.5 w-3.5 ${state === "active" ? "animate-pulse" : ""}`}
        />
        <span>{t(`indicator.${labelKey}`)}</span>
      </button>

      {open && (
        <div
          id={popoverId}
          role="dialog"
          aria-label={t("indicator.popoverLabel")}
          className="absolute right-0 top-full z-50 mt-1 w-64 rounded-lg border border-border bg-card p-3 shadow-lg"
        >
          <p className="mb-1 text-sm font-medium text-foreground">{t(`indicator.${labelKey}`)}</p>
          <p className="mb-2 text-xs text-muted-foreground">
            {t(`indicator.description.${labelKey}`)}
          </p>
          <Link
            href={`/novel/${novelId}/settings?category=learning`}
            className="text-xs text-violet-600 hover:underline dark:text-violet-400"
          >
            {t("indicator.manage")}
          </Link>
        </div>
      )}
    </div>
  );
}
