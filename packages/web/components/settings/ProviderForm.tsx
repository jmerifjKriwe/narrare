"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { aiSettingsApi, setupApi } from "@/lib/api/client";
import { getProviderLabel, PROVIDERS } from "@/lib/providers";
import type { AIProvider, UserProvider } from "@/types";

interface ProviderFormProps {
  readonly existingProvider?: UserProvider | null;
  readonly onSaved: (provider: UserProvider) => void;
  readonly onCancel: () => void;
}

export function ProviderForm({ existingProvider, onSaved, onCancel }: ProviderFormProps) {
  const t = useTranslations("settings-ai.providerForm");
  const isEdit = !!existingProvider;

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
          <span className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            {t("provider")}
          </span>
          <span className="text-[0.9375rem] text-foreground">
            {getProviderLabel(existingProvider.provider_name)}
          </span>
        </div>
      ) : (
        <Select
          label={t("provider")}
          value={providerName}
          onChange={(e) => setProviderName(e.target.value as AIProvider)}
          options={PROVIDERS}
        />
      )}

      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="api-key-input"
           className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-muted-foreground"
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
              className="w-full px-4 py-3 border border-border rounded-xl bg-card text-foreground text-[0.9375rem] transition-all duration-300 outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/15 pr-10"
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-muted-foreground text-[0.75rem]"
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
          className="bg-destructive/10 text-destructive rounded-lg p-3 text-[0.875rem]"
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
