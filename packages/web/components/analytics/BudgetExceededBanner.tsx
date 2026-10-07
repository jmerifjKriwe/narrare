"use client";

/**
 * BudgetExceededBanner — dismissible hard-stop notice for the 429
 * BUDGET_EXCEEDED error (STATS-002 budgets, ADR-094 spec A-8).
 *
 * The 429 only ever fires in block mode (warn mode never blocks at the
 * `ModelRegistry.get_model()` gate), so one block-mode text is correct:
 * it explains that AI calls are stopped and points to the AI settings.
 * Pure presentation — the panel owns the error mapping (isBudgetExceededError)
 * and the dismissal state (RULE-06/RULE-13).
 */

import { X } from "lucide-react";
import { useTranslations } from "next-intl";

interface BudgetExceededBannerProps {
  readonly onDismiss: () => void;
}

export function BudgetExceededBanner({ onDismiss }: BudgetExceededBannerProps) {
  const t = useTranslations("analytics.budget");

  return (
    <div
      role="alert"
      data-testid="costs-budget-banner"
      className="flex items-start gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
    >
      <div className="flex-1 space-y-0.5">
        <p className="font-medium">{t("bannerTitle")}</p>
        <p className="text-destructive/90">{t("bannerBody")}</p>
      </div>
      <button
        type="button"
        aria-label={t("bannerDismiss")}
        onClick={onDismiss}
        className="shrink-0 rounded-md p-1 hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X aria-hidden="true" className="h-4 w-4" />
      </button>
    </div>
  );
}
