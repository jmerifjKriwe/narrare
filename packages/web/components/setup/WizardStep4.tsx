"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { setupApi } from "@/lib/api/client";
import { PROVIDERS } from "@/lib/providers";
import { useWizardStore } from "@/lib/stores/wizardStore";
import type { AIProvider } from "@/types";

export function WizardStep4({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const t = useTranslations("wizard.step4");
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
      setError(msg || t("validationFailed"));
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <div>
          <h2 className="text-xl font-semibold mb-1">
            {t("title")}
          </h2>
          <p className="text-muted-foreground text-[0.9375rem]">{t("description")}</p>
        </div>
      </div>

      <div className="flex flex-col gap-5">
        <Select
          label={t("provider")}
          value={provider}
          onChange={(e) => setProvider(e.target.value as AIProvider)}
          options={PROVIDERS}
        />

        {provider === "ollama" ? (
          <Input
            label={t("ollamaUrl")}
            value={ollamaUrl}
            onChange={(e) => setOllamaUrl(e.target.value)}
            placeholder="http://localhost:11434"
          />
        ) : (
          <Input
            label={t("apiKey")}
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={t("apiKeyPlaceholder")}
            autoComplete="off"
          />
        )}

        {provider === "zai" && (
          <Select
            label={t("zaiEndpoint")}
            value={zaiEndpoint}
            onChange={(e) => setZaiEndpoint(e.target.value)}
            options={[
              { value: "general", label: "General API (api.z.ai/api/paas/v4)" },
              { value: "coding", label: "Coding API (api.z.ai/api/coding/paas/v4)" },
            ]}
          />
        )}

        {modelsLoading ? (
          <p className="text-sm text-muted-foreground p-2">{t("modelLoading")}</p>
        ) : models.length > 0 ? (
          <Select
            label={t("model")}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            options={models}
            placeholder={t("modelPlaceholder")}
          />
        ) : (
          <Input
            label={t("model")}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={t("modelPlaceholder")}
          />
        )}

        {validating && <p className="text-sm text-blue-600 dark:text-blue-400">{t("validating")}</p>}

        {error && (
          <p className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm">
            {error}
          </p>
        )}
      </div>

      <div className="flex justify-end gap-3 mt-4">
        <Button type="button" variant="secondary" onClick={onBack}>
          ← {tCommon("back")}
        </Button>
        <Button onClick={handleNext} loading={validating} disabled={!model}>
          {tCommon("next")} →
        </Button>
      </div>
    </div>
  );
}
