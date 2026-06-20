"use client";

import { useEffect, useState } from "react";
import { setupApi } from "@/lib/api/client";
import type { AIProvider, ModelCatalogProvenance } from "@/types";

interface ProviderSetupState {
  provider: AIProvider;
  apiKey: string;
  ollamaUrl: string;
  zaiEndpoint: string;
  model: string;
  models: { value: string; label: string }[];
  modelsLoading: boolean;
  validating: boolean;
  error: string | null;
  /** Catalog provenance from the last model-list fetch (null until loaded). */
  provenance: ModelCatalogProvenance | null;
}

interface UseProviderSetupReturn extends ProviderSetupState {
  setProvider: (provider: AIProvider) => void;
  setApiKey: (key: string) => void;
  setOllamaUrl: (url: string) => void;
  setZaiEndpoint: (endpoint: string) => void;
  setModel: (model: string) => void;
  handleValidate: () => Promise<void>;
}

/** Manages provider selection, model loading, and API key validation for wizard step 4. */
export function useProviderSetup(
  initialState: {
    provider: AIProvider;
    api_key: string;
    ollama_url: string;
    zai_endpoint: string;
    model: string;
  },
  onSuccess: (data: {
    provider: AIProvider;
    api_key: string;
    model: string;
    ollama_url: string;
    zai_endpoint: string;
  }) => void,
  onErrorLabel: string,
): UseProviderSetupReturn {
  const [provider, setProvider] = useState<AIProvider>(initialState.provider);
  const [apiKey, setApiKey] = useState(initialState.api_key);
  const [ollamaUrl, setOllamaUrl] = useState(initialState.ollama_url);
  const [zaiEndpoint, setZaiEndpoint] = useState<string>(initialState.zai_endpoint || "general");
  const [model, setModel] = useState(initialState.model);
  const [models, setModels] = useState<{ value: string; label: string }[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provenance, setProvenance] = useState<ModelCatalogProvenance | null>(null);

  // Load models when provider or key changes
  // biome-ignore lint/correctness/useExhaustiveDependencies: loadModels reads latest closure values; ollamaUrl needed to trigger reload for Ollama
  useEffect(() => {
    const key = apiKey.trim();
    if (provider === "ollama" || key.length > 8) {
      loadModels();
    }
  }, [provider, apiKey, ollamaUrl]);

  const loadModels = async () => {
    setModelsLoading(true);
    setModels([]);
    setModel("");
    try {
      const result = await setupApi.getProviderModels(provider, apiKey, ollamaUrl);
      const opts = result.models.map((m) => ({ value: m.id, label: m.name }));
      setModels(opts);
      setProvenance(result.provenance ?? null);
      if (opts.length > 0 && !model) setModel(opts[0].value);
    } catch {
      // Fallback — still show empty list, user can type manually
      setProvenance(null);
    } finally {
      setModelsLoading(false);
    }
  };

  const handleValidate = async () => {
    setError(null);
    setValidating(true);
    try {
      await setupApi.validateStep4({
        provider,
        api_key: apiKey,
        model,
        ollama_url: ollamaUrl,
        zai_endpoint: zaiEndpoint,
      });
      onSuccess({
        provider,
        api_key: apiKey,
        model,
        ollama_url: ollamaUrl,
        zai_endpoint: zaiEndpoint,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg || onErrorLabel);
    } finally {
      setValidating(false);
    }
  };

  return {
    provider,
    apiKey,
    ollamaUrl,
    zaiEndpoint,
    model,
    models,
    modelsLoading,
    validating,
    error,
    provenance,
    setProvider,
    setApiKey,
    setOllamaUrl,
    setZaiEndpoint,
    setModel,
    handleValidate,
  };
}
