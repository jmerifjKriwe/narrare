"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { aiSettingsApi, setupApi } from "@/lib/api/client";
import type { AIProvider, UserProvider } from "@/types";

interface ProviderFormProps {
  readonly existingProvider?: UserProvider | null;
  readonly onSaved: (provider: UserProvider) => void;
  readonly onCancel: () => void;
}

export function ProviderForm({ existingProvider, onSaved, onCancel }: ProviderFormProps) {
  const t = useTranslations("settings-ai.providerForm");
  const tProviders = useTranslations("settings-ai.providers");
  const isEdit = !!existingProvider;

  const PROVIDER_OPTIONS: { value: AIProvider; label: string }[] = [
    { value: "anthropic", label: tProviders("anthropic") },
    { value: "openai", label: tProviders("openai") },
    { value: "google", label: tProviders("google") },
    { value: "groq", label: tProviders("groq") },
    { value: "ollama", label: tProviders("ollamaLocal") },
    { value: "openrouter", label: tProviders("openrouter") },
    { value: "zai", label: tProviders("zai") },
  ];

  const [providerName, setProviderName] = useState<AIProvider>(
    (existingProvider?.provider_name as AIProvider) ?? "anthropic",
  );
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [baseUrl, setBaseUrl] = useState(existingProvider?.base_url ?? "");
  const [validating, setValidating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationSuccess, setValidationSuccess] = useState(false);

  const handleValidate = async () => {
    setError(null);
    setValidationSuccess(false);
    setValidating(true);
    try {
      await setupApi.validateStep4({
        provider: providerName,
        api_key: apiKey,
        model: "test",
        ollama_url: "http://localhost:11434",
      });
      setValidationSuccess(true);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("validationFailed");
      setError(msg);
    } finally {
      setValidating(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      let result: UserProvider;
      if (isEdit && existingProvider) {
        const updateData: Record<string, unknown> = {};
        if (apiKey) updateData.api_key = apiKey;
        if (baseUrl !== (existingProvider.base_url ?? "")) updateData.base_url = baseUrl || null;
        result = await aiSettingsApi.updateProvider(
          existingProvider.id,
          updateData as Parameters<typeof aiSettingsApi.updateProvider>[1],
        );
      } else {
        result = await aiSettingsApi.createProvider({
          provider_name: providerName,
          api_key: apiKey,
          base_url: baseUrl || null,
        });
      }
      onSaved(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("saveFailed");
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {isEdit ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">
            {t("provider")}
          </span>
          <span className="text-[0.9375rem] text-[var(--color-text-primary)] capitalize">
            {existingProvider.provider_name}
          </span>
        </div>
      ) : (
        <Select
          label={t("provider")}
          value={providerName}
          onChange={(e) => setProviderName(e.target.value as AIProvider)}
          options={PROVIDER_OPTIONS}
        />
      )}

      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="api-key-input"
          className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]"
        >
          {t("apiKey")}
        </label>
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              id="api-key-input"
              type={showApiKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={isEdit ? t("apiKeyPlaceholder") : t("apiKeyEnter")}
              autoComplete="off"
              className="w-full px-4 py-3 border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] text-[var(--color-text-primary)] text-[0.9375rem] font-[family-name:var(--font-sans)] transition-all duration-300 outline-none placeholder:text-[var(--color-text-placeholder)] focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)]/15 focus:shadow-[0_0_0_4px_var(--color-accent-light)] pr-10"
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)] text-[0.75rem]"
              aria-label={showApiKey ? t("hideApiKey") : t("showApiKey")}
            >
              {showApiKey ? t("hide") : t("show")}
            </button>
          </div>
          {!isEdit && apiKey && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleValidate}
              loading={validating}
            >
              {t("validate")}
            </Button>
          )}
        </div>
        {validationSuccess && (
          <p className="text-[0.8125rem] text-green-600">{t("validationSuccess")}</p>
        )}
      </div>

      {providerName !== "ollama" && (
        <Input
          label={t("baseUrlOptional")}
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder={t("baseUrlPlaceholder")}
          hint={t("baseUrlTooltip")}
        />
      )}

      {error && (
        <div
          className="bg-[var(--color-error)]/10 text-[var(--color-error)] rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          {t("cancel")}
        </Button>
        <Button type="submit" loading={saving} disabled={!isEdit && !apiKey}>
          {isEdit ? t("updateProvider") : t("addProvider")}
        </Button>
      </div>
    </form>
  );
}
