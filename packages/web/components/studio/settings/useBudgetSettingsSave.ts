"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { aiSettingsApi } from "@/lib/api/client";
import type { BudgetMode } from "@/types";

/**
 * Budget-specific AI-settings mutation and handlers (STATS-002 budgets,
 * ADR-094). Separate mutation instance so a failed budget PATCH can surface
 * in the BudgetSection (`saveFailed`) instead of dying in the shared
 * AI-settings mutation's console-only onError (review fix round 1, A6).
 */
export function useBudgetSettingsSave() {
  const queryClient = useQueryClient();

  const [budgetSaveFailed, setBudgetSaveFailed] = useState(false);
  const updateBudgetMutation = useMutation({
    mutationFn: aiSettingsApi.updateUserSettings,
    onSuccess: () => {
      setBudgetSaveFailed(false);
      queryClient.invalidateQueries({ queryKey: ["settings", "ai"] });
    },
    onError: (err) => {
      console.error("Failed to update the monthly budget:", err);
      setBudgetSaveFailed(true);
    },
  });

  /** Monthly budget (STATS-002 budgets, ADR-094): null unsets the budget.
   *  Goes through the budget-specific mutation so failures surface inline. */
  function handleMonthlyBudgetChange(monthlyBudgetUsd: number | null) {
    updateBudgetMutation.mutate({ monthly_budget_usd: monthlyBudgetUsd });
  }

  /** Enforcement mode change; never sends null (backend rejects with 422). */
  function handleBudgetModeChange(budgetMode: BudgetMode) {
    updateBudgetMutation.mutate({ budget_mode: budgetMode });
  }

  return {
    handleMonthlyBudgetChange,
    handleBudgetModeChange,
    budgetSaveFailed,
  };
}
