"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { BudgetMode, UserAiSettings } from "@/types";

interface BudgetSectionProps {
  readonly aiSettings: UserAiSettings | undefined;
  readonly onBudgetChange: (monthlyBudgetUsd: number | null) => void;
  readonly onBudgetModeChange: (mode: BudgetMode) => void;
  /** True when the budget PATCH failed server-side — surfaced inline. */
  readonly saveFailed?: boolean;
}

/**
 * Accepted amount shapes: non-negative, at most two decimals, at most 8
 * integer digits (mirrors the backend NUMERIC(10,2) / Decimal ge=0 contract
 * — anything else is a 422). The digit cap pins the maximum to 99999999.99
 * client-side, so an over-magnitude value shows the invalid hint instead of
 * dying in a silent 422.
 */
const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/;
const AMOUNT_MAX_INTEGER_DIGITS = 8;

function isAcceptedAmount(raw: string): boolean {
  if (!AMOUNT_PATTERN.test(raw)) return false;
  return raw.split(".")[0].length <= AMOUNT_MAX_INTEGER_DIGITS;
}

/**
 * Monthly AI budget section (STATS-002 budgets, ADR-094 spec A-8).
 *
 * Nullable, clearable USD amount + warn/block enforcement mode. Mirrors the
 * sibling section card markup (DefaultModelSection & co.) and commits the
 * amount on blur/Enter like SystemTimeouts commits its numeric field — no
 * PATCH per keystroke. An empty field commits null (unset); invalid input
 * shows an inline hint and never fires the mutation; a failed budget PATCH
 * surfaces inline via `saveFailed` instead of vanishing into the console.
 */
export function BudgetSection({
  aiSettings,
  onBudgetChange,
  onBudgetModeChange,
  saveFailed = false,
}: BudgetSectionProps) {
  const t = useTranslations("studio");
  const [amountText, setAmountText] = useState("");
  const [invalid, setInvalid] = useState(false);

  // Re-sync the text field whenever the persisted value changes (post-save
  // refetch, initial load). Keystrokes are never clobbered: the prop only
  // changes on a server round-trip.
  const persisted = aiSettings?.monthly_budget_usd ?? null;
  useEffect(() => {
    setAmountText(persisted ?? "");
  }, [persisted]);

  function commitAmount() {
    const raw = amountText.trim();
    const persistedValue = persisted != null ? Number(persisted) : null;
    if (raw === "") {
      if (persistedValue === null) return; // unchanged — no PATCH
      setInvalid(false);
      onBudgetChange(null); // cleared field = unset budget
      return;
    }
    if (!isAcceptedAmount(raw)) {
      setInvalid(true);
      return;
    }
    const value = Number(raw);
    if (value === persistedValue) return; // unchanged — no PATCH
    setInvalid(false);
    onBudgetChange(value);
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
          <span className="text-lg">{"\uD83D\uDCB0"}</span>
        </div>
        <div>
          <h3 className="font-medium">{t("settings.ai.budget.title")}</h3>
          <p className="text-sm text-muted-foreground">{t("settings.ai.budget.description")}</p>
        </div>
      </div>
      <div className="space-y-4 ml-15">
        <div>
          <label htmlFor="monthly-budget" className="block text-sm text-muted-foreground mb-1">
            {t("settings.ai.budget.amountLabel")}
          </label>
          <input
            id="monthly-budget"
            type="text"
            inputMode="decimal"
            value={amountText}
            onChange={(e) => setAmountText(e.target.value)}
            onBlur={commitAmount}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitAmount();
            }}
            placeholder={t("settings.ai.budget.amountPlaceholder")}
            aria-invalid={invalid || saveFailed || undefined}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
          {invalid ? (
            <p className="mt-1 text-xs text-destructive">{t("settings.ai.budget.amountInvalid")}</p>
          ) : saveFailed ? (
            <p className="mt-1 text-xs text-destructive" role="alert">
              {t("settings.ai.budget.amountSaveFailed")}
            </p>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">
              {t("settings.ai.budget.amountHint")}
            </p>
          )}
        </div>
        <div className="h-px bg-border" />
        <div>
          <label htmlFor="budget-mode" className="block text-sm text-muted-foreground mb-1">
            {t("settings.ai.budget.modeLabel")}
          </label>
          <select
            id="budget-mode"
            value={aiSettings?.budget_mode ?? "warn"}
            onChange={(e) => onBudgetModeChange(e.target.value as BudgetMode)}
            className="px-4 py-2 bg-background border border-border rounded-md text-sm"
          >
            <option value="warn">{t("settings.ai.budget.modeWarn")}</option>
            <option value="block">{t("settings.ai.budget.modeBlock")}</option>
          </select>
        </div>
      </div>
    </div>
  );
}
