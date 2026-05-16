"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import type { CreateProviderRequest, UpdateProviderRequest } from "@/types";

// --- Provider label map ---

const PROVIDER_OPTIONS: { value: string; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic / Claude" },
  { value: "google", label: "Google / Gemini" },
  { value: "ollama", label: "Ollama (Local)" },
  { value: "openrouter", label: "OpenRouter" },
];

export function providerLabel(name: string): string {
  return PROVIDER_OPTIONS.find((p) => p.value === name)?.label ?? name;
}

// --- Provider Form ---

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

export function ProviderForm({
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
