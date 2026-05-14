"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { CategoryOverrides } from "@/components/settings/CategoryOverrides";
import { CustomTokenLimits } from "@/components/settings/CustomTokenLimits";
import { IntentOverrides } from "@/components/settings/IntentOverrides";
import { TokenLimitProfileSelector } from "@/components/settings/TokenLimitProfileSelector";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { aiSettingsApi, setupApi } from "@/lib/api/client";
import type {
  AIProvider,
  ModelOverride,
  TokenLimitOverride,
  TokenLimitProfile,
  UserAiSettings,
  UserProvider,
} from "@/types";

export default function AiModelPage() {
  const t = useTranslations("settings-ai.modelPage");
  const [settings, setSettings] = useState<UserAiSettings | null>(null);
  const [providers, setProviders] = useState<UserProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [defaultProviderId, setDefaultProviderId] = useState("");
  const [defaultModel, setDefaultModel] = useState("");

  const [categoryOverrides, setCategoryOverrides] = useState<Record<string, ModelOverride>>({});
  const [intentOverrides, setIntentOverrides] = useState<Record<string, ModelOverride>>({});

  const [tokenLimitProfile, setTokenLimitProfile] = useState<TokenLimitProfile>("balanced");
  const [tokenLimitOverrides, setTokenLimitOverrides] = useState<
    Record<string, TokenLimitOverride>
  >({});

  const [modelOptions, setModelOptions] = useState<
    Record<string, { value: string; label: string }[]>
  >({});
  const [loadingModels, setLoadingModels] = useState<Record<string, boolean>>({});

  const activeProviders = providers.filter((p) => p.is_active);
  const providerOptions = activeProviders.map((p) => ({
    value: p.id,
    label: `${p.provider_name}${p.base_url ? ` ${t("customUrl")}` : ""}`,
  }));

  const loadModelsForProvider = useCallback(
    async (providerId: string) => {
      if (modelOptions[providerId] || loadingModels[providerId]) return;

      const provider = providers.find((p) => p.id === providerId);
      if (!provider) return;

      setLoadingModels((prev) => ({ ...prev, [providerId]: true }));
      try {
        const providerName = provider.provider_name as AIProvider;
        const result = await setupApi.getProviderModels(providerName, "");
        const opts = result.models.map((m) => ({ value: m.id, label: m.name }));
        setModelOptions((prev) => ({ ...prev, [providerId]: opts }));
      } catch {
        // Silently fail — user can enter model ID manually
      } finally {
        setLoadingModels((prev) => ({ ...prev, [providerId]: false }));
      }
    },
    [providers, modelOptions, loadingModels],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [settingsResult, providersResult] = await Promise.all([
          aiSettingsApi.getUserSettings(),
          aiSettingsApi.listProviders(),
        ]);
        if (cancelled) return;

        setSettings(settingsResult);
        setProviders(providersResult);
        setDefaultProviderId(settingsResult.default_provider_id ?? "");
        setDefaultModel(settingsResult.default_model ?? "");
        setCategoryOverrides(
          (settingsResult.category_overrides as Record<string, ModelOverride>) ?? {},
        );
        setIntentOverrides(
          (settingsResult.intent_overrides as Record<string, ModelOverride>) ?? {},
        );
        setTokenLimitProfile(settingsResult.token_limit_profile as TokenLimitProfile);
        setTokenLimitOverrides(
          (settingsResult.token_limit_overrides as Record<string, TokenLimitOverride>) ?? {},
        );
      } catch (e: unknown) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : t("loadFailed");
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();
    return () => {
      cancelled = true;
    };
  }, [t]);

  useEffect(() => {
    if (defaultProviderId) {
      loadModelsForProvider(defaultProviderId);
    }
  }, [defaultProviderId, loadModelsForProvider]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await aiSettingsApi.updateUserSettings({
        default_provider_id: defaultProviderId || null,
        default_model: defaultModel || undefined,
        category_overrides: categoryOverrides,
        intent_overrides: intentOverrides,
        token_limit_profile: tokenLimitProfile,
        token_limit_overrides: tokenLimitProfile === "custom" ? tokenLimitOverrides : undefined,
      });
      setSettings(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("saveFailed");
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="text-[var(--color-text-tertiary)]">{t("loading")}</span>
      </div>
    );
  }

  if (error && !settings) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <p className="text-[var(--color-error)]" role="alert">
          {error}
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => window.location.reload()}
        >
          {t("retry")}
        </Button>
      </div>
    );
  }

  const currentModelOptions = defaultProviderId ? (modelOptions[defaultProviderId] ?? []) : [];
  const isModelLoading = defaultProviderId ? (loadingModels[defaultProviderId] ?? false) : false;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">{t("title")}</h1>
        <p className="text-[0.875rem] text-[var(--color-text-secondary)] mt-1">
          {t("description")}
        </p>
      </div>

      {/* Default Model Section */}
      <section className="flex flex-col gap-5">
        <h2 className="text-[0.9375rem] font-semibold text-[var(--color-text-primary)]">
          {t("defaultModel")}
        </h2>

        {activeProviders.length === 0 ? (
          <div className="border border-dashed border-[var(--color-border)] rounded-xl p-6 text-center">
            <p className="text-[var(--color-text-secondary)]">{t("noActiveProviders")}</p>
            <a
              href="/settings/ai-providers"
              className="text-[var(--color-accent)] text-[0.875rem] hover:underline mt-1 inline-block"
            >
              {t("addProviderLink")}
            </a>
          </div>
        ) : (
          <div className="border border-[var(--color-border)] rounded-xl p-5 bg-[var(--color-surface)]">
            <div className="grid grid-cols-2 gap-4">
              <Select
                label={t("provider")}
                value={defaultProviderId}
                onChange={(e) => {
                  setDefaultProviderId(e.target.value);
                  setDefaultModel("");
                }}
                options={providerOptions}
                placeholder={t("selectProvider")}
              />
              <div>
                {isModelLoading ? (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">
                      {t("model")}
                    </span>
                    <span className="text-[0.8125rem] text-[var(--color-text-tertiary)] py-3">
                      {t("loadingModels")}
                    </span>
                  </div>
                ) : currentModelOptions.length > 0 ? (
                  <Select
                    label={t("model")}
                    value={defaultModel}
                    onChange={(e) => setDefaultModel(e.target.value)}
                    options={currentModelOptions}
                    placeholder={t("selectModel")}
                  />
                ) : (
                  <div className="flex flex-col gap-1.5">
                    <label
                      htmlFor="default-model-input"
                      className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]"
                    >
                      {t("model")}
                    </label>
                    <input
                      id="default-model-input"
                      type="text"
                      value={defaultModel}
                      onChange={(e) => setDefaultModel(e.target.value)}
                      placeholder={t("enterModelId")}
                      className="w-full px-4 py-3 border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] text-[var(--color-text-primary)] text-[0.9375rem] transition-all duration-300 outline-none placeholder:text-[var(--color-text-placeholder)] focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)]/15"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Separator */}
      <hr className="border-[var(--color-border)]" />

      {/* Category Overrides */}
      <CategoryOverrides
        overrides={categoryOverrides}
        providers={providers}
        onChange={setCategoryOverrides}
        modelOptions={modelOptions}
        loadingModels={loadingModels}
      />

      {/* Intent Overrides (Advanced) */}
      <IntentOverrides
        overrides={intentOverrides}
        providers={providers}
        onChange={setIntentOverrides}
        modelOptions={modelOptions}
        loadingModels={loadingModels}
      />

      {/* Separator */}
      <hr className="border-[var(--color-border)]" />

      {/* Token Limits */}
      <TokenLimitProfileSelector value={tokenLimitProfile} onChange={setTokenLimitProfile} />

      {tokenLimitProfile === "custom" && (
        <CustomTokenLimits overrides={tokenLimitOverrides} onChange={setTokenLimitOverrides} />
      )}

      {/* Error / Success */}
      {error && (
        <div
          className="bg-[var(--color-error)]/10 text-[var(--color-error)] rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 text-green-700 rounded-lg p-3 text-[0.875rem]">
          {t("saveSuccess")}
        </div>
      )}

      {/* Save Button */}
      <div className="flex justify-end pt-2">
        <Button type="button" onClick={handleSave} loading={saving}>
          {t("saveSettings")}
        </Button>
      </div>
    </div>
  );
}
