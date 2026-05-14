"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { setupApi } from "@/lib/api/client";
import { getProviderLabel } from "@/lib/providers";
import type { AIProvider } from "@/types";

interface ModelDropdownProps {
  readonly providerName: AIProvider;
  readonly apiKey: string;
  readonly ollamaUrl?: string;
  readonly value: string;
  readonly onChange: (modelId: string) => void;
  readonly label?: string;
}

export function ModelDropdown({
  providerName,
  apiKey,
  ollamaUrl = "http://localhost:11434",
  value,
  onChange,
  label,
}: ModelDropdownProps) {
  const t = useTranslations("settings-ai.modelDropdown");
  const [models, setModels] = useState<{ value: string; label: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const displayLabel = label ?? t("model");

  useEffect(() => {
    let cancelled = false;

    async function loadModels() {
      setLoading(true);
      setError(null);
      setModels([]);
      try {
        const result = await setupApi.getProviderModels(providerName, apiKey, ollamaUrl);
        if (cancelled) return;
        const opts = result.models.map((m) => ({
          value: m.id,
          label: m.name,
        }));
        setModels(opts);
      } catch (e: unknown) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : t("loadFailed");
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    // Only fetch from provider API when we have a key (or Ollama which needs no key)
    if (providerName === "ollama" || apiKey.trim().length > 0) {
      loadModels();
    }

    return () => {
      cancelled = true;
    };
  }, [providerName, apiKey, ollamaUrl, t]);

  if (loading) {
    return (
      <div className="flex flex-col gap-1.5">
        <span className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">
          {displayLabel}
        </span>
        <div className="w-full px-4 py-3 border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)] text-[0.9375rem] text-[var(--color-text-tertiary)]">
          {t("loadingFrom", { provider: getProviderLabel(providerName) })}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-1.5">
        <span className="text-[0.75rem] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-tertiary)]">
          {displayLabel}
        </span>
        <p className="text-[0.8125rem] text-[var(--color-error)] mb-2">{error}</p>
        <Input
          label=""
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={t("enterManually")}
        />
      </div>
    );
  }

  if (models.length > 0) {
    return (
      <Select
        label={displayLabel}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        options={models}
        placeholder={t("selectModel")}
      />
    );
  }

  return (
    <Input
      label={displayLabel}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={t("enterModelId")}
    />
  );
}
