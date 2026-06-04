"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { aiSettingsApi, tokenLimitsApi } from "@/lib/api/client";
import type { ContextTier, ModelOverride, TokenLimitProfile } from "@/types";

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
    queryKey: ["settings", "token-limits"],
    queryFn: tokenLimitsApi.getResolved,
  });

  // Dynamic model loading per provider (for overrides)
  const [providerModelsCache, setProviderModelsCache] = useState<
    Record<string, { value: string; label: string }[]>
  >({});
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({});

  async function loadModelsForProvider(providerId: string) {
    if (providerModelsCache[providerId] || loadingModels[providerId]) return;
    setLoadingModels((prev) => ({ ...prev, [providerId]: true }));
    try {
      const data = await aiSettingsApi.getProviderModels(providerId);
      setProviderModelsCache((prev) => ({
        ...prev,
        [providerId]: data.models.map((m) => ({ value: m.id, label: m.name })),
      }));
    } catch {
      // Silently fail — the user can still type a model ID manually
    } finally {
      setLoadingModels((prev) => ({ ...prev, [providerId]: false }));
    }
  }

  // Settings mutation
  const updateAiSettingsMutation = useMutation({
    mutationFn: aiSettingsApi.updateUserSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai"] });
    },
    onError: (err) => console.error("Failed to update AI settings:", err),
  });

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
    const normalized: Partial<Record<ContextTier, number>> = {};
    for (const [key, val] of Object.entries(tierPercentages)) {
      normalized[key as ContextTier] = val / 100;
    }
    updateTokenLimitsMutation.mutate({ tier_percentages: normalized });
  }

  function handleSystemTimeoutsChange(values: {
    ws_timeout?: number;
    retry_max_attempts?: number;
    retry_base_delay?: number;
  }) {
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
    handleCategoryOverridesChange,
    handleIntentOverridesChange,
    handleTierPercentagesChange,
    handleSystemTimeoutsChange,
  };
}
