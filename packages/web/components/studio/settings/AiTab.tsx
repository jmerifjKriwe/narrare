"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { AdvancedAiSettings } from "./AdvancedAiSettings";
import { BudgetSection } from "./BudgetSection";
import { DefaultModelSection } from "./DefaultModelSection";
import { ModelDataStatus } from "./ModelDataStatus";
import { ProviderList } from "./ProviderList";
import { useAiTabData } from "./useAiTabData";

export function AiTab() {
  const t = useTranslations("studio");
  const data = useAiTabData();
  const { providers, providersLoading, aiSettings, modelsData, modelsLoading } = data;

  if (providersLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("settings.ai.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("settings.ai.description")}</p>
      </div>
      <div className="space-y-4">
        {/* Provider management */}
        <ProviderList providers={providers} isLoading={providersLoading} />

        {/* Model data refresh */}
        <ModelDataStatus />

        {/* Default model */}
        <DefaultModelSection
          aiSettings={aiSettings}
          providers={providers}
          modelsData={modelsData}
          modelsLoading={modelsLoading}
          onProviderChange={data.handleDefaultProviderChange}
          onModelChange={data.handleDefaultModelChange}
        />

        {/* Monthly budget (STATS-002 budgets, ADR-094) */}
        <BudgetSection
          aiSettings={aiSettings}
          onBudgetChange={data.handleMonthlyBudgetChange}
          onBudgetModeChange={data.handleBudgetModeChange}
          saveFailed={data.budgetSaveFailed}
        />

        {/* Advanced settings (collapsible — CR-AUFG-07-32 progressive disclosure).
            The five power-user sections live in <AdvancedAiSettings>, collapsed
            by default behind a "Erweiterte Einstellungen" disclosure. */}
        <AdvancedAiSettings data={data} />

        {/* System prompts info */}
        <div className="bg-muted/30 border border-border rounded-lg p-4 text-sm text-muted-foreground">
          {t("settings.ai.promptsInfo")}
        </div>
      </div>
    </div>
  );
}
