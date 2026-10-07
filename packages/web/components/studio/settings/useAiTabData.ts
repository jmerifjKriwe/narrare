"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { aiSettingsApi, tokenLimitsApi } from "@/lib/api/client";
import type { ContextTier, ModelOverride, TokenLimitProfile } from "@/types";
import { buildTokenLimitsQuery, normalizeTierPercentages } from "./useAiTabDataHelpers";
import { useBudgetSettingsSave } from "./useBudgetSettingsSave";
import { useProviderModelCache } from "./useProviderModelCache";

/** All data-fetching, mutations, and handler logic for the AI settings tab. */
export function useAiTabData() {
  const queryClient = useQueryClient();

  // Data fetching
  const { data: providers = [], isLoading: providersLoading } = useQuery({
    queryKey: ["settings", "ai", "providers"],
    queryFn: aiSettingsApi.listProviders,
  });

  const { data: aiSettings } = useQuery({
    queryKey: ["settings", "ai"],
    queryFn: aiSettingsApi.getUserSettings,
  });

  const { data: modelsData, isLoading: modelsLoading } = useQuery({
    queryKey: ["settings", "ai", "models", aiSettings?.default_provider_id],
    queryFn: () => aiSettingsApi.getProviderModels(aiSettings!.default_provider_id!),
    enabled: !!aiSettings?.default_provider_id,
  });

  const { data: tokenLimitsData } = useQuery({
    queryKey: [
      "settings",
      "token-limits",
      aiSettings?.default_provider_id,
      aiSettings?.default_model,
    ],
    queryFn: () => tokenLimitsApi.getResolved(buildTokenLimitsQuery(aiSettings)),
  });

  const { providerModelsCache, loadingModels, loadModelsForProvider } = useProviderModelCache();

  // Settings mutation
  const updateAiSettingsMutation = useMutation({
    mutationFn: aiSettingsApi.updateUserSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai"] });
    },
    onError: (err) => console.error("Failed to update AI settings:", err),
  });

  // Budget save — dedicated mutation + handlers (see useBudgetSettingsSave).
  const { handleMonthlyBudgetChange, handleBudgetModeChange, budgetSaveFailed } =
    useBudgetSettingsSave();

  // Token limits mutation
  const updateTokenLimitsMutation = useMutation({
    mutationFn: tokenLimitsApi.updateUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "token-limits"] });
    },
    onError: (err) => console.error("Failed to update token limits:", err),
  });

  // Handlers
  function handleDefaultProviderChange(providerId: string) {
    updateAiSettingsMutation.mutate({
      default_provider_id: providerId || null,
      default_model: "",
    });
  }

  function handleDefaultModelChange(modelId: string) {
    updateAiSettingsMutation.mutate({ default_model: modelId });
  }

  function handleTokenProfileChange(profile: TokenLimitProfile) {
    updateTokenLimitsMutation.mutate({ token_profile: profile });
  }

  function handleCustomOutputLimitChange(outputLimit: number) {
    updateTokenLimitsMutation.mutate({ token_profile: "custom", output_limit: outputLimit });
  }

  function handleCategoryOverridesChange(categoryOverrides: Record<string, ModelOverride>) {
    updateAiSettingsMutation.mutate({ category_overrides: categoryOverrides });
  }

  function handleIntentOverridesChange(intentOverrides: Record<string, ModelOverride>) {
    for (const override of Object.values(intentOverrides)) {
      if (override.provider_id && !providerModelsCache[override.provider_id]) {
        loadModelsForProvider(override.provider_id);
      }
    }
    updateAiSettingsMutation.mutate({ intent_overrides: intentOverrides });
  }

  function handleTierPercentagesChange(tierPercentages: Record<ContextTier, number>) {
    updateTokenLimitsMutation.mutate({
      tier_percentages: normalizeTierPercentages(tierPercentages),
    });
  }

  function handleSystemTimeoutsChange(values: { ws_timeout?: number }) {
    updateTokenLimitsMutation.mutate(values);
  }

  // Pre-load models for active category overrides
  if (aiSettings?.category_overrides) {
    for (const override of Object.values(aiSettings.category_overrides)) {
      if (override.provider_id && !providerModelsCache[override.provider_id]) {
        loadModelsForProvider(override.provider_id);
      }
    }
  }

  return {
    providers,
    providersLoading,
    aiSettings,
    modelsData,
    modelsLoading,
    tokenLimitsData,
    providerModelsCache,
    loadingModels,
    handleDefaultProviderChange,
    handleDefaultModelChange,
    handleTokenProfileChange,
    handleCustomOutputLimitChange,
    handleCategoryOverridesChange,
    handleIntentOverridesChange,
    handleTierPercentagesChange,
    handleSystemTimeoutsChange,
    handleMonthlyBudgetChange,
    handleBudgetModeChange,
    budgetSaveFailed,
  };
}

/** Inferred return type of {@link useAiTabData} — lets child presentational
 *  components declare precise, auto-syncing prop types via `Pick`. */
export type AiTabData = ReturnType<typeof useAiTabData>;
