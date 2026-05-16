"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { aiSettingsApi } from "@/lib/api/client";
import type { CreateProviderRequest, TokenLimitProfile, UpdateProviderRequest } from "@/types";

// --- Provider label map ---

const PROVIDER_OPTIONS: { value: string; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic / Claude" },
  { value: "google", label: "Google / Gemini" },
  { value: "ollama", label: "Ollama (Local)" },
  { value: "openrouter", label: "OpenRouter" },
];

const TOKEN_PROFILES: { value: TokenLimitProfile; labelKey: string }[] = [
  { value: "quick", labelKey: "settings.ai.tokenProfileQuick" },
  { value: "balanced", labelKey: "settings.ai.tokenProfileBalanced" },
  { value: "long_texts", labelKey: "settings.ai.tokenProfileLong" },
  { value: "custom", labelKey: "settings.ai.tokenProfileCustom" },
];

function providerLabel(name: string): string {
  return PROVIDER_OPTIONS.find((p) => p.value === name)?.label ?? name;
}

// --- Provider Form (Add / Edit) ---

interface ProviderFormProps {
  mode: "add" | "edit";
  initialProviderName?: string;
  initialBaseUrl?: string | null;
  hasKey?: boolean;
  last4?: string;
  onSubmit: (data: CreateProviderRequest | UpdateProviderRequest) => void;
  onCancel: () => void;
  isPending: boolean;
  t: (key: string) => string;
}

function ProviderForm({
  mode,
  initialProviderName,
  initialBaseUrl,
  hasKey,
  last4,
  onSubmit,
  onCancel,
  isPending,
  t,
}: ProviderFormProps) {
  const [providerName, setProviderName] = useState(initialProviderName ?? "openai");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(initialBaseUrl ?? "");

  function handleSubmit() {
    if (mode === "add") {
      onSubmit({
        provider_name: providerName,
        api_key: apiKey,
        base_url: baseUrl || null,
      } satisfies CreateProviderRequest);
    } else {
      const payload: UpdateProviderRequest = {};
      if (apiKey) payload.api_key = apiKey;
      if (baseUrl !== (initialBaseUrl ?? "")) payload.base_url = baseUrl || null;
      onSubmit(payload);
    }
  }

  return (
    <div className="space-y-4 ml-15">
      {mode === "add" && (
        <div>
          <label htmlFor="provider-name" className="block text-sm font-medium mb-1.5">
            {t("settings.ai.providerName")}
          </label>
          <select
            id="provider-name"
            value={providerName}
            onChange={(e) => setProviderName(e.target.value)}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          >
            {PROVIDER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      )}
      <div>
        <label htmlFor="provider-api-key" className="block text-sm font-medium mb-1.5">
          {mode === "edit" ? t("settings.ai.editApiKey") : t("settings.ai.apiKey")}
        </label>
        <input
          id="provider-api-key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          placeholder={
            mode === "edit" && hasKey
              ? `••••••••${last4 ?? ""}`
              : t("settings.ai.apiKeyPlaceholder")
          }
        />
        {mode === "edit" && hasKey && (
          <p className="text-xs text-muted-foreground mt-1">{t("settings.ai.apiKeyHint")}</p>
        )}
      </div>
      <div>
        <label htmlFor="provider-base-url" className="block text-sm font-medium mb-1.5">
          {t("settings.ai.baseUrl")}
        </label>
        <input
          id="provider-base-url"
          type="text"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          placeholder="https://api.openai.com/v1"
        />
      </div>
      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isPending}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {isPending ? t("settings.ai.loading") : t("settings.ai.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          {t("settings.ai.cancel")}
        </button>
      </div>
    </div>
  );
}

// --- Main AI Tab ---

export function AiTab() {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  const [showAddForm, setShowAddForm] = useState(false);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

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

  // Mutations
  const createProviderMutation = useMutation({
    mutationFn: (data: CreateProviderRequest) => aiSettingsApi.createProvider(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai", "providers"] });
      setShowAddForm(false);
    },
    onError: (err) => console.error("Failed to create provider:", err),
  });

  const updateProviderMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProviderRequest }) =>
      aiSettingsApi.updateProvider(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai", "providers"] });
      setEditingProviderId(null);
    },
    onError: (err) => console.error("Failed to update provider:", err),
  });

  const deleteProviderMutation = useMutation({
    mutationFn: (id: string) => aiSettingsApi.deleteProvider(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai", "providers"] });
      setConfirmDeleteId(null);
    },
    onError: (err) => console.error("Failed to delete provider:", err),
  });

  const updateAiSettingsMutation = useMutation({
    mutationFn: aiSettingsApi.updateUserSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai"] });
    },
    onError: (err) => console.error("Failed to update AI settings:", err),
  });

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

  // --- Render ---

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
        {/* Provider list */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                <span className="text-lg">🤖</span>
              </div>
              <div>
                <h3 className="font-medium">{t("settings.ai.provider")}</h3>
                <p className="text-sm text-muted-foreground">
                  {t("settings.ai.providerDescription")}
                </p>
              </div>
            </div>
            {!showAddForm && (
              <button
                type="button"
                onClick={() => setShowAddForm(true)}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>{t("settings.ai.addProvider")}</span>
              </button>
            )}
          </div>

          {/* Add form */}
          {showAddForm && (
            <ProviderForm
              mode="add"
              onSubmit={(data) => createProviderMutation.mutate(data as CreateProviderRequest)}
              onCancel={() => setShowAddForm(false)}
              isPending={createProviderMutation.isPending}
              t={t}
            />
          )}

          {/* Provider list or empty state */}
          {!showAddForm && (
            <div className="ml-15 space-y-2">
              {providers.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-muted-foreground">{t("settings.ai.noProviders")}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {t("settings.ai.noProvidersDescription")}
                  </p>
                </div>
              ) : (
                providers.map((provider) => (
                  <div
                    key={provider.id}
                    className="flex items-center justify-between p-4 rounded-lg border border-border bg-background"
                  >
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="text-sm font-medium">
                          {providerLabel(provider.provider_name)}
                        </p>
                        {provider.has_api_key && provider.api_key_last4 && (
                          <p className="text-xs text-muted-foreground">
                            ••••{provider.api_key_last4}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {editingProviderId === provider.id ? (
                        <ProviderForm
                          mode="edit"
                          initialProviderName={provider.provider_name}
                          initialBaseUrl={provider.base_url}
                          hasKey={provider.has_api_key}
                          last4={provider.api_key_last4}
                          onSubmit={(data) =>
                            updateProviderMutation.mutate({
                              id: provider.id,
                              data: data as UpdateProviderRequest,
                            })
                          }
                          onCancel={() => setEditingProviderId(null)}
                          isPending={updateProviderMutation.isPending}
                          t={t}
                        />
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => setEditingProviderId(provider.id)}
                            className="px-3 py-1.5 text-xs bg-muted rounded-md hover:bg-accent transition-colors"
                          >
                            {t("settings.ai.editApiKey")}
                          </button>
                          {confirmDeleteId === provider.id ? (
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">
                                {t("settings.ai.confirmDelete")}
                              </span>
                              <button
                                type="button"
                                onClick={() => deleteProviderMutation.mutate(provider.id)}
                                disabled={deleteProviderMutation.isPending}
                                className="px-3 py-1.5 text-xs bg-destructive text-destructive-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
                              >
                                {t("settings.ai.deleteProvider")}
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmDeleteId(null)}
                                className="px-3 py-1.5 text-xs bg-muted rounded-md hover:bg-accent transition-colors"
                              >
                                {t("settings.ai.cancel")}
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setConfirmDeleteId(provider.id)}
                              className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"
                              aria-label={t("settings.ai.deleteProvider")}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

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
            {/* Default provider selector */}
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
                    {providerLabel(p.provider_name)}
                  </option>
                ))}
              </select>
            </div>
            <div className="h-px bg-border" />
            {/* Model selector */}
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
              value={aiSettings?.token_limit_profile ?? "balanced"}
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

        {/* System prompts info */}
        <div className="bg-muted/30 border border-border rounded-lg p-4 text-sm text-muted-foreground">
          {t("settings.ai.promptsInfo")}
        </div>
      </div>
    </div>
  );
}
