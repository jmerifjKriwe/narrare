"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { setupApi } from "@/lib/api/client";
import { PROVIDERS } from "@/lib/providers";
import { useWizardStore } from "@/lib/stores/wizardStore";
import type { AIProvider } from "@/types";

interface WizardStep4Props {
  onNext: () => void;
  onBack: () => void;
}

export function WizardStep4({ onNext, onBack }: WizardStep4Props) {
  const t = useTranslations("studio");
  const tCommon = useTranslations("common");
  const { updateStep4, state } = useWizardStore();

  const [provider, setProvider] = useState<AIProvider>(state.provider);
  const [apiKey, setApiKey] = useState(state.api_key);
  const [ollamaUrl, setOllamaUrl] = useState(state.ollama_url);
  const [zaiEndpoint, setZaiEndpoint] = useState<string>(state.zai_endpoint || "general");
  const [model, setModel] = useState(state.model);
  const [models, setModels] = useState<{ value: string; label: string }[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      if (opts.length > 0 && !model) setModel(opts[0].value);
    } catch {
      // Fallback — still show empty list, user can type manually
    } finally {
      setModelsLoading(false);
    }
  };

  const handleNext = async () => {
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
      updateStep4({
        provider,
        api_key: apiKey,
        model,
        ollama_url: ollamaUrl,
        zai_endpoint: zaiEndpoint,
      });
      onNext();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg || t("wizard.step4.validationFailed"));
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">{t("wizard.step4.title")}</h2>
        <p className="text-muted-foreground text-[0.9375rem]">{t("wizard.step4.description")}</p>
      </div>

      <div className="flex flex-col gap-5">
        <div>
          <label htmlFor="provider" className="block text-sm font-medium mb-1.5">
            {t("wizard.step4.provider")}
          </label>
          <select
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value as AIProvider)}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        {provider === "ollama" ? (
          <div>
            <label htmlFor="ollama_url" className="block text-sm font-medium mb-1.5">
              {t("wizard.step4.ollamaUrl")}
            </label>
            <input
              id="ollama_url"
              type="text"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://localhost:11434"
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            />
          </div>
        ) : (
          <div>
            <label htmlFor="api_key" className="block text-sm font-medium mb-1.5">
              {t("wizard.step4.apiKey")}
            </label>
            <input
              id="api_key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={t("wizard.step4.apiKeyPlaceholder")}
              autoComplete="off"
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            />
          </div>
        )}

        {provider === "zai" && (
          <div>
            <label htmlFor="zai_endpoint" className="block text-sm font-medium mb-1.5">
              {t("wizard.step4.zaiEndpoint")}
            </label>
            <select
              id="zai_endpoint"
              value={zaiEndpoint}
              onChange={(e) => setZaiEndpoint(e.target.value)}
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            >
              <option value="general">{t("wizard.step4.zaiGeneral")}</option>
              <option value="coding">{t("wizard.step4.zaiCoding")}</option>
            </select>
          </div>
        )}

        {modelsLoading ? (
          <p className="text-sm text-muted-foreground p-2">{t("wizard.step4.modelLoading")}</p>
        ) : models.length > 0 ? (
          <div>
            <label htmlFor="model" className="block text-sm font-medium mb-1.5">
              {t("wizard.step4.model")}
            </label>
            <select
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            >
              <option value="">{t("wizard.step4.modelPlaceholder")}</option>
              {models.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div>
            <label htmlFor="model_input" className="block text-sm font-medium mb-1.5">
              {t("wizard.step4.model")}
            </label>
            <input
              id="model_input"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={t("wizard.step4.modelPlaceholder")}
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            />
          </div>
        )}

        {validating && (
          <p className="text-sm text-blue-600 dark:text-blue-400">{t("wizard.step4.validating")}</p>
        )}

        {error && (
          <p className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm">{error}</p>
        )}
      </div>

      <div className="flex justify-end gap-3 mt-4">
        <button
          type="button"
          onClick={onBack}
          data-testid="wizard-back"
          className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          ← {tCommon("back")}
        </button>
        <button
          type="button"
          onClick={handleNext}
          disabled={validating || !model}
          data-testid="wizard-next"
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {validating ? `${tCommon("next")}…` : `${tCommon("next")} →`}
        </button>
      </div>
    </div>
  );
}
