"use client";

import { useState } from "react";
import { aiSettingsApi } from "@/lib/api/client";

interface ProviderModelOption {
  readonly value: string;
  readonly label: string;
}

export function useProviderModelCache() {
  const [providerModelsCache, setProviderModelsCache] = useState<
    Record<string, ProviderModelOption[]>
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

  return { providerModelsCache, loadingModels, loadModelsForProvider };
}
