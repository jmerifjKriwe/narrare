"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { aiSettingsApi } from "@/lib/api/client";
import type { ModelOverride, TokenLimitOverride, TokenLimitProfile } from "@/types";
import { CategoryOverrides } from "./CategoryOverrides";
import { CustomTokenLimits } from "./CustomTokenLimits";
import { IntentOverrides } from "./IntentOverrides";
import { ProviderList } from "./ProviderList";

// --- Token profile options ---

const TOKEN_PROFILES: { value: TokenLimitProfile; labelKey: string }[] = [
  { value: "quick", labelKey: "settings.ai.tokenProfileQuick" },
  { value: "balanced", labelKey: "settings.ai.tokenProfileBalanced" },
  { value: "long_texts", labelKey: "settings.ai.tokenProfileLong" },
  { value: "custom", labelKey: "settings.ai.tokenProfileCustom" },
];

// --- Main AI Tab ---

export function AiTab() {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  const [showCustomLimits, setShowCustomLimits] = useState(false);

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
    updateAiSettingsMutation.mutate({ token_limit_profile: profile });
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

  function handleTokenLimitOverridesChange(
    tokenLimitOverrides: Record<string, TokenLimitOverride>,
  ) {
    updateAiSettingsMutation.mutate({ token_limit_overrides: tokenLimitOverrides });
  }

  // Pre-load models for active category overrides
  if (aiSettings?.category_overrides) {
    for (const override of Object.values(aiSettings.category_overrides)) {
      if (override.provider_id && !providerModelsCache[override.provider_id]) {
        loadModelsForProvider(override.provider_id);
      }
    }
  }

  // --- Render ---

  if (providersLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const currentProfile = aiSettings?.token_limit_profile ?? "balanced";

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("settings.ai.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("settings.ai.description")}</p>
      </div>
      <div className="space-y-4">
        {/* Provider management */}
        <ProviderList providers={providers} isLoading={providersLoading} />

        {/* Default model */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <span className="text-lg">🎯</span>
            </div>
            <div>
              <h3 className="font-medium">{t("settings.ai.defaultModel")}</h3>
            </div>
          </div>
          <div className="space-y-4 ml-15">
            <div className="flex items-center justify-between">
              <span className="text-sm">{t("settings.ai.providerName")}</span>
              <select
                value={aiSettings?.default_provider_id ?? ""}
                onChange={(e) => handleDefaultProviderChange(e.target.value)}
                className="px-4 py-2 bg-background border border-border rounded-md text-sm"
              >
                <option value="">{t("settings.ai.noneSelected")}</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.provider_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="h-px bg-border" />
            <div className="flex items-center justify-between">
              <span className="text-sm">{t("settings.ai.defaultModel")}</span>
              {modelsLoading ? (
                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
              ) : (
                <select
                  value={aiSettings?.default_model ?? ""}
                  onChange={(e) => handleDefaultModelChange(e.target.value)}
                  disabled={!aiSettings?.default_provider_id}
                  className="px-4 py-2 bg-background border border-border rounded-md text-sm disabled:opacity-50"
                >
                  <option value="">{t("settings.ai.selectProviderFirst")}</option>
                  {modelsData?.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        </div>

        {/* Token limit profile */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <span className="text-lg">⚡</span>
            </div>
            <div>
              <h3 className="font-medium">{t("settings.ai.tokenProfile")}</h3>
            </div>
          </div>
          <div className="ml-15">
            <select
              value={currentProfile}
              onChange={(e) => handleTokenProfileChange(e.target.value as TokenLimitProfile)}
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            >
              {TOKEN_PROFILES.map(({ value, labelKey }) => (
                <option key={value} value={value}>
                  {t(labelKey)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Category Overrides */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
              <span className="text-lg">📂</span>
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
              <span className="text-lg">🔧</span>
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

        {/* Custom Token Limits (only when profile is "custom") */}
        {currentProfile === "custom" && (
          <div className="bg-card border border-border rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                  <span className="text-lg">🎛️</span>
                </div>
                <div>
                  <h3 className="font-medium">{t("settings.ai.tokenLimits.title")}</h3>
                  <p className="text-sm text-muted-foreground">
                    {t("settings.ai.tokenLimits.description")}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowCustomLimits(!showCustomLimits)}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {showCustomLimits
                  ? t("settings.ai.intentOverrides.collapse")
                  : t("settings.ai.intentOverrides.advanced")}
              </button>
            </div>
            {showCustomLimits && (
              <CustomTokenLimits
                overrides={aiSettings?.token_limit_overrides ?? {}}
                onChange={handleTokenLimitOverridesChange}
              />
            )}
          </div>
        )}

        {/* System prompts info */}
        <div className="bg-muted/30 border border-border rounded-lg p-4 text-sm text-muted-foreground">
          {t("settings.ai.promptsInfo")}
        </div>
      </div>
    </div>
  );
}
