"use client";

import { ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ContextTier } from "@/types";
import { DEFAULT_TIER_PERCENTAGES } from "./aiTabConstants";
import { CategoryOverrides } from "./CategoryOverrides";
import { ContextBudget } from "./ContextBudget";
import { IntentOverrides } from "./IntentOverrides";
import { SystemTimeouts } from "./SystemTimeouts";
import { TokenProfileSection } from "./TokenProfileSection";
import type { AiTabData } from "./useAiTabData";

/** Props for the advanced (power-user) AI settings disclosure. */
export interface AdvancedAiSettingsProps {
  data: Pick<
    AiTabData,
    | "aiSettings"
    | "providers"
    | "tokenLimitsData"
    | "providerModelsCache"
    | "loadingModels"
    | "handleTokenProfileChange"
    | "handleCustomOutputLimitChange"
    | "handleCategoryOverridesChange"
    | "handleIntentOverridesChange"
    | "handleTierPercentagesChange"
    | "handleSystemTimeoutsChange"
  >;
}

/**
 * Collapsible "Advanced settings" disclosure (CR-AUFG-07-32 progressive
 * disclosure). Holds the five power-user sections so non-technical users are
 * not overwhelmed: token profile, category/intent overrides, context budget
 * and system timeouts. Collapsed by default; expanded by activating the
 * summary toggle. Pure presentation — all state lives in {@link useAiTabData}.
 */
export function AdvancedAiSettings({ data }: AdvancedAiSettingsProps) {
  const t = useTranslations("studio");
  const {
    aiSettings,
    providers,
    tokenLimitsData,
    providerModelsCache,
    loadingModels,
    handleTokenProfileChange,
    handleCustomOutputLimitChange,
    handleCategoryOverridesChange,
    handleIntentOverridesChange,
    handleTierPercentagesChange,
    handleSystemTimeoutsChange,
  } = data;

  const currentProfile = tokenLimitsData?.token_profile ?? "balanced";

  return (
    <details className="group">
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden bg-card border border-border rounded-lg p-6 flex items-center gap-3 hover:bg-accent/50">
        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
          <ChevronDown className="w-5 h-5 transition-transform duration-200 group-open:rotate-180" />
        </div>
        <div>
          <h3 className="font-medium">{t("settings.ai.advancedSettings")}</h3>
          <p className="text-sm text-muted-foreground">{t("settings.ai.advancedSettingsHint")}</p>
        </div>
      </summary>

      <div className="space-y-4 mt-4">
        {/* Token limit profile */}
        <TokenProfileSection
          currentProfile={currentProfile}
          outputLimit={
            tokenLimitsData?.output_limit ?? tokenLimitsData?.effective_output_limit ?? 2000
          }
          metadata={tokenLimitsData?.metadata ?? null}
          calibration={tokenLimitsData?.calibration ?? null}
          suitability={tokenLimitsData?.suitability ?? null}
          onProfileChange={handleTokenProfileChange}
          onCustomOutputLimitChange={handleCustomOutputLimitChange}
        />

        {/* Category Overrides */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <span className="text-lg">{"\uD83D\uDCC2"}</span>
            </div>
            <div>
              <h3 className="font-medium">{t("settings.ai.categoryOverrides.title")}</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.ai.categoryOverrides.description")}
              </p>
            </div>
          </div>
          <CategoryOverrides
            overrides={aiSettings?.category_overrides ?? {}}
            providers={providers}
            onChange={handleCategoryOverridesChange}
            modelOptions={providerModelsCache}
            loadingModels={loadingModels}
          />
        </div>

        {/* Intent Overrides */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <span className="text-lg">{"\uD83D\uDD27"}</span>
            </div>
            <div>
              <h3 className="font-medium">{t("settings.ai.intentOverrides.title")}</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.ai.intentOverrides.description")}
              </p>
            </div>
          </div>
          <IntentOverrides
            overrides={aiSettings?.intent_overrides ?? {}}
            providers={providers}
            onChange={handleIntentOverridesChange}
            modelOptions={providerModelsCache}
            loadingModels={loadingModels}
          />
        </div>

        {/* Context Budget */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <span className="text-lg">{"\uD83D\uDCCA"}</span>
            </div>
            <div>
              <h3 className="font-medium">{t("settings.ai.contextBudget.title")}</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.ai.contextBudget.description")}
              </p>
            </div>
          </div>
          <ContextBudget
            percentages={
              tokenLimitsData?.tier_percentages
                ? (Object.fromEntries(
                    Object.entries(tokenLimitsData.tier_percentages).map(([k, v]) => [
                      k,
                      Math.round(v * 100),
                    ]),
                  ) as Record<ContextTier, number>)
                : DEFAULT_TIER_PERCENTAGES
            }
            onChange={handleTierPercentagesChange}
            disabled={!tokenLimitsData}
          />
        </div>

        {/* System Timeouts */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <span className="text-lg">{"\u23F1\uFE0F"}</span>
            </div>
            <div>
              <h3 className="font-medium">{t("settings.ai.systemTimeouts.title")}</h3>
              <p className="text-sm text-muted-foreground">
                {t("settings.ai.systemTimeouts.description")}
              </p>
            </div>
          </div>
          <SystemTimeouts
            wsTimeout={tokenLimitsData?.ws_timeout ?? 1800}
            onChange={handleSystemTimeoutsChange}
            disabled={!tokenLimitsData}
          />
        </div>
      </div>
    </details>
  );
}
